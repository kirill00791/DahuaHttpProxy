import os
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from pydahua import DahuaAPI
from requests.auth import HTTPDigestAuth

_base_dir = os.path.dirname(__file__)
_project_root = os.path.abspath(os.path.join(_base_dir, '..'))
_env_path = os.path.join(_project_root, '.env')

if os.path.isfile(_env_path):
    load_dotenv(_env_path)
    logger_env_source = _env_path
else:
    logger_env_source = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.CRITICAL)

app = Flask(__name__)

DEVICE_URL_KEY_PATTERN = re.compile(r'^DAHUA_DEVICE_(\d+)_URL$')
HEALTH_CHECK_TIMEOUT = 5


@dataclass(frozen=True)
class DeviceConfig:
    id: str
    url: str
    username: str
    password: str


def _load_devices_from_env() -> Dict[str, DeviceConfig]:
    devices: Dict[str, DeviceConfig] = {}

    for key in os.environ:
        match = DEVICE_URL_KEY_PATTERN.match(key)
        if not match:
            continue

        device_id = match.group(1)
        url = (os.getenv(key) or '').strip()
        user_key = f'DAHUA_DEVICE_{device_id}_USER'
        pass_key = f'DAHUA_DEVICE_{device_id}_PASS'
        username = (os.getenv(user_key) or '').strip()
        password = (os.getenv(pass_key) or '').strip()

        if not url:
            raise ValueError(f'DAHUA_DEVICE_{device_id}_URL не задан или пуст')
        if not username:
            raise ValueError(f'Отсутствует {user_key} для устройства {device_id}')
        if not password:
            raise ValueError(f'Отсутствует {pass_key} для устройства {device_id}')
        if device_id in devices:
            raise ValueError(f'Дублирующийся ID устройства: {device_id}')

        devices[device_id] = DeviceConfig(
            id=device_id,
            url=url,
            username=username,
            password=password,
        )

    if devices:
        return devices

    legacy_ip = (os.getenv('DAHUA_IP') or '').strip()
    legacy_user = (os.getenv('DAHUA_USERNAME') or '').strip()
    legacy_pass = (os.getenv('DAHUA_PASSWORD') or '').strip()

    if legacy_ip and legacy_user and legacy_pass:
        logger.warning(
            'Используется устаревший формат DAHUA_IP/DAHUA_USERNAME/DAHUA_PASSWORD. '
            'Перейдите на DAHUA_DEVICE_{id}_URL/USER/PASS.'
        )
        return {
            '1': DeviceConfig(
                id='1',
                url=legacy_ip,
                username=legacy_user,
                password=legacy_pass,
            )
        }

    raise ValueError(
        f'Не задана конфигурация устройств Dahua. '
        f'Создайте файл {_env_path} по образцу .env.example.'
    )


DEVICES = _load_devices_from_env()
logger.info('Конфиг: %s', logger_env_source or 'переменные окружения процесса')
for device in sorted(DEVICES.values(), key=lambda d: int(d.id)):
    logger.info('  устройство %s: %s (user=%s)', device.id, device.url, device.username)
logger.info('Загружено устройств: %s', len(DEVICES))


def get_device(device_id: str) -> DeviceConfig:
    device = DEVICES.get(device_id)
    if not device:
        raise KeyError(device_id)
    return device


def get_dahua_client(device_id: str) -> DahuaAPI:
    device = get_device(device_id)
    try:
        client = DahuaAPI(
            ip=device.url,
            username=device.username,
            password=device.password,
        )
        logger.info('Клиент Dahua создан для устройства %s', device_id)
        return client
    except Exception as e:
        logger.error('Ошибка создания клиента Dahua для устройства %s: %s', device_id, e)
        raise


def get_device_auth(device_id: str) -> HTTPDigestAuth:
    device = get_device(device_id)
    return HTTPDigestAuth(device.username, device.password)


class DahuaDeviceResponseError(Exception):
    """Считыватель вернул неожиданный или ошибочный ответ."""

    def __init__(self, message: str, details=None):
        super().__init__(message)
        self.details = details


def error_response(message: str, status: int = 400, details=None, **extra):
    payload = {'success': False, 'error': message}
    if details is not None:
        payload['details'] = details
    payload.update(extra)
    return jsonify(payload), status


def device_error_response(message: str, details=None, status: int = 502, **extra):
    return error_response(message, status=status, details=details, **extra)


def device_not_found_response(device_id: str):
    return error_response(f'Unknown deviceId: {device_id}', status=404)


