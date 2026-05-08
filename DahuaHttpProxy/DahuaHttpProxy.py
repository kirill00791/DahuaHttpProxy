import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from pydahua import DahuaAPI
from dotenv import load_dotenv
import re
from typing import List, Dict
import requests
from requests.auth import HTTPDigestAuth
from flask import Flask, request, jsonify, json

# Загрузка переменных окружения из .env файла в корне проекта
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Уменьшаем уровень логгирования werkzeug, чтобы скрыть ошибки Bad request version
logging.getLogger('werkzeug').setLevel(logging.CRITICAL)

app = Flask(__name__)

# Конфигурация устройства Dahua из переменных окружения
DAHUA_IP = os.getenv('DAHUA_IP')
DAHUA_USERNAME = os.getenv('DAHUA_USERNAME')
DAHUA_PASSWORD = os.getenv('DAHUA_PASSWORD')

# Проверка наличия обязательных переменных
if not DAHUA_IP or not DAHUA_USERNAME or not DAHUA_PASSWORD:
    logger.error('Переменные окружения DAHUA_IP, DAHUA_USERNAME, DAHUA_PASSWORD не установлены.')
    raise ValueError('Не задана конфигурация устройства Dahua. Укажите переменные окружения в .env файле.')

def get_dahua_client():
    """Создает и возвращает клиент DahuaAPI."""
    try:
        client = DahuaAPI(ip=DAHUA_IP, username=DAHUA_USERNAME, password=DAHUA_PASSWORD)
        logger.info('Клиент Dahua успешно создан')
        return client
    except Exception as e:
        logger.error(f'Ошибка создания клиента Dahua: {e}')
        raise

@app.route('/api/getOpenDoorRecords', methods=['POST'])
def get_open_door_records():
    """
    Ожидает JSON:
    {
        "startTime": "2026-03-01 00:00:00",
        "endTime":   "2026-03-30 23:59:59",
        "cardNo":    "123456"   (опционально)
    }
    """
    # Проверка наличия JSON
    if not request.is_json:
        logger.warning('Запрос без JSON')
        return jsonify({'error': 'Content-Type должен быть application/json'}), 400

    data = request.get_json()
    if not data:
        logger.warning('Пустой JSON')
        return jsonify({'error': 'Пустое тело запроса'}), 400

    # Валидация обязательных полей
    required_fields = ['startTime', 'endTime']
    for field in required_fields:
        if field not in data:
            logger.warning(f'Отсутствует обязательное поле: {field}')
            return jsonify({'error': f'Отсутствует обязательное поле: {field}'}), 400

    try:
        # Парсинг времени
        start_time = datetime.strptime(data['startTime'], '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(data['endTime'], '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        logger.warning(f'Неверный формат времени: {e}')
        return jsonify({'error': 'Неверный формат времени. Используйте YYYY-MM-DD HH:MM:SS'}), 400

    card_no = data.get('cardNo', None)

    try:
        dahua = get_dahua_client()
        logs = dahua.get_control_card_rec(
            card_no=card_no,
            start_time=start_time,
            end_time=end_time
        )
        # logs может быть словарем с полями found, records, status_code
        if isinstance(logs, dict) and 'records' in logs:
            record_count = len(logs['records'])
            found = logs.get('found', record_count)
            logger.info(f'get_control_card_rec(): Успешно получено {record_count} записей (found: {found})')
        else:
            record_count = len(logs) if isinstance(logs, list) else 0
            logger.info(f'get_control_card_rec(): Успешно получено {record_count} записей')
        return jsonify(logs)
    except Exception as e:
        logger.error(f'get_control_card_rec(): Ошибка при получении записей: {e}')
        return jsonify({'error': 'Внутренняя ошибка сервера при обращении к устройству Dahua'}), 500


@app.route('/api/addNewUserCard', methods=['POST'])
def enroll_new_user():
    """
    Ожидает JSON:
    {
        "card_name": "Иван Иванов",
        "card_no": "123456",
        "user_id": "1001",
        "card_status": 0,
        "card_type": 0,
        "password": "",
        "doors": [1, 2],
        "time_sections": [1],
        "vto_position": "",
        "valid_date_start": "2026-01-01",
        "valid_date_end": "2026-12-31",
        "is_valid": true
    }
    Все поля, кроме card_name, card_no, user_id, являются опциональными.
    """
    if not request.is_json:
        logger.warning('Запрос без JSON')
        return jsonify({'error': 'Content-Type должен быть application/json'}), 400

    data = request.get_json()
    if not data:
        logger.warning('Пустой JSON')
        return jsonify({'error': 'Пустое тело запроса'}), 400

    required_fields = ['card_name', 'card_no', 'user_id']
    for field in required_fields:
        if field not in data:
            logger.warning(f'Отсутствует обязательное поле: {field}')
            return jsonify({'error': f'Отсутствует обязательное поле: {field}'}), 400

    try:
        dahua = get_dahua_client()
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
            is_valid=data.get('is_valid', True)
        )
        logger.info(f'enroll_new_user(): Успешно зарегистрирован пользователь {data["card_name"]}')
        return jsonify(result)
    except Exception as e:
        logger.error(f'enroll_new_user(): Ошибка при регистрации пользователя: {e}')
        return jsonify({'error': 'Внутренняя ошибка сервера при обращении к устройству Dahua'}), 500

