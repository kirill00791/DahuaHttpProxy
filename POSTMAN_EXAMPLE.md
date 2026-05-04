# Примеры запросов для Postman

## Базовый URL
После запуска сервера (по умолчанию на порту 8080):
```
http://localhost:8080
```

**Важно:** Сервер работает по HTTP, не HTTPS. Убедитесь, что в Postman вы используете `http://`, иначе будут ошибки соединения.

## 1. Health check (проверка работоспособности)
**Метод:** GET  
**Эндпоинт:** `/health`  
**Заголовки:** не требуются

**Пример запроса:**
```
GET http://localhost:8080/health
```

**Ожидаемый ответ (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2026-04-29T06:25:00.123456"
}
```

## 2. Получение записей об открытии дверей
**Метод:** POST  
**Эндпоинт:** `/api/getOpenDoorRecords`  
**Заголовки:**
- `Content-Type: application/json`

**Тело запроса (JSON):**
```json
{
  "startTime": "2026-03-01 00:00:00",
  "endTime": "2026-03-30 23:59:59",
  "cardNo": "123456"
}
```

**Параметры:**
- `startTime` (обязательный) – начальная дата и время в формате `"YYYY-MM-DD HH:MM:SS"`
- `endTime` (обязательный) – конечная дата и время в том же формате
- `cardNo` (опциональный) – номер карты для фильтрации. Если не нужен, можно опустить поле или передать `null`.

**Пример запроса в Postman:**
1. Выберите метод **POST**.
2. Введите URL: `http://localhost:8080/api/getOpenDoorRecords`
3. На вкладке **Headers** добавьте ключ `Content-Type` со значением `application/json`.
4. На вкладке **Body** выберите **raw** и тип **JSON**, вставьте JSON из примера выше.

**Успешный ответ (200 OK):**
```json
{
    "found": "2",
    "records": [
        {
            "attendance_state": "0",
            "card_name": "",
            "card_no": "0087D4B7",
            "card_type": "0",
            "create_time": "Tue, 28 Apr 2026 07:51:01 GMT",
            "door": "0",
            "error_code": "16",
            "face_index": "0",
            "hat_color": "",
            "hat_type": "0",
            "method": "1",
            "notes": "",
            "password": "",
            "reader_id": "1",
            "rec_no": "15",
            "remaining_times": "0",
            "reserved_int": "0",
            "reserved_string": "",
            "room_number": "",
            "status": "0",
            "type": "Entry",
            "url": "",
            "user_id": "",
            "user_type": "0"
        },
        {
            "attendance_state": "0",
            "card_name": "",
            "card_no": "000D3453",
            "card_type": "0",
            "create_time": "Tue, 28 Apr 2026 07:57:28 GMT",
            "door": "0",
            "error_code": "16",
            "face_index": "0",
            "hat_type": "0",
            "method": "1",
            "notes": "",
            "password": "",
            "reader_id": "1",
            "rec_no": "16",
            "remaining_times": "0",
            "reserved_int": "0",
            "reserved_string": "",
            "room_number": "",
            "status": "0",
            "type": "Entry",
            "url": "",
            "user_id": "",
            "user_type": "0"
        }
    ],
    "status_code": 200
}
```

**Возможные ошибки:**

| Код | Тело ответа | Причина |
|-----|-------------|---------|
| 400 | `{"error": "Content-Type должен быть application/json"}` | Заголовок `Content-Type` отсутствует или неверный |
| 400 | `{"error": "Пустое тело запроса"}` | Тело запроса пустое или не JSON |
| 400 | `{"error": "Отсутствует обязательное поле: startTime"}` | Не указано обязательное поле |
| 400 | `{"error": "Неверный формат времени. Используйте YYYY-MM-DD HH:MM:SS"}` | Некорректный формат даты/времени |
| 500 | `{"error": "Внутренняя ошибка сервера при обращении к устройству Dahua"}` | Проблемы с подключением к устройству Dahua или ошибка библиотеки |

## 3. Пример запроса без cardNo
```json
{
  "startTime": "2026-03-01 00:00:00",
  "endTime": "2026-03-30 23:59:59"
}
```

## 4. Пример запроса с конкретным временным диапазоном (один день)
```json
{
  "startTime": "2026-03-15 00:00:00",
  "endTime": "2026-03-15 23:59:59",
  "cardNo": "987654"
}
```

## 5. Экспорт коллекции Postman
Вы можете импортировать следующую коллекцию в Postman:

```json
{
  "info": {
    "name": "Dahua HTTP Proxy",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "http://localhost:8080/health",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8080",
          "path": ["health"]
        }
      }
    },
    {
      "name": "Get Open Door Records",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"startTime\": \"2026-03-01 00:00:00\",\n  \"endTime\": \"2026-03-30 23:59:59\",\n  \"cardNo\": \"123456\"\n}"
        },
        "url": {
          "raw": "http://localhost:8080/api/getOpenDoorRecords",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8080",
          "path": ["api", "getOpenDoorRecords"]
        }
      }
    }
  ]
}
```

Скопируйте этот JSON, в Postman нажмите **Import** и вставьте его.

## Примечания
- Убедитесь, что сервер запущен (`python DahuaHttpProxy/DahuaHttpProxy.py`).
- Если вы изменили порт в `.env` (переменная `FLASK_PORT`), замените `8080` на ваш порт.
- Если сервер работает на удалённом хосте, замените `localhost` на соответствующий IP-адрес.