def _normalize_dahua_datetime(value: Any, *, end_of_day: bool = False) -> str:
    """Normalize to Dahua ValidDate* format: yyyyMMdd HHMMSS."""
    if value is None:
        return ''
    text = str(value).strip()
    if not text:
        return ''

    formats = (
        '%Y%m%d %H%M%S',
        '%Y%m%d%H%M%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%Y%m%d',
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            if fmt in ('%Y-%m-%d', '%Y%m%d'):
                if end_of_day:
                    dt = dt.replace(hour=23, minute=59, second=59)
                else:
                    dt = dt.replace(hour=0, minute=0, second=0)
            return dt.strftime('%Y%m%d %H%M%S')
        except ValueError:
            continue

    raise ValueError(
        'Неверный формат даты. Используйте YYYY-MM-DD, '
        'YYYY-MM-DD HH:MM:SS или yyyyMMdd HHMMSS'
    )


def _parse_cgi_kv_body(body: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for raw_line in (body or '').replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        line = raw_line.strip()
        if not line or '=' not in line:
            continue
        key, value = line.split('=', 1)
        result[key.strip()] = value.strip()
    return result


def _append_array_params(params: Dict[str, Any], name: str, values: Optional[List[Any]]) -> None:
    if values is None:
        return
    for index, value in enumerate(values):
        params[f'{name}[{index}]'] = value


def _card_fields_from_payload(
    data: Dict[str, Any],
    *,
    include_identity: bool = False,
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Build AccessControlCard CGI fields from JSON. Returns (params, error_response)."""
    params: Dict[str, Any] = {}

    if include_identity:
        params['CardName'] = data['card_name']
        params['CardNo'] = data['card_no']
        params['UserID'] = data['user_id']

    optional_scalars = {
        'card_name': 'CardName',
        'card_status': 'CardStatus',
        'card_type': 'CardType',
        'password': 'Password',
        'vto_position': 'VTOPosition',
        'user_type': 'UserType',
        'use_time': 'UseTime',
    }
    for src, dst in optional_scalars.items():
        if src in data and data[src] is not None:
            params[dst] = data[src]

    if 'is_valid' in data and data['is_valid'] is not None:
        params['IsValid'] = 'true' if bool(data['is_valid']) else 'false'

    if 'first_enter' in data and data['first_enter'] is not None:
        params['FirstEnter'] = 'true' if bool(data['first_enter']) else 'false'

    if 'doors' in data:
        _append_array_params(params, 'Doors', data.get('doors'))
    if 'time_sections' in data:
        _append_array_params(params, 'TimeSections', data.get('time_sections'))

    try:
        if 'valid_date_start' in data and data['valid_date_start'] not in (None, ''):
            params['ValidDateStart'] = _normalize_dahua_datetime(
                data['valid_date_start'],
                end_of_day=False,
            )
        if 'valid_date_end' in data and data['valid_date_end'] not in (None, ''):
            params['ValidDateEnd'] = _normalize_dahua_datetime(
                data['valid_date_end'],
                end_of_day=True,
            )
    except ValueError as e:
        return {}, error_response(str(e), status=400)

    return params, None


def find_card_recno(device_id: str, card_no: str) -> Optional[str]:
    dahua = get_dahua_client(device_id)
    auth = get_device_auth(device_id)
    response = requests.get(
        f'{dahua.base_url}recordFinder.cgi',
        params={
            'action': 'find',
            'name': 'AccessControlCard',
            'CardNo': card_no,
        },
        auth=auth,
        timeout=10,
    )
    if response.status_code != 200:
        raise DahuaDeviceResponseError('Search failed', details=response.text)

    if not _is_record_finder_response(response.text):
        raise DahuaDeviceResponseError(
            'Некорректный ответ считывателя при поиске карты',
            details=response.text[:500],
        )

    # Match the parsed record. RecNo is often emitted before CardNo, so a
    # "CardNo ... next RecNo" regex can bind the following card.
    card_no_norm = str(card_no).strip().upper()
    for card in parse_card_records(response.text):
        if str(card.get('CardNo', '')).strip().upper() != card_no_norm:
            continue
        recno = card.get('RecNo')
        return str(recno) if recno is not None else None
    return None


def check_device_reachable(device: DeviceConfig) -> str:
    try:
        base_url = device.url if device.url.endswith('/') else f'{device.url}/'
        response = requests.get(
            base_url,
            auth=HTTPDigestAuth(device.username, device.password),
            timeout=HEALTH_CHECK_TIMEOUT,
        )
        if response.status_code < 500:
            return 'ok'
        return 'unreachable'
    except requests.RequestException:
        return 'unreachable'


@app.route('/api/devices', methods=['GET'])
def list_devices():
    """Список настроенных считывателей (без паролей)."""
    return jsonify({
        'devices': [
            {
                'id': device.id,
                'url': device.url,
                'username': device.username,
            }
            for device in sorted(DEVICES.values(), key=lambda d: int(d.id))
        ]
    })


@app.route('/api/devices/<device_id>/get_open_door_records', methods=['POST'])
def get_open_door_records(device_id: str):
    if device_id not in DEVICES:
        return device_not_found_response(device_id)

    if not request.is_json:
        logger.warning('Запрос без JSON (device %s)', device_id)
        return error_response('Content-Type должен быть application/json', status=400)

    data = request.get_json()
    if not data:
        logger.warning('Пустой JSON (device %s)', device_id)
        return error_response('Пустое тело запроса', status=400)

    required_fields = ['startTime', 'endTime']
    for field in required_fields:
        if field not in data:
            logger.warning('Отсутствует поле %s (device %s)', field, device_id)
            return error_response(f'Отсутствует обязательное поле: {field}', status=400)

    try:
        start_time = datetime.strptime(data['startTime'], '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(data['endTime'], '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        logger.warning('Неверный формат времени (device %s): %s', device_id, e)
        return error_response(
            'Неверный формат времени. Используйте YYYY-MM-DD HH:MM:SS',
            status=400,
        )

    card_no = data.get('cardNo', None)

    try:
        dahua = get_dahua_client(device_id)
        logs = dahua.get_control_card_rec(
            card_no=card_no,
            start_time=start_time,
            end_time=end_time,
        )
        if isinstance(logs, dict) and 'records' in logs:
            record_count = len(logs['records'])
            found = logs.get('found', record_count)
            logger.info(
                'get_control_card_rec(device=%s): %s записей (found: %s)',
                device_id, record_count, found,
            )
        else:
            record_count = len(logs) if isinstance(logs, list) else 0
            logger.info(
                'get_control_card_rec(device=%s): %s записей',
                device_id, record_count,
            )
        return jsonify(logs)
    except KeyError:
        return device_not_found_response(device_id)
    except requests.Timeout as e:
        logger.error('get_control_card_rec(device=%s): timeout: %s', device_id, e)
        return device_error_response(
            'Таймаут при обращении к считывателю Dahua',
            details=str(e),
            status=504,
        )
    except requests.RequestException as e:
        logger.error('get_control_card_rec(device=%s): %s', device_id, e)
        return device_error_response(
            'Не удалось связаться со считывателем Dahua',
            details=str(e),
            status=502,
        )
    except Exception as e:
        logger.error('get_control_card_rec(device=%s): %s', device_id, e)
        return device_error_response(
            'Внутренняя ошибка сервера при обращении к считывателю Dahua',
            details=str(e),
            status=500,
        )


# Methods that involve an access card (Dahua OpenDoorMethod).
_CARD_METHODS = {1, 2, 3, 9, 25, 29, 30, 32, 33, 34, 36, 37, 38, 39}
_METHOD_NAMES = {
    0: 'password',
    1: 'card',
    2: 'card_then_password',
    3: 'password_then_card',
    4: 'remote',
    5: 'button',
    6: 'fingerprint',
    12: 'key',
    15: 'face',
}
_EVENT_FILTERS = {'all', 'card', 'non_card'}
_ACCESS_EVENTS_COUNT = 1024


def _format_record_time(value):
    if value is None or value == '':
        return None
    try:
        return datetime.fromtimestamp(int(value)).strftime('%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError, OSError):
        return str(value)


def _as_int(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_card_method(method, card_no) -> bool:
    parsed = _as_int(method)
    if parsed is None:
        return bool(str(card_no or '').strip())
    return parsed in _CARD_METHODS


def _record_finder_find(device_id: str, name: str, start_time: datetime, end_time: datetime):
    dahua = get_dahua_client(device_id)
    auth = get_device_auth(device_id)
    response = requests.get(
        f'{dahua.base_url}recordFinder.cgi',
        params={
            'action': 'find',
            'name': name,
            'StartTime': int(start_time.timestamp()),
            'EndTime': int(end_time.timestamp()),
            'count': _ACCESS_EVENTS_COUNT,
        },
        auth=auth,
        timeout=10,
    )
    body = response.text or ''
    logger.info(
        'recordFinder %s (device=%s): status=%s, bytes=%s',
        name, device_id, response.status_code, len(body),
    )
    return response


def _normalize_unlock_record(card: Dict) -> Dict:
    method = _as_int(card.get('Method'))
    card_no = card.get('CardNo') or ''
    return {
        'source': 'unlock',
        'time': _format_record_time(card.get('CreateTime')),
        'rec_no': card.get('RecNo'),
        'type': card.get('Type'),
        'status': _as_int(card.get('Status')),
        'method': method,
        'method_name': _METHOD_NAMES.get(method, 'other' if method is not None else None),
        'is_card': _is_card_method(method, card_no),
        'card_no': card_no or None,
        'card_name': card.get('CardName'),
        'user_id': card.get('UserID'),
        'door': _as_int(card.get('Door')),
        'reader_id': card.get('ReaderID'),
        'error_code': _as_int(card.get('ErrorCode')),
        'event_code': None,
    }


def _normalize_alarm_record(card: Dict) -> Dict:
    event_code = card.get('EventCode')
    return {
        'source': 'alarm',
        'time': card.get('Time') or _format_record_time(card.get('CreateTime')),
        'rec_no': card.get('RecNo'),
        'type': None,
        'status': None,
        'method': None,
        'method_name': None,
        'is_card': False,
        'card_no': None,
        'card_name': None,
        'user_id': card.get('UserID'),
        'door': _as_int(card.get('IndexNum') if card.get('IndexNum') is not None else card.get('DevAddrs')),
        'reader_id': None,
        'error_code': None,
        'event_code': event_code,
    }


@app.route('/api/devices/<device_id>/get_access_events', methods=['POST'])
def get_access_events(device_id: str):
    """Unlock journal plus door alarms. Filter events=all|card|non_card."""
    if device_id not in DEVICES:
        return device_not_found_response(device_id)

    if not request.is_json:
        return error_response('Content-Type должен быть application/json', status=400)

    data = request.get_json()
    if not data:
        return error_response('Пустое тело запроса', status=400)

    for field in ('startTime', 'endTime'):
        if field not in data:
            return error_response(f'Отсутствует обязательное поле: {field}', status=400)

    try:
        start_time = datetime.strptime(data['startTime'], '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(data['endTime'], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return error_response(
            'Неверный формат времени. Используйте YYYY-MM-DD HH:MM:SS',
            status=400,
        )

    events_filter = str(data.get('events', 'all') or 'all').strip().lower()
    if events_filter not in _EVENT_FILTERS:
        return error_response(
            'events должен быть all, card или non_card',
            status=400,
        )

    user_id = data.get('user_id')
    user_id_norm = str(user_id).strip() if user_id not in (None, '') else None

    try:
        unlock_response = _record_finder_find(
            device_id, 'AccessControlCardRec', start_time, end_time,
        )
        if unlock_response.status_code != 200 or not _is_record_finder_response(unlock_response.text):
            return device_error_response(
                'Не удалось получить журнал открытий со считывателя',
                details=(unlock_response.text or '')[:500],
                status=502,
            )

        records = [
            _normalize_unlock_record(card)
            for card in parse_card_records(unlock_response.text)
        ]
        unlock_found = None
        for line in (unlock_response.text or '').splitlines():
            if line.startswith('found='):
                unlock_found = line.split('=', 1)[1].strip()
                break

        alarm_status = 'ok'
        alarm_found = None
        try:
            alarm_response = _record_finder_find(
                device_id, 'AccessControlAlarmRecord', start_time, end_time,
            )
            if (
                alarm_response.status_code == 200
                and _is_record_finder_response(alarm_response.text)
                and 'Error' not in alarm_response.text
            ):
                records.extend(
                    _normalize_alarm_record(card)
                    for card in parse_card_records(alarm_response.text)
                )
                for line in alarm_response.text.splitlines():
                    if line.startswith('found='):
                        alarm_found = line.split('=', 1)[1].strip()
                        break
            else:
                alarm_status = 'unavailable'
                logger.warning(
                    'AccessControlAlarmRecord недоступен (device=%s): %s',
                    device_id, (alarm_response.text or '')[:300],
                )
        except requests.RequestException as e:
            alarm_status = 'unavailable'
            logger.warning(
                'AccessControlAlarmRecord недоступен (device=%s): %s',
                device_id, e,
            )

        if user_id_norm is not None:
            records = [
                record for record in records
                if str(record.get('user_id') or '').strip() == user_id_norm
            ]
        if events_filter == 'card':
            records = [record for record in records if record['is_card']]
        elif events_filter == 'non_card':
            records = [record for record in records if not record['is_card']]

        records.sort(key=lambda record: record.get('time') or '')

        return jsonify({
            'success': True,
            'count': len(records),
            'events': events_filter,
            'unlock_found': unlock_found,
            'alarm_found': alarm_found,
            'alarm_status': alarm_status,
            'records': records,
        })
    except KeyError:
        return device_not_found_response(device_id)
    except requests.Timeout as e:
        logger.error('get_access_events(device=%s): timeout: %s', device_id, e)
        return device_error_response(
            'Таймаут при обращении к считывателю Dahua',
            details=str(e),
            status=504,
        )
    except requests.RequestException as e:
        logger.error('get_access_events(device=%s): %s', device_id, e)
        return device_error_response(
            'Не удалось связаться со считывателем Dahua',
            details=str(e),
            status=502,
        )
    except Exception as e:
        logger.error('get_access_events(device=%s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Внутренняя ошибка сервера при обращении к считывателю Dahua',
            details=str(e),
            status=500,
        )


def _door_control(device_id: str, action: str, channel: int, user_id=None):
    """Remote open/close door via Dahua accessControl.cgi."""
    dahua = get_dahua_client(device_id)
    auth = get_device_auth(device_id)
    url = f'{dahua.base_url}accessControl.cgi'
    params = {
        'action': action,
        'channel': channel,
        'Type': 'Remote',
    }
    if user_id is not None and str(user_id).strip() != '':
        params['UserID'] = user_id

    logger.info(
        '%s(device=%s, channel=%s, user_id=%s)',
        action, device_id, channel, user_id,
    )
    response = requests.get(url, params=params, auth=auth, timeout=10)
    body = (response.text or '').strip()
    logger.info(
        '%s(device=%s): status=%s, body=%s',
        action, device_id, response.status_code, body,
    )
    return response.status_code, body


def _parse_door_control_request(device_id: str):
    if device_id not in DEVICES:
        return None, device_not_found_response(device_id)

    data = {}
    if request.data:
        if not request.is_json:
            return None, error_response(
                'Content-Type должен быть application/json',
                status=400,
            )
        data = request.get_json(silent=True)
        if data is None:
            return None, error_response(
                'Пустое или некорректное тело запроса',
                status=400,
            )

    channel = data.get('channel', 1)
    try:
        channel = int(channel)
    except (TypeError, ValueError):
        return None, error_response('channel должен быть целым числом', status=400)

    if channel < 1:
        return None, error_response('channel должен быть >= 1', status=400)

    user_id = data.get('user_id')
    return {'channel': channel, 'user_id': user_id}, None


@app.route('/api/devices/<device_id>/open_door', methods=['POST'])
def open_door(device_id: str):
    parsed, parse_error = _parse_door_control_request(device_id)
    if parse_error is not None:
        return parse_error

    try:
        status_code, body = _door_control(
            device_id,
            action='openDoor',
            channel=parsed['channel'],
            user_id=parsed['user_id'],
        )
        if status_code == 200 and 'Error' not in body:
            return jsonify({
                'success': True,
                'action': 'openDoor',
                'channel': parsed['channel'],
                'device_response': body or 'OK',
            })
        return device_error_response(
            'Open door failed',
            details=body,
            status=502,
            channel=parsed['channel'],
        )
    except KeyError:
        return device_not_found_response(device_id)
    except requests.Timeout as e:
        logger.error('open_door(device=%s): timeout: %s', device_id, e, exc_info=True)
        return device_error_response(
            'Таймаут при обращении к считывателю Dahua',
            details=str(e),
            status=504,
        )
    except requests.RequestException as e:
        logger.error('open_door(device=%s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Не удалось связаться со считывателем Dahua',
            details=str(e),
            status=502,
        )
    except Exception as e:
        logger.error('open_door(device=%s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Внутренняя ошибка сервера при обращении к считывателю Dahua',
            details=str(e),
            status=500,
        )


@app.route('/api/devices/<device_id>/close_door', methods=['POST'])
def close_door(device_id: str):
    parsed, parse_error = _parse_door_control_request(device_id)
    if parse_error is not None:
        return parse_error

    try:
        status_code, body = _door_control(
            device_id,
            action='closeDoor',
            channel=parsed['channel'],
            user_id=parsed['user_id'],
        )
        if status_code == 200 and 'Error' not in body:
            return jsonify({
                'success': True,
                'action': 'closeDoor',
                'channel': parsed['channel'],
                'device_response': body or 'OK',
            })
        return device_error_response(
            'Close door failed',
            details=body,
            status=502,
            channel=parsed['channel'],
        )
    except KeyError:
        return device_not_found_response(device_id)
    except requests.Timeout as e:
        logger.error('close_door(device=%s): timeout: %s', device_id, e, exc_info=True)
        return device_error_response(
            'Таймаут при обращении к считывателю Dahua',
            details=str(e),
            status=504,
        )
    except requests.RequestException as e:
        logger.error('close_door(device=%s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Не удалось связаться со считывателем Dahua',
            details=str(e),
            status=502,
        )
    except Exception as e:
        logger.error('close_door(device=%s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Внутренняя ошибка сервера при обращении к считывателю Dahua',
            details=str(e),
            status=500,
        )


def _parse_channel_query(device_id: str):
    if device_id not in DEVICES:
        return None, device_not_found_response(device_id)

    channel = request.args.get('channel', 1)
    try:
        channel = int(channel)
    except (TypeError, ValueError):
        return None, error_response('channel должен быть целым числом', status=400)
    if channel < 1:
        return None, error_response('channel должен быть >= 1', status=400)
    return channel, None


def _get_access_control_status(device_id: str, action: str, channel: int):
    dahua = get_dahua_client(device_id)
    auth = get_device_auth(device_id)
    response = requests.get(
        f'{dahua.base_url}accessControl.cgi',
        params={'action': action, 'channel': channel},
        auth=auth,
        timeout=10,
    )
    body = (response.text or '').strip()
    logger.info(
        '%s(device=%s, channel=%s): status=%s, body=%s',
        action, device_id, channel, response.status_code, body,
    )
    return response.status_code, body


@app.route('/api/devices/<device_id>/get_door_status', methods=['GET'])
def get_door_status(device_id: str):
    channel, parse_error = _parse_channel_query(device_id)
    if parse_error is not None:
        return parse_error

    try:
        status_code, body = _get_access_control_status(device_id, 'getDoorStatus', channel)
        if status_code != 200 or 'Error' in body:
            return device_error_response(
                'Get door status failed',
                details=body,
                status=502,
                channel=channel,
            )
        parsed = _parse_cgi_kv_body(body)
        return jsonify({
            'success': True,
            'action': 'getDoorStatus',
            'channel': channel,
            'status': parsed.get('Info.status') or parsed.get('status'),
            'raw': parsed or {'result': body},
        })
    except KeyError:
        return device_not_found_response(device_id)
    except requests.Timeout as e:
        logger.error('get_door_status(device=%s): timeout: %s', device_id, e, exc_info=True)
        return device_error_response(
            'Таймаут при обращении к считывателю Dahua',
            details=str(e),
            status=504,
        )
    except requests.RequestException as e:
        logger.error('get_door_status(device=%s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Не удалось связаться со считывателем Dahua',
            details=str(e),
            status=502,
        )
    except Exception as e:
        logger.error('get_door_status(device=%s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Внутренняя ошибка сервера при обращении к считывателю Dahua',
            details=str(e),
            status=500,
        )


@app.route('/api/devices/<device_id>/get_lock_status', methods=['GET'])
def get_lock_status(device_id: str):
    channel, parse_error = _parse_channel_query(device_id)
    if parse_error is not None:
        return parse_error

    try:
        status_code, body = _get_access_control_status(device_id, 'getLockStatus', channel)
        if status_code != 200 or 'Error' in body:
            return device_error_response(
                'Get lock status failed',
                details=body,
                status=502,
                channel=channel,
            )
        parsed = _parse_cgi_kv_body(body)
        return jsonify({
            'success': True,
            'action': 'getLockStatus',
            'channel': channel,
            'status': parsed.get('status'),
            'online_status': parsed.get('onLineStatus') or parsed.get('onlineStatus'),
            'raw': parsed or {'result': body},
        })
    except KeyError:
        return device_not_found_response(device_id)
    except requests.Timeout as e:
        logger.error('get_lock_status(device=%s): timeout: %s', device_id, e, exc_info=True)
        return device_error_response(
            'Таймаут при обращении к считывателю Dahua',
            details=str(e),
            status=504,
        )
    except requests.RequestException as e:
        logger.error('get_lock_status(device=%s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Не удалось связаться со считывателем Dahua',
            details=str(e),
            status=502,
        )
    except Exception as e:
        logger.error('get_lock_status(device=%s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Внутренняя ошибка сервера при обращении к считывателю Dahua',
            details=str(e),
            status=500,
        )


@app.route('/api/devices/<device_id>/add_user_card', methods=['POST'])
def enroll_new_user(device_id: str):
    if device_id not in DEVICES:
        return device_not_found_response(device_id)

    if not request.is_json:
        logger.warning('Запрос без JSON (device %s)', device_id)
        return error_response('Content-Type должен быть application/json', status=400)

    data = request.get_json()
    if not data:
        logger.warning('Пустой JSON (device %s)', device_id)
        return error_response('Пустое тело запроса', status=400)

    required_fields = ['card_name', 'card_no', 'user_id']
    for field in required_fields:
        if field not in data:
            logger.warning('Отсутствует поле %s (device %s)', field, device_id)
            return error_response(f'Отсутствует обязательное поле: {field}', status=400)

    # Defaults for insert (optional fields stay optional for callers)
    payload = {
        'card_name': data['card_name'],
        'card_no': data['card_no'],
        'user_id': data['user_id'],
        'card_status': data.get('card_status', 0),
        'card_type': data.get('card_type', 0),
        'is_valid': data.get('is_valid', True),
    }
    for key in (
        'password',
        'doors',
        'time_sections',
        'vto_position',
        'valid_date_start',
        'valid_date_end',
        'user_type',
        'first_enter',
        'use_time',
    ):
        if key in data:
            payload[key] = data[key]

    card_params, field_error = _card_fields_from_payload(payload, include_identity=True)
    if field_error is not None:
        return field_error

    try:
        dahua = get_dahua_client(device_id)
        auth = get_device_auth(device_id)
        params = {
            'action': 'insert',
            'name': 'AccessControlCard',
            **card_params,
        }
        response = requests.get(
            f'{dahua.base_url}recordUpdater.cgi',
            params=params,
            auth=auth,
            timeout=10,
        )
        body = (response.text or '').strip()
        logger.info(
            'enroll_new_user(device=%s): status=%s, body=%s',
            device_id, response.status_code, body,
        )
        if response.status_code != 200 or 'Error' in body:
            return device_error_response(
                'Add user card failed',
                details=body,
                status=502,
            )

        parsed = _parse_cgi_kv_body(body)
        result = {'status_code': response.status_code, **parsed}
        if 'RecNo' not in result and body and '=' not in body:
            result['result'] = body
        logger.info(
            'enroll_new_user(device=%s): зарегистрирован %s',
            device_id, data['card_name'],
        )
        return jsonify(result)
    except KeyError:
        return device_not_found_response(device_id)
    except requests.Timeout as e:
        logger.error('enroll_new_user(device=%s): timeout: %s', device_id, e)
        return device_error_response(
            'Таймаут при обращении к считывателю Dahua',
            details=str(e),
            status=504,
        )
    except requests.RequestException as e:
        logger.error('enroll_new_user(device=%s): %s', device_id, e)
        return device_error_response(
            'Не удалось связаться со считывателем Dahua',
            details=str(e),
            status=502,
        )
    except Exception as e:
        logger.error('enroll_new_user(device=%s): %s', device_id, e)
        return device_error_response(
            'Внутренняя ошибка сервера при обращении к считывателю Dahua',
            details=str(e),
            status=500,
        )


@app.route('/api/devices/<device_id>/update_user_card', methods=['POST'])
def update_user_card(device_id: str):
    if device_id not in DEVICES:
        return device_not_found_response(device_id)

    if not request.is_json:
        return error_response('Content-Type должен быть application/json', status=400)

    data = request.get_json()
    if not data:
        return error_response('Пустое тело запроса', status=400)

    card_no = data.get('card_no')
    if not card_no:
        return error_response('card_no is required', status=400)

    update_keys = {
        'card_name',
        'card_status',
        'card_type',
        'password',
        'doors',
        'time_sections',
        'vto_position',
        'valid_date_start',
        'valid_date_end',
        'is_valid',
        'user_type',
        'first_enter',
        'use_time',
    }
    if not any(key in data for key in update_keys):
        return error_response(
            'Укажите хотя бы одно поле для обновления '
            '(card_name, card_status, is_valid, doors, …)',
            status=400,
        )

    card_params, field_error = _card_fields_from_payload(data, include_identity=False)
    if field_error is not None:
        return field_error
    if not card_params:
        return error_response('Нет корректных полей для обновления', status=400)

    try:
        recno = find_card_recno(device_id, card_no)
        if not recno:
            return error_response(f'Card {card_no} not found', status=404)

        dahua = get_dahua_client(device_id)
        auth = get_device_auth(device_id)
        params = {
            'action': 'update',
            'name': 'AccessControlCard',
            'recno': recno,
            **card_params,
        }
        response = requests.get(
            f'{dahua.base_url}recordUpdater.cgi',
            params=params,
            auth=auth,
            timeout=10,
        )
        body = (response.text or '').strip()
        logger.info(
            'update_user_card(device=%s, card_no=%s, recno=%s): status=%s, body=%s',
            device_id, card_no, recno, response.status_code, body,
        )
        if response.status_code == 200 and 'Error' not in body:
            return jsonify({
                'success': True,
                'message': f'Card {card_no} (RecNo={recno}) updated successfully',
                'recno': recno,
                'device_response': body or 'OK',
            })
        return device_error_response(
            'Update failed',
            details=body,
            status=502,
            recno=recno,
        )
    except KeyError:
        return device_not_found_response(device_id)
    except DahuaDeviceResponseError as e:
        logger.error('update_user_card(device=%s): %s', device_id, e)
        return device_error_response(str(e), details=e.details, status=502)
    except requests.Timeout as e:
        logger.error('update_user_card(device=%s): timeout: %s', device_id, e, exc_info=True)
        return device_error_response(
            'Таймаут при обращении к считывателю Dahua',
            details=str(e),
            status=504,
        )
    except requests.RequestException as e:
        logger.error('update_user_card(device=%s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Не удалось связаться со считывателем Dahua',
            details=str(e),
            status=502,
        )
    except Exception as e:
        logger.error('update_user_card(device=%s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Внутренняя ошибка сервера при обращении к считывателю Dahua',
            details=str(e),
            status=500,
        )


@app.route('/api/devices/<device_id>/remove_user_card', methods=['POST'])
def delete_card(device_id: str):
    if device_id not in DEVICES:
        return device_not_found_response(device_id)

    if not request.is_json:
        return error_response('JSON required', status=400)

    data = request.get_json()
    card_no = data.get('card_no')

    if not card_no:
        return error_response('card_no is required', status=400)

    try:
        logger.info('Ищем карту %s (device %s)', card_no, device_id)
        recno = find_card_recno(device_id, card_no)
        if not recno:
            logger.warning('Карта %s не найдена (device %s)', card_no, device_id)
            return error_response(f'Card {card_no} not found', status=404)

        logger.info('Найден RecNo=%s для карты %s (device %s)', recno, card_no, device_id)

        dahua = get_dahua_client(device_id)
        auth = get_device_auth(device_id)
        delete_params = {
            'action': 'remove',
            'name': 'AccessControlCard',
            'recno': recno,
        }

        logger.info('Удаляем карту (device %s): %s', device_id, delete_params)
        delete_response = requests.get(
            f'{dahua.base_url}recordUpdater.cgi',
            params=delete_params,
            auth=auth,
            timeout=10,
        )

        logger.info(
            'Ответ на удаление (device %s): status=%s, body=%s',
            device_id, delete_response.status_code, delete_response.text,
        )

        if delete_response.status_code == 200 and 'Error' not in delete_response.text:
            logger.info('Карта %s удалена (device %s)', card_no, device_id)
            return jsonify({
                'success': True,
                'message': f'Card {card_no} (RecNo={recno}) deleted successfully',
                'recno': recno,
            })

        logger.error('Ошибка удаления (device %s): %s', device_id, delete_response.text)
        return device_error_response(
            'Deletion failed',
            details=delete_response.text,
            status=502,
            recno=recno,
        )

    except KeyError:
        return device_not_found_response(device_id)
    except DahuaDeviceResponseError as e:
        logger.error('Исключение (device %s): %s', device_id, e, exc_info=True)
        return device_error_response(str(e), details=e.details, status=502)
    except requests.Timeout as e:
        logger.error('Исключение (device %s): timeout: %s', device_id, e, exc_info=True)
        return device_error_response(
            'Таймаут при обращении к считывателю Dahua',
            details=str(e),
            status=504,
        )
    except requests.RequestException as e:
        logger.error('Исключение (device %s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Не удалось связаться со считывателем Dahua',
            details=str(e),
            status=502,
        )
    except Exception as e:
        logger.error('Исключение (device %s): %s', device_id, e, exc_info=True)
        return device_error_response(
            'Внутренняя ошибка сервера при обращении к считывателю Dahua',
            details=str(e),
            status=500,
        )


@app.route('/api/devices/<device_id>/get_user_cards', methods=['GET'])
def api_get_all_cards(device_id: str):
    if device_id not in DEVICES:
        return device_not_found_response(device_id)

    card_no = request.args.get('card_no') or None
    user_id = request.args.get('user_id') or None

    try:
        cards = get_user_card_all(device_id, card_no=card_no, user_id=user_id)
        return jsonify({
            'success': True,
            'count': len(cards),
            'cards': cards,
            'filters': {
                'card_no': card_no,
                'user_id': user_id,
            },
        })
    except requests.Timeout as e:
        logger.error('Ошибка (device %s): timeout: %s', device_id, e)
        return device_error_response(
            'Таймаут при получении списка карт со считывателя',
            details=str(e),
            status=504,
        )
    except requests.RequestException as e:
        logger.error('Ошибка (device %s): %s', device_id, e)
        return device_error_response(
            'Не удалось получить список карт со считывателя',
            details=str(e),
            status=502,
        )
    except DahuaDeviceResponseError as e:
        logger.error('Ошибка (device %s): %s', device_id, e)
        return device_error_response(str(e), details=e.details, status=502)
    except Exception as e:
        logger.error('Ошибка (device %s): %s', device_id, e)
        return device_error_response(
            'Внутренняя ошибка сервера при обращении к считывателю Dahua',
            details=str(e),
            status=500,
        )


def get_user_card_all(
    device_id: str,
    card_no: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List[Dict]:
    dahua = get_dahua_client(device_id)
    base_url = dahua.base_url
    auth = get_device_auth(device_id)

    url = f"{base_url}recordFinder.cgi"
    params: Dict[str, Any] = {
        'action': 'find',
        'name': 'AccessControlCard',
    }
    if card_no:
        params['CardNo'] = card_no
    if user_id:
        params['UserID'] = user_id

    response = requests.get(url, params=params, auth=auth, timeout=10)

    if response.status_code != 200:
        logger.error(
            'Ошибка получения списка карт (device %s): %s',
            device_id, response.text,
        )
        raise DahuaDeviceResponseError(
            'Не удалось получить список карт со считывателя',
            details=response.text,
        )

    if not _is_record_finder_response(response.text):
        logger.error(
            'Некорректный ответ при получении списка карт (device %s): %s',
            device_id, response.text[:500],
        )
        raise DahuaDeviceResponseError(
            'Некорректный ответ считывателя при получении списка карт',
            details=response.text[:500],
        )

    cards = parse_card_records(response.text)

    # Client-side filter as a safety net if the device ignores finder conditions.
    if card_no:
        card_no_norm = str(card_no).strip().upper()
        cards = [
            card for card in cards
            if str(card.get('CardNo', '')).strip().upper() == card_no_norm
        ]
    if user_id is not None and str(user_id).strip() != '':
        user_id_norm = str(user_id).strip()
        cards = [
            card for card in cards
            if str(card.get('UserID', '')).strip() == user_id_norm
        ]

    logger.info(
        'Получено %s карт (device %s, card_no=%s, user_id=%s)',
        len(cards), device_id, card_no, user_id,
    )
    return cards


def _is_record_finder_response(raw_text: str) -> bool:
    return 'found=' in raw_text or 'records[' in raw_text


def parse_card_records(raw_text: str) -> List[Dict]:
    normalized = raw_text.replace('\r\\', '\r\n')
    lines = normalized.strip().split('\r\n')

    records_by_index = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('found='):
            continue

        records_pos = line.find('records[')
        if records_pos == -1:
            continue

        line = line[records_pos:]

        match = re.match(r'records\[(\d+)\]\.(.+)', line)
        if not match:
            continue

        index = int(match.group(1))
        rest = match.group(2)

        if index not in records_by_index:
            records_by_index[index] = {}

        if '=' in rest:
            array_match = re.match(r'(\w+)\[(\d+)\]=(.+)', rest)
            if array_match:
                array_name = array_match.group(1)
                array_index = int(array_match.group(2))
                array_value = array_match.group(3)

                if array_name not in records_by_index[index]:
                    records_by_index[index][array_name] = []

                while len(records_by_index[index][array_name]) <= array_index:
                    records_by_index[index][array_name].append(None)

                records_by_index[index][array_name][array_index] = array_value
            else:
                field, value = rest.split('=', 1)
                records_by_index[index][field] = value

    cards = []
    for idx in sorted(records_by_index.keys()):
        card = records_by_index[idx]

        if 'RecNo' in card:
            card['RecNo'] = int(card['RecNo'])
        if 'UserID' in card:
            card['UserID'] = int(card['UserID'])
        if 'CardStatus' in card:
            card['CardStatus'] = int(card['CardStatus'])
        if 'CardType' in card:
            card['CardType'] = int(card['CardType'])
        if 'UserType' in card:
            card['UserType'] = int(card['UserType'])
        if 'UseTime' in card:
            card['UseTime'] = int(card['UseTime'])
        if 'RepeatEnterRouteTimeout' in card:
            try:
                card['RepeatEnterRouteTimeout'] = int(card['RepeatEnterRouteTimeout'])
            except ValueError:
                pass

        for bool_field in ['Handicap', 'FirstEnter', 'IsValid']:
            if bool_field in card:
                card[bool_field] = card[bool_field].lower() == 'true'

        for array_field in ['Doors', 'TimeSections']:
            if array_field in card and isinstance(card[array_field], list):
                filtered = []
                for val in card[array_field]:
                    if val is not None:
                        try:
                            filtered.append(int(val))
                        except ValueError:
                            filtered.append(val)
                card[array_field] = filtered

        cards.append(card)

    return cards


@app.route('/health', methods=['GET'])
def health_check():
    device_status = {
        device.id: check_device_reachable(device)
        for device in sorted(DEVICES.values(), key=lambda d: int(d.id))
    }
    overall = 'ok' if all(status == 'ok' for status in device_status.values()) else 'degraded'

    return jsonify({
        'status': overall,
        'timestamp': datetime.now().isoformat(),
        'devices': device_status,
    })


if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '8080'))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    logger.info('Запуск сервера на %s:%s (debug=%s)', host, port, debug)
    app.run(host=host, port=port, debug=debug)