# =================================================================

@app.route('/api/removeUserCard', methods=['POST'])
def delete_card():
    if not request.is_json:
        return jsonify({'error': 'JSON required'}), 400

    data = request.get_json()
    card_no = data.get('card_no')

    if not card_no:
        return jsonify({'error': 'card_no is required'}), 400

    try:
        dahua = get_dahua_client()
        base_url = dahua.base_url
        auth = HTTPDigestAuth(DAHUA_USERNAME, DAHUA_PASSWORD)

        # Шаг 1: Поиск RecNo
        search_url = f"{base_url}recordFinder.cgi"
        search_params = {
            "action": "find",
            "name": "AccessControlCard",
            "CardNo": card_no
        }
        
        logger.info(f'Ищем карту {card_no}')
        search_response = requests.get(
            search_url, 
            params=search_params, 
            auth=auth, 
            timeout=10
        )
        
        if search_response.status_code != 200:
            logger.error(f'Ошибка поиска: {search_response.text}')
            return jsonify({'error': 'Search failed', 'details': search_response.text}), 500

        # Парсим RecNo
        import re
        # Ищем конкретную запись с картой
        pattern = rf'CardNo={re.escape(card_no)}\b.*?RecNo=(\d+)'
        match = re.search(pattern, search_response.text, re.DOTALL)
        
        if not match:
            logger.warning(f'Карта {card_no} не найдена в ответе')
            return jsonify({'error': f'Card {card_no} not found'}), 404
            
        recno = match.group(1)
        logger.info(f'Найден RecNo={recno} для карты {card_no}')

        # Шаг 2: Удаление по RecNo
        delete_url = f"{base_url}recordUpdater.cgi"
        delete_params = {
            "action": "remove",
            "name": "AccessControlCard",
            "recno": recno
        }
        
        logger.info(f'Удаляем карту с параметрами: {delete_params}')
        delete_response = requests.get(
            delete_url,
            params=delete_params,
            auth=auth,
            timeout=10
        )
        
        logger.info(f'Ответ на удаление: status={delete_response.status_code}, body={delete_response.text}')
        
        if delete_response.status_code == 200 and 'Error' not in delete_response.text:
            logger.info(f'Карта {card_no} успешно удалена')
            return jsonify({
                'success': True,
                'message': f'Card {card_no} (RecNo={recno}) deleted successfully',
                'recno': recno
            })
        else:
            logger.error(f'Ошибка удаления: {delete_response.text}')
            return jsonify({
                'error': 'Deletion failed',
                'details': delete_response.text,
                'recno': recno
            }), 500

    except Exception as e:
        logger.error(f'Исключение: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500

# =================================================================

@app.route('/api/getAllUserCards', methods=['GET'])
def api_get_all_cards():
    """
    GET /api/getAllUserCards
    Возвращает JSON-список всех карт с пользователями.
    """
    try:
        cards = get_user_card_all()
        return jsonify({
            'success': True,
            'count': len(cards),
            'cards': cards
        })
    except Exception as e:
        logger.error(f'Ошибка: {e}')
        return jsonify({'error': str(e)}), 500

def get_user_card_all() -> List[Dict]:
    """
    Получает список всех карт с привязкой к пользователям.
    Возвращает список словарей с полной информацией о каждой карте.
    """
    try:
        dahua = get_dahua_client()
        base_url = dahua.base_url
        auth = HTTPDigestAuth(DAHUA_USERNAME, DAHUA_PASSWORD)
        
        # Запрашиваем все карты
        url = f"{base_url}recordFinder.cgi"
        params = {
            "action": "find",
            "name": "AccessControlCard"
        }
        
        response = requests.get(url, params=params, auth=auth, timeout=10)
        
        if response.status_code != 200:
            logger.error(f'Ошибка получения списка карт: {response.text}')
            return []
        
        # Парсим ответ
        cards = parse_card_records(response.text)
        logger.info(f'Получено {len(cards)} карт')
        return cards
        
    except Exception as e:
        logger.error(f'Исключение в get_user_card_all: {e}')
        return []

def parse_card_records(raw_text: str) -> List[Dict]:
    """
    Парсит сырой ответ от recordFinder.cgi в список словарей.
    """
    # Нормализуем разделители строк: заменяем \r\ на \r\n
    normalized = raw_text.replace('\r\\', '\r\n')
    lines = normalized.strip().split('\r\n')
    
    # Словарь для группировки записей по индексу
    records_by_index = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Пропускаем строку с found
        if line.startswith('found='):
            continue
        
        # Некоторые строки могут содержать лишние символы перед records (например, 'nrecords')
        # Ищем позицию подстроки 'records[' в строке
        records_pos = line.find('records[')
        if records_pos == -1:
            continue
        
        # Обрезаем лишнее перед records
        line = line[records_pos:]
        
        # Ищем паттерн records[индекс].поле=значение
        match = re.match(r'records\[(\d+)\]\.(.+)', line)
        if not match:
            continue
            
        index = int(match.group(1))
        rest = match.group(2)
        
        # Инициализируем запись, если еще нет
        if index not in records_by_index:
            records_by_index[index] = {}
        
        # Обрабатываем поле=значение
        if '=' in rest:
            # Проверяем, является ли поле массивом (например, Doors[0]=0)
            array_match = re.match(r'(\w+)\[(\d+)\]=(.+)', rest)
            if array_match:
                array_name = array_match.group(1)
                array_index = int(array_match.group(2))
                array_value = array_match.group(3)
                
                # Создаем список для массива, если еще нет
                if array_name not in records_by_index[index]:
                    records_by_index[index][array_name] = []
                
                # Увеличиваем список до нужного размера
                while len(records_by_index[index][array_name]) <= array_index:
                    records_by_index[index][array_name].append(None)
                
                records_by_index[index][array_name][array_index] = array_value
            else:
                # Обычное поле
                field, value = rest.split('=', 1)
                records_by_index[index][field] = value
    
    # Преобразуем словарь в список, сортируя по индексу
    cards = []
    for idx in sorted(records_by_index.keys()):
        card = records_by_index[idx]
        
        # Преобразуем типы
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
            except:
                pass
        
        # Преобразуем булевы значения
        for bool_field in ['Handicap', 'FirstEnter', 'IsValid']:
            if bool_field in card:
                card[bool_field] = card[bool_field].lower() == 'true'
        
        # Обрабатываем массивы: преобразуем значения в int и удаляем None
        for array_field in ['Doors', 'TimeSections']:
            if array_field in card and isinstance(card[array_field], list):
                # Фильтруем None и преобразуем в int
                filtered = []
                for val in card[array_field]:
                    if val is not None:
                        try:
                            filtered.append(int(val))
                        except:
                            filtered.append(val)
                card[array_field] = filtered
        
        cards.append(card)
    
    return cards
    
# =================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Эндпоинт для проверки работоспособности сервиса."""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '8080'))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    logger.info(f'Запуск сервера на {host}:{port} (debug={debug})')
    app.run(host=host, port=port, debug=debug)