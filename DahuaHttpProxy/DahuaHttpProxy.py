import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from pydahua import DahuaAPI
from dotenv import load_dotenv

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