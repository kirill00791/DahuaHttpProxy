# Dahua HTTP Proxy

HTTP-прокси на Flask для работы со считывателями Dahua в системах контроля и управления доступом (СКУД) через REST API.

Проверено со считывателем **DHI-ASI2201H-DW**; совместимость с другими моделями не подтверждена.

## Функциональность

- Список настроенных считывателей (`GET /api/devices`)
- Получение записей проходов (`POST /api/devices/{id}/get_open_door_records`)
- Удалённое открытие замка (`POST /api/devices/{id}/open_door`)
- Удалённое закрытие замка (`POST /api/devices/{id}/close_door`)
- Статус двери / замка (`GET /api/devices/{id}/get_door_status`, `GET /api/devices/{id}/get_lock_status`)
- Список карт доступа (`GET /api/devices/{id}/get_user_cards`, фильтры `card_no` / `user_id`)
- Добавление карты (`POST /api/devices/{id}/add_user_card`)
- Обновление карты (`POST /api/devices/{id}/update_user_card`)
- Удаление карты (`POST /api/devices/{id}/remove_user_card`)
- Health check с проверкой доступности считывателей (`GET /health`)

Каждый считыватель имеет свой числовой ID (`1`, `2`, `3`, …) и независимую базу карт.

## Требования

- Python 3.8+
- Зависимости: см. `requirements.txt`

## Установка

1. Клонируйте репозиторий и перейдите в каталог проекта.

2. Создайте виртуальное окружение и установите зависимости:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Настройте переменные окружения — один файл `.env` в **корне** репозитория:
   ```bash
   copy .env.example .env
   ```
   Отредактируйте `.env`: для каждого считывателя укажите `DAHUA_DEVICE_{id}_URL`, `_USER`, `_PASS`.

### Формат конфигурации считывателей

```env
DAHUA_DEVICE_1_URL=http://192.168.1.100
DAHUA_DEVICE_1_USER=your_username
DAHUA_DEVICE_1_PASS=your_password

DAHUA_DEVICE_2_URL=http://192.168.1.101
DAHUA_DEVICE_2_USER=your_username
DAHUA_DEVICE_2_PASS=another_password
```

Чтобы добавить 3-й считыватель — допишите блок `DAHUA_DEVICE_3_*` и перезапустите сервер.

## Запуск

```bash
python DahuaHttpProxy/DahuaHttpProxy.py
```

Сервер по умолчанию: `http://localhost:8080`.

### Продакшен (Waitress)

```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=8080 DahuaHttpProxy.DahuaHttpProxy:app
```

## Docker

Образ собирается из [`Dockerfile`](Dockerfile). Файл `.env` **не попадает** в образ (см. [`.dockerignore`](.dockerignore)) — учётные данные и адреса считывателей передаются при запуске контейнера.

### Сборка

```bash
docker build -t dahua-http-proxy .
```

### Запуск

Подготовьте `.env` в корне репозитория (см. [`.env.example`](.env.example)) и передайте его в контейнер:

```bash
docker run -d --name dahua-proxy -p 6001:6001 --env-file .env dahua-http-proxy
```

Сервис будет доступен на `http://localhost:6001` (в образе по умолчанию `FLASK_PORT=6001`).

Проверка:

```bash
curl http://localhost:6001/health
curl http://localhost:6001/api/devices
```

### Остановка и перезапуск

```bash
docker stop dahua-proxy
docker rm dahua-proxy
```

После изменения `.env` (новый считыватель, другой пароль) пересоздайте контейнер с тем же `--env-file` — пересборка образа не нужна.

### Сеть

Контейнер должен иметь доступ к IP считывателей в локальной сети. Если из контейнера считыватели недоступны, а с хоста доступны — проверьте сетевые настройки Docker (на Windows иногда помогает запуск на хосте или настройка маршрутизации в LAN).

### Переменные окружения в контейнере

Минимально необходимы блоки `DAHUA_DEVICE_{id}_URL`, `_USER`, `_PASS` для каждого считывателя. Опционально:

| Переменная | По умолчанию в образе | Описание |
|------------|----------------------|----------|
| `FLASK_HOST` | `0.0.0.0` | Адрес привязки |
| `FLASK_PORT` | `6001` | Порт внутри контейнера |
| `FLASK_DEBUG` | `False` | Режим отладки Flask |

Пример переопределения порта:

```bash
docker run -d --name dahua-proxy -p 8080:8080 --env-file .env -e FLASK_PORT=8080 dahua-http-proxy
```


Базовый префикс для операций со считывателем: `/api/devices/{deviceId}/`, где `deviceId` — число из конфига (`1`, `2`, …).

