import os
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

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


def device_not_found_response(device_id: str):
    return jsonify({'error': f'Unknown deviceId: {device_id}'}), 404


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
        return jsonify({'error': 'Content-Type должен быть application/json'}), 400

    data = request.get_json()
    if not data:
        logger.warning('Пустой JSON (device %s)', device_id)
        return jsonify({'error': 'Пустое тело запроса'}), 400

    required_fields = ['startTime', 'endTime']
    for field in required_fields:
        if field not in data:
            logger.warning('Отсутствует поле %s (device %s)', field, device_id)
            return jsonify({'error': f'Отсутствует обязательное поле: {field}'}), 400

    try:
        start_time = datetime.strptime(data['startTime'], '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(data['endTime'], '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        logger.warning('Неверный формат времени (device %s): %s', device_id, e)
        return jsonify({'error': 'Неверный формат времени. Используйте YYYY-MM-DD HH:MM:SS'}), 400

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
    except Exception as e:
        logger.error('get_control_card_rec(device=%s): %s', device_id, e)
        return jsonify({'error': 'Внутренняя ошибка сервера при обращении к устройству Dahua'}), 500


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
            return None, (jsonify({'error': 'Content-Type должен быть application/json'}), 400)
        data = request.get_json(silent=True)
        if data is None:
            return None, (jsonify({'error': 'Пустое или некорректное тело запроса'}), 400)

    channel = data.get('channel', 1)
    try:
        channel = int(channel)
    except (TypeError, ValueError):
        return None, (jsonify({'error': 'channel должен быть целым числом'}), 400)

    if channel < 1:
        return None, (jsonify({'error': 'channel должен быть >= 1'}), 400)

    user_id = data.get('user_id')
    return {'channel': channel, 'user_id': user_id}, None


@app.route('/api/devices/<device_id>/open_door', methods=['POST'])
def open_door(device_id: str):
    parsed, error_response = _parse_door_control_request(device_id)
    if error_response is not None:
        return error_response

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
        return jsonify({
            'error': 'Open door failed',
            'details': body,
            'channel': parsed['channel'],
        }), 500
    except KeyError:
        return device_not_found_response(device_id)
    except Exception as e:
        logger.error('open_door(device=%s): %s', device_id, e, exc_info=True)
        return jsonify({'error': 'Внутренняя ошибка сервера при обращении к устройству Dahua'}), 500


@app.route('/api/devices/<device_id>/close_door', methods=['POST'])
def close_door(device_id: str):
    parsed, error_response = _parse_door_control_request(device_id)
    if error_response is not None:
        return error_response

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
        return jsonify({
            'error': 'Close door failed',
            'details': body,
            'channel': parsed['channel'],
        }), 500
    except KeyError:
        return device_not_found_response(device_id)
    except Exception as e:
        logger.error('close_door(device=%s): %s', device_id, e, exc_info=True)
        return jsonify({'error': 'Внутренняя ошибка сервера при обращении к устройству Dahua'}), 500


@app.route('/api/devices/<device_id>/add_user_card', methods=['POST'])
def enroll_new_user(device_id: str):
    if device_id not in DEVICES:
        return device_not_found_response(device_id)

    if not request.is_json:
        logger.warning('Запрос без JSON (device %s)', device_id)
        return jsonify({'error': 'Content-Type должен быть application/json'}), 400

    data = request.get_json()
    if not data:
        logger.warning('Пустой JSON (device %s)', device_id)
        return jsonify({'error': 'Пустое тело запроса'}), 400

    required_fields = ['card_name', 'card_no', 'user_id']
    for field in required_fields:
        if field not in data:
            logger.warning('Отсутствует поле %s (device %s)', field, device_id)
            return jsonify({'error': f'Отсутствует обязательное поле: {field}'}), 400

    try:
        dahua = get_dahua_client(device_id)
        result = dahua.enroll_new_user(
            card_name=data['card_name'],
            card_no=data['card_no'],
            user_id=data['user_id'],
            card_status=data.get('card_status', 0),
            card_type=data.get('card_type', 0),
            password=data.get('password', ''),
            doors=data.get('doors', None),
            time_sections=data.get('time_sections', None),
            vto_position=data.get('vto_position', ''),
            valid_date_start=data.get('valid_date_start', ''),
            valid_date_end=data.get('valid_date_end', ''),
            is_valid=data.get('is_valid', True),
        )
        logger.info(
            'enroll_new_user(device=%s): зарегистрирован %s',
            device_id, data['card_name'],
        )
        return jsonify(result)
    except KeyError:
        return device_not_found_response(device_id)
    except Exception as e:
        logger.error('enroll_new_user(device=%s): %s', device_id, e)
        return jsonify({'error': 'Внутренняя ошибка сервера при обращении к устройству Dahua'}), 500


@app.route('/api/devices/<device_id>/remove_user_card', methods=['POST'])
def delete_card(device_id: str):
    if device_id not in DEVICES:
        return device_not_found_response(device_id)

    if not request.is_json:
        return jsonify({'error': 'JSON required'}), 400

    data = request.get_json()
    card_no = data.get('card_no')

    if not card_no:
        return jsonify({'error': 'card_no is required'}), 400

    try:
        dahua = get_dahua_client(device_id)
        base_url = dahua.base_url
        auth = get_device_auth(device_id)

        search_url = f"{base_url}recordFinder.cgi"
        search_params = {
            'action': 'find',
            'name': 'AccessControlCard',
            'CardNo': card_no,
        }

        logger.info('Ищем карту %s (device %s)', card_no, device_id)
        search_response = requests.get(
            search_url,
            params=search_params,
            auth=auth,
            timeout=10,
        )

        if search_response.status_code != 200:
            logger.error('Ошибка поиска (device %s): %s', device_id, search_response.text)
            return jsonify({'error': 'Search failed', 'details': search_response.text}), 500

        pattern = rf'CardNo={re.escape(card_no)}\b.*?RecNo=(\d+)'
        match = re.search(pattern, search_response.text, re.DOTALL)

        if not match:
            logger.warning('Карта %s не найдена (device %s)', card_no, device_id)
            return jsonify({'error': f'Card {card_no} not found'}), 404

        recno = match.group(1)
        logger.info('Найден RecNo=%s для карты %s (device %s)', recno, card_no, device_id)

        delete_url = f"{base_url}recordUpdater.cgi"
        delete_params = {
            'action': 'remove',
            'name': 'AccessControlCard',
            'recno': recno,
        }

        logger.info('Удаляем карту (device %s): %s', device_id, delete_params)
        delete_response = requests.get(
            delete_url,
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
        return jsonify({
            'error': 'Deletion failed',
            'details': delete_response.text,
            'recno': recno,
        }), 500

    except KeyError:
        return device_not_found_response(device_id)
    except Exception as e:
        logger.error('Исключение (device %s): %s', device_id, e, exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/devices/<device_id>/get_user_cards', methods=['GET'])
def api_get_all_cards(device_id: str):
    if device_id not in DEVICES:
        return device_not_found_response(device_id)

    try:
        cards = get_user_card_all(device_id)
        return jsonify({
            'success': True,
            'count': len(cards),
            'cards': cards,
        })
    except Exception as e:
        logger.error('Ошибка (device %s): %s', device_id, e)
        return jsonify({'error': str(e)}), 500


def get_user_card_all(device_id: str) -> List[Dict]:
    try:
        dahua = get_dahua_client(device_id)
        base_url = dahua.base_url
        auth = get_device_auth(device_id)

        url = f"{base_url}recordFinder.cgi"
        params = {
            'action': 'find',
            'name': 'AccessControlCard',
        }

        response = requests.get(url, params=params, auth=auth, timeout=10)

        if response.status_code != 200:
            logger.error(
                'Ошибка получения списка карт (device %s): %s',
                device_id, response.text,
            )
            return []

        cards = parse_card_records(response.text)
        logger.info('Получено %s карт (device %s)', len(cards), device_id)
        return cards

    except Exception as e:
        logger.error('Исключение в get_user_card_all (device %s): %s', device_id, e)
        return []


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
