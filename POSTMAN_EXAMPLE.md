# Примеры запросов для Postman

## Базовый URL

```
http://localhost:8080
```

Сервер работает по HTTP. В Postman используйте `http://`, не `https://`.

`deviceId` в URL — числовой ID считывателя из `.env` (`1`, `2`, …).

---

## 1. Health check

**GET** `/health`

```
GET http://localhost:8080/health
```

**Ответ (200):**
```json
{
  "status": "ok",
  "timestamp": "2026-06-24T12:00:00.000000",
  "devices": {
    "1": "ok",
    "2": "ok"
  }
}
```

---

## 2. Список считывателей

**GET** `/api/devices`

```
GET http://localhost:8080/api/devices
```

**Ответ (200):**
```json
{
  "devices": [
    {"id": "1", "url": "http://192.168.1.100", "username": "your_username"},
    {"id": "2", "url": "http://192.168.1.101", "username": "your_username"}
  ]
}
```

---

## 3. Записи проходов

**POST** `/api/devices/{deviceId}/get_open_door_records`

**Заголовки:** `Content-Type: application/json`

**Тело:**
```json
{
  "startTime": "2026-03-01 00:00:00",
  "endTime": "2026-03-30 23:59:59",
  "cardNo": "DEADBEEF"
}
```

**Пример:**
```
POST http://localhost:8080/api/devices/1/get_open_door_records
```

Для второго считывателя замените `1` на `2`.

**Без фильтра по карте:**
```json
{
  "startTime": "2026-03-01 00:00:00",
  "endTime": "2026-03-30 23:59:59"
}
```

**Успешный ответ (200):**
```json
{
  "found": "2",
  "records": [
    {
      "card_no": "DEADBEEF",
      "create_time": "Tue, 28 Apr 2026 07:51:01 GMT",
      "door": "0",
      "reader_id": "1",
      "type": "Entry"
    }
  ],
  "status_code": 200
}
```

**Ошибки:**

| Код | Причина |
|-----|---------|
| 400 | Нет JSON, пустое тело, неверный формат времени |
| 404 | Неизвестный `deviceId` |
| 502 / 504 / 500 | Ошибка связи со считывателем Dahua |

---

## 4. Открытие / закрытие замка

**POST** `/api/devices/{deviceId}/open_door`

**POST** `/api/devices/{deviceId}/close_door`

**Заголовки:** `Content-Type: application/json` (если передаёте тело)

**Тело (опционально):**
```json
{
  "channel": 1,
  "user_id": "101"
}
```

**Пример:**
```
POST http://localhost:8080/api/devices/1/open_door
POST http://localhost:8080/api/devices/1/close_door
```

`channel` по умолчанию `1`. `user_id` опционален.

**Успешный ответ (200):**
```json
{
  "success": true,
  "action": "openDoor",
  "channel": 1,
  "device_response": "OK"
}
```

**Ошибки:**

| Код | Причина |
|-----|---------|
| 400 | Неверный JSON или `channel` |
| 404 | Неизвестный `deviceId` |
| 502 / 504 / 500 | Ошибка связи со считывателем Dahua |

---

## 5. Статус двери / замка

**GET** `/api/devices/{deviceId}/get_door_status?channel=1`

**GET** `/api/devices/{deviceId}/get_lock_status?channel=1`

```
GET http://localhost:8080/api/devices/1/get_door_status?channel=1
GET http://localhost:8080/api/devices/1/get_lock_status?channel=1
```

`channel` опционален, по умолчанию `1`.

**Ответ door (200):**
```json
{
  "success": true,
  "action": "getDoorStatus",
  "channel": 1,
  "status": "Close",
  "raw": {"Info.status": "Close"}
}
```

**Ответ lock (200):**
```json
{
  "success": true,
  "action": "getLockStatus",
  "channel": 1,
  "status": "Close",
  "online_status": "Online",
  "raw": {"status": "Close", "onLineStatus": "Online"}
}
```

---

## 6. Список карт доступа

**GET** `/api/devices/{deviceId}/get_user_cards`

```
GET http://localhost:8080/api/devices/1/get_user_cards
GET http://localhost:8080/api/devices/1/get_user_cards?card_no=AABBCCDD
GET http://localhost:8080/api/devices/1/get_user_cards?user_id=1001
```

Опциональные query: `card_no`, `user_id`.

**Ответ (200):**
```json
{
  "success": true,
  "count": 2,
  "filters": {"card_no": null, "user_id": null},
  "cards": [
    {
      "CardName": "Test User",
      "CardNo": "AABBCCDD",
      "UserID": 1,
      "RecNo": 1,
      "Doors": [0],
      "IsValid": false
    }
  ]
}
```

**Ошибка связи со считывателем (например 504):**
```json
{
  "success": false,
  "error": "Таймаут при получении списка карт со считывателя",
  "details": "HTTPConnectionPool(host='192.168.1.100', port=80): Read timed out. (read timeout=10)"
}
```

| Код | Причина |
|-----|---------|
| 404 | Неизвестный `deviceId` |
| 502 | Ошибка связи или некорректный ответ считывателя |
| 504 | Таймаут |
| 500 | Внутренняя ошибка прокси |

---

## 7. Добавление карты

**POST** `/api/devices/{deviceId}/add_user_card`

**Заголовки:** `Content-Type: application/json`