### Список считывателей

**`GET /api/devices`**

```json
{
  "devices": [
    {"id": "1", "url": "http://192.168.1.100", "username": "your_username"},
    {"id": "2", "url": "http://192.168.1.101", "username": "your_username"}
  ]
}
```

### Health check

**`GET /health`**

```json
{
  "status": "ok",
  "timestamp": "2026-06-24T12:00:00.000000",
  "devices": {"1": "ok", "2": "unreachable"}
}
```

`status` — `ok`, если все считыватели доступны; иначе `degraded`.

### Записи проходов

**`POST /api/devices/1/get_open_door_records`**

```json
{
  "startTime": "2026-03-01 00:00:00",
  "endTime": "2026-03-30 23:59:59",
  "cardNo": "AABBCCDD"
}
```

`startTime`, `endTime` — обязательны; `cardNo` — опционален.

### Открытие / закрытие замка

**`POST /api/devices/1/open_door`**

**`POST /api/devices/1/close_door`**

```json
{
  "channel": 1,
  "user_id": "101"
}
```

`channel` — номер канала двери на считывателе (по умолчанию `1`). `user_id` — опционален (для журнала на считывателе).

Тело запроса можно опустить — тогда откроется/закроется канал `1`.

### Статус двери / замка

**`GET /api/devices/1/get_door_status?channel=1`**

**`GET /api/devices/1/get_lock_status?channel=1`**

`channel` опционален, по умолчанию `1`.

### Список карт

**`GET /api/devices/1/get_user_cards`**

Опциональные query-параметры: `card_no`, `user_id`.

```json
{
  "success": true,
  "count": 2,
  "cards": [...],
  "filters": {"card_no": null, "user_id": null}
}
```

При ошибке связи или ответа считывателя (таймаут, недоступность и т.п.) — не пустой список, а явный отказ:

```json
{
  "success": false,
  "error": "Не удалось получить список карт со считывателя",
  "details": "..."
}
```

Коды: `504` — таймаут, `502` — ошибка связи/ответа считывателя, `500` — внутренняя ошибка прокси.

### Добавление карты

**`POST /api/devices/1/add_user_card`**

```json
{
  "card_name": "Test User",
  "card_no": "AABBCCDD",
  "user_id": "5",
  "doors": [1],
  "time_sections": [1],
  "valid_date_start": "2026-01-01",
  "valid_date_end": "2026-12-31",
  "is_valid": true,
  "user_type": 0,
  "first_enter": false,
  "use_time": 0
}
```

Обязательные поля: `card_name`, `card_no`, `user_id`. Остальное опционально.

Даты `valid_date_*` принимаются как `YYYY-MM-DD`, `YYYY-MM-DD HH:MM:SS` или `yyyyMMdd HHMMSS` и нормализуются в формат устройства. Для даты без времени конец периода = `23:59:59`.

Для прохода по карте отдельного поля «доверенный» нет. Достаточно карты с `is_valid: true`, `card_status: 0` и `doors` с номером нужной двери (например `[1]`). Без `doors` часть прошивок не даёт доступ к замку.

### Обновление карты

**`POST /api/devices/1/update_user_card`**

```json
{
  "card_no": "AABBCCDD",
  "is_valid": false,
  "card_status": 4,
  "doors": [1],
  "valid_date_end": "2026-12-31"
}
```

`card_no` обязателен (поиск записи). Остальные поля опциональны — нужно передать хотя бы одно для изменения. Смена самого номера карты — через `remove` + `add`.

### Удаление карты

**`POST /api/devices/1/remove_user_card`**

```json
{
  "card_no": "AABBCCDD"
}
```

Подробные примеры для Postman — в [`POSTMAN_EXAMPLE.md`](POSTMAN_EXAMPLE.md).

## Безопасность

Сервис **не имеет аутентификации** — любой, кто может достучаться до порта, может читать и изменять карты доступа, а также вызывать `open_door` / `close_door` (физическое управление замком).

Рекомендации:

- Запускайте только в доверенной закрытой сети. Не выставляйте порт в интернет.
- При публикации наружу ставьте reverse proxy с аутентификацией (nginx, Traefik и т.п.).
- `GET /api/devices` возвращает внутренние URL и логины считывателей — не публикуйте этот endpoint наружу.
- Учётные данные считывателей храните только в `.env` (файл в `.gitignore`).

## Зависимости

- `Flask` — веб-фреймворк
- `pydahua` — клиент API Dahua
- `python-dotenv` — загрузка `.env`
- `requests` — HTTP-запросы к считывателю

## Лицензия

[MIT](LICENSE)