**Тело:**
```json
{
  "card_name": "Test User",
  "card_no": "AABBCCDD",
  "user_id": "1001",
  "card_status": 0,
  "card_type": 0,
  "password": "",
  "doors": [1],
  "time_sections": [1],
  "vto_position": "",
  "valid_date_start": "2026-01-01",
  "valid_date_end": "2026-12-31",
  "is_valid": true,
  "user_type": 0,
  "first_enter": false,
  "use_time": 0
}
```

**Пример:**
```
POST http://localhost:8080/api/devices/1/add_user_card
```

Обязательные поля: `card_name`, `card_no`, `user_id`. Остальное опционально.

`card_no` — 8-символьный HEX RFID (например `AABBCCDD`).

Даты `valid_date_*`: `YYYY-MM-DD`, `YYYY-MM-DD HH:MM:SS` или `yyyyMMdd HHMMSS`.

Для прохода по карте нужны `is_valid: true`, `card_status: 0` и `doors` с номером двери — отдельного поля «доверенный» нет.

**Успешный ответ (200):**
```json
{
  "RecNo": "9",
  "status_code": 200
}
```

---

## 8. Обновление карты

**POST** `/api/devices/{deviceId}/update_user_card`

**Заголовки:** `Content-Type: application/json`

**Тело:**
```json
{
  "card_no": "AABBCCDD",
  "is_valid": false,
  "card_status": 4,
  "doors": [1],
  "valid_date_end": "2026-12-31"
}
```

**Пример:**
```
POST http://localhost:8080/api/devices/1/update_user_card
```

`card_no` обязателен. Нужно хотя бы одно поле для изменения. Смена номера карты — через remove + add.

**Успешный ответ (200):**
```json
{
  "success": true,
  "message": "Card AABBCCDD (RecNo=5) updated successfully",
  "recno": "5",
  "device_response": "OK"
}
```

---

## 9. Удаление карты

**POST** `/api/devices/{deviceId}/remove_user_card`

**Заголовки:** `Content-Type: application/json`

**Тело:**
```json
{
  "card_no": "AABBCCDD"
}
```

**Пример:**
```
POST http://localhost:8080/api/devices/1/remove_user_card
```

**Успешный ответ (200):**
```json
{
  "success": true,
  "message": "Card AABBCCDD (RecNo=5) deleted successfully",
  "recno": "5"
}
```

---

## 10. Импорт коллекции Postman (минимальный набор)

```json
{
  "info": {
    "name": "Dahua HTTP Proxy",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Health",
      "request": {
        "method": "GET",
        "url": "http://localhost:8080/health"
      }
    },
    {
      "name": "List Devices",
      "request": {
        "method": "GET",
        "url": "http://localhost:8080/api/devices"
      }
    },
    {
      "name": "Get Open Door Records (device 1)",
      "request": {
        "method": "POST",
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": {
          "mode": "raw",
          "raw": "{\"startTime\": \"2026-03-01 00:00:00\", \"endTime\": \"2026-03-30 23:59:59\"}"
        },
        "url": "http://localhost:8080/api/devices/1/get_open_door_records"
      }
    },
    {
      "name": "Open Door (device 1)",
      "request": {
        "method": "POST",
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": {
          "mode": "raw",
          "raw": "{\"channel\": 1}"
        },
        "url": "http://localhost:8080/api/devices/1/open_door"
      }
    },
    {
      "name": "Close Door (device 1)",
      "request": {
        "method": "POST",
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": {
          "mode": "raw",
          "raw": "{\"channel\": 1}"
        },
        "url": "http://localhost:8080/api/devices/1/close_door"
      }
    },
    {
      "name": "Get Door Status (device 1)",
      "request": {
        "method": "GET",
        "url": "http://localhost:8080/api/devices/1/get_door_status?channel=1"
      }
    },
    {
      "name": "Get Lock Status (device 1)",
      "request": {
        "method": "GET",
        "url": "http://localhost:8080/api/devices/1/get_lock_status?channel=1"
      }
    },
    {
      "name": "Get User Cards (device 1)",
      "request": {
        "method": "GET",
        "url": "http://localhost:8080/api/devices/1/get_user_cards"
      }
    },
    {
      "name": "Get User Cards by card_no (device 1)",
      "request": {
        "method": "GET",
        "url": "http://localhost:8080/api/devices/1/get_user_cards?card_no=AABBCCDD"
      }
    },
    {
      "name": "Add User Card (device 1)",
      "request": {
        "method": "POST",
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": {
          "mode": "raw",
          "raw": "{\"card_name\": \"Test User\", \"card_no\": \"AABBCCDD\", \"user_id\": \"1001\"}"
        },
        "url": "http://localhost:8080/api/devices/1/add_user_card"
      }
    },
    {
      "name": "Update User Card (device 1)",
      "request": {
        "method": "POST",
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": {
          "mode": "raw",
          "raw": "{\"card_no\": \"AABBCCDD\", \"is_valid\": false}"
        },
        "url": "http://localhost:8080/api/devices/1/update_user_card"
      }
    },
    {
      "name": "Remove User Card (device 1)",
      "request": {
        "method": "POST",
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": {
          "mode": "raw",
          "raw": "{\"card_no\": \"AABBCCDD\"}"
        },
        "url": "http://localhost:8080/api/devices/1/remove_user_card"
      }
    }
  ]
}
```

Скопируйте JSON → Postman → **Import**.

---

## Примечания

- Порт по умолчанию: `8080` (`FLASK_PORT` в `.env`).
- Карты независимы на каждом считывателе — указывайте нужный `deviceId` в URL.
- Новый считыватель: добавьте `DAHUA_DEVICE_N_URL/USER/PASS` в `.env` в корне проекта и перезапустите сервер.
