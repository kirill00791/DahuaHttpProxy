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
  "cardNo": "0087D4B7"
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

## 5. Различие между add_user и enroll_new_user

Методы `add_user` и `enroll_new_user` выполняют разные задачи:

- **`add_user`** – создаёт учётную запись пользователя для доступа к веб-интерфейсу устройства Dahua (администратор или обычный пользователь). Этот пользователь может входить в веб-панель управления устройством, но не имеет карты доступа. Параметры: имя, пароль, группа (admin/user), флаги sharable и reserved.

- **`enroll_new_user`** – регистрирует нового пользователя **системы контроля доступа** (СКУД) с привязкой карты (или другого идентификатора) к определённым дверям, временным интервалам и т.д. Этот пользователь используется для физического прохода через турникет/дверь. Параметры: card_name, card_no, user_id, doors, time_sections и др.

**Проще говоря:**
- `add_user` – для веб-управления устройством.
- `enroll_new_user` – для пропускной системы (карты доступа).

## 6. Добавление пользователя (add_user)
**Метод:** POST
**Эндпоинт:** `/api/add_user`
**Заголовки:**
- `Content-Type: application/json`

**Тело запроса (JSON):**
```json
{
  "username": "user1",
  "password": "pass123",
  "group": "user",
  "sharable": false,
  "reserved": false,
  "memo": "optional note"
}
```

**Параметры:**
- `username` (обязательный) – имя пользователя
- `password` (обязательный) – пароль пользователя
- `group` (обязательный) – группа пользователя: "admin" или "user"
- `sharable` (обязательный) – разрешить многопользовательский вход (true/false)
- `reserved` (обязательный) – зарезервированный пользователь, который не может быть удалён (true/false)
- `memo` (опциональный) – заметка

**Пример запроса в Postman:**
1. Выберите метод **POST**.
2. Введите URL: `http://localhost:8080/api/add_user`
3. На вкладке **Headers** добавьте ключ `Content-Type` со значением `application/json`.
4. На вкладке **Body** выберите **raw** и тип **JSON**, вставьте JSON из примера выше.

**Успешный ответ (200 OK):**
Ответ зависит от устройства Dahua. Пример:
```json
{
  "result": "OK",
  "status_code": 200
}
```

**Возможные ошибки:**
| Код | Тело ответа | Причина |
|-----|-------------|---------|
| 400 | `{"error": "Content-Type должен быть application/json"}` | Неверный заголовок |
| 400 | `{"error": "Пустое тело запроса"}` | Пустой JSON |
| 400 | `{"error": "Отсутствует обязательное поле: username"}` | Не указано обязательное поле |
| 500 | `{"error": "Внутренняя ошибка сервера при обращении к устройству Dahua"}` | Ошибка устройства |

## 7. Получение информации о пользователе (get_user_info)
**Метод:** POST
**Эндпоинт:** `/api/get_user_info`
**Заголовки:**
- `Content-Type: application/json`

**Тело запроса (JSON):**
```json
{
  "username": "user1"
}
```

**Параметры:**
- `username` (обязательный) – имя пользователя

**Пример запроса в Postman:**
1. Выберите метод **POST**.
2. Введите URL: `http://localhost:8080/api/get_user_info`
3. На вкладке **Headers** добавьте ключ `Content-Type` со значением `application/json`.
4. На вкладке **Body** выберите **raw** и тип **JSON**, вставьте JSON из примера выше.

**Успешный ответ (200 OK):**
Ответ содержит информацию о пользователе. Пример:
```json
{
  "Group": "user",
  "Memo": "optional note",
  "Name": "user1",
  "Reserved": "false",
  "Sharable": "false",
  "status_code": 200
}
```

**Возможные ошибки:** аналогично предыдущему эндпоинту.

## 8. Получение информации обо всех пользователях (get_user_info_all)
**Метод:** GET или POST
**Эндпоинт:** `/api/get_user_info_all`
**Заголовки:** не требуются (для GET) или `Content-Type: application/json` (для POST)

**Тело запроса:** не требуется (можно отправить пустой JSON `{}` или ничего)

**Пример запроса в Postman (GET):**
1. Выберите метод **GET**.
2. Введите URL: `http://localhost:8080/api/get_user_info_all`

**Успешный ответ (200 OK):**
Ответ содержит список всех пользователей. Пример:
```json
{
  "UserInfo": [
    {
      "Group": "admin",
      "Memo": "",
      "Name": "admin",
      "Reserved": "true",
      "Sharable": "false"
    },
    {
      "Group": "user",
      "Memo": "optional note",
      "Name": "user1",
      "Reserved": "false",
      "Sharable": "false"
    }
  ],
  "status_code": 200
}
```

## 9. Регистрация нового пользователя с картой доступа (addNewUserCard)
**Метод:** POST
**Эндпоинт:** `/api/addNewUserCard`
**Заголовки:**
- `Content-Type: application/json`

**Тело запроса (JSON):**
```json
{
  "card_name": "Иван Иванов",
  "card_no": "00DF1FD1",
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
```

**Параметры:**
- `card_name` (обязательный) – имя владельца карты (до 32 символов)
- `card_no` (обязательный) – номер карты (!!! уникальный !!!)
- `user_id` (обязательный) – идентификатор пользователя (!!! уникальный !!!)
- `card_status` (опциональный, по умолчанию 0) – статус карты
- `card_type` (опциональный, по умолчанию 0) – тип карты
- `password` (опциональный) – пароль
- `doors` (опциональный) – массив номеров дверей, к которым есть доступ
- `time_sections` (опциональный) – массив номеров временных сегментов
- `vto_position` (опциональный) – позиция VTO
- `valid_date_start` (опциональный) – дата начала действия в формате "YYYY-MM-DD"
- `valid_date_end` (опциональный) – дата окончания действия
- `is_valid` (опциональный, по умолчанию true) – активна ли карта

**Пример запроса в Postman:**
1. Выберите метод **POST**.
2. Введите URL: `http://localhost:8080/api/enroll_new_user`
3. На вкладке **Headers** добавьте ключ `Content-Type` со значением `application/json`.
4. На вкладке **Body** выберите **raw** и тип **JSON**, вставьте JSON из примера выше.

**Успешный ответ (200 OK):**
Ответ зависит от устройства. Пример:
```json
{
    "RecNo": "9",
    "status_code": 200
}
```

**Возможные ошибки:** аналогично предыдущим эндпоинтам.

## 10. Получение информации о группе пользователей (get_group_info)
**Метод:** POST
**Эндпоинт:** `/api/get_group_info`
**Заголовки:**
- `Content-Type: application/json`

**Тело запроса (JSON):**
```json
{
  "name": "admin"
}
```

**Параметры:**
- `name` (обязательный) – название группы

**Пример запроса в Postman:**
1. Выберите метод **POST**.
2. Введите URL: `http://localhost:8080/api/get_group_info`
3. На вкладке **Headers** добавьте ключ `Content-Type` со значением `application/json`.
4. На вкладке **Body** выберите **raw** и тип **JSON**, вставьте JSON из примера выше.

**Успешный ответ (200 OK):**
Ответ содержит информацию о группе. Пример:
```json
{
  "GroupInfo": [
    {
      "Name": "admin",
      "Memo": "",
      "Reserved": "true",
      "Sharable": "false"
    }
  ],
  "status_code": 200
}
```

**Возможные ошибки:** аналогично предыдущим эндпоинтам.

## 11. Получение информации обо всех группах пользователей (get_group_info_all)
**Метод:** GET или POST
**Эндпоинт:** `/api/get_group_info_all`
**Заголовки:** не требуются (для GET) или `Content-Type: application/json` (для POST)

**Тело запроса:** не требуется (можно отправить пустой JSON `{}` или ничего)

**Пример запроса в Postman (GET):**
1. Выберите метод **GET**.
2. Введите URL: `http://localhost:8080/api/get_group_info_all`

**Успешный ответ (200 OK):**
Ответ содержит список всех групп. Пример:
```json
{
  "GroupInfo": [
    {
      "Name": "admin",
      "Memo": "",
      "Reserved": "true",
      "Sharable": "false"
    },
    {
      "Name": "user",
      "Memo": "",
      "Reserved": "false",
      "Sharable": "false"
    }
  ],
  "status_code": 200
}
```

## 12. Удаление пользователя (delete_user)
**Метод:** POST
**Эндпоинт:** `/api/delete_user`
**Заголовки:**
- `Content-Type: application/json`

**Тело запроса (JSON):**
```json
{
  "username": "user1"
}
```

**Параметры:**
- `username` (обязательный) – имя пользователя для удаления (веб-пользователь)

**Пример запроса в Postman:**
1. Выберите метод **POST**.
2. Введите URL: `http://localhost:8080/api/delete_user`
3. На вкладке **Headers** добавьте ключ `Content-Type` со значением `application/json`.
4. На вкладке **Body** выберите **raw** и тип **JSON**, вставьте JSON из примера выше.

**Успешный ответ (200 OK):**
Ответ зависит от устройства. Пример:
```json
{
  "result": "OK",
  "status_code": 200
}
```

**Возможные ошибки:** аналогично предыдущим эндпоинтам.

## 13. Удаление карты доступа (removeUserCard)
**Метод:** POST
**Эндпоинт:** `/api/removeUserCard`
**Заголовки:**
- `Content-Type: application/json`

**Тело запроса (JSON):**
```json
{
  "card_no": "000C3BA7"
}
```

**Параметры:**
- `card_no` (обязательный) – номер карты, которую нужно удалить из системы контроля доступа

**Пример запроса в Postman:**
1. Выберите метод **POST**.
2. Введите URL: `http://localhost:8080/api/removeUserCard`
3. На вкладке **Headers** добавьте ключ `Content-Type` со значением `application/json`.
4. На вкладке **Body** выберите **raw** и тип **JSON**, вставьте JSON из примера выше.

**Успешный ответ (200 OK):**
Ответ зависит от устройства. Пример:
```json
{
  "result": "OK",
  "status_code": 200
}
```

**Примечание:** Этот эндпоинт удаляет запись карты доступа, созданную через `addNewUserCard`.

## 14. Получение списка всех карт доступа (getAllUserCards)
**Метод:** GET
**Эндпоинт:** `/api/getAllUserCards`
**Заголовки:** не требуются

**Пример запроса:**
```
GET http://localhost:8080/api/getAllUserCards
```

**Успешный ответ (200 OK):**
```json
{
    "success": true,
    "count": 7,
    "cards": [
        {
            "UserType": 0,
            "Handicap": false,
            "CardType": 0,
            "CardName": "Иванов И.А.",
            "CardNo": "02908E73",
            "CardStatus": 0,
            "CitizenIDNo": "",
            "Doors": [0],
            "DynamicCheckCode": "",
            "FirstEnter": false,
            "IsValid": false,
            "Password": "26441488",
            "RepeatEnterRouteTimeout": 4294967295,
            "TimeSections": [255],
            "UseTime": 200,
            "UserID": 1,
            "VTOPosition": "",
            "ValidDateStart": "2026-04-27 15:54:08",
            "ValidDateEnd": "2037-12-31 23:59:59",
            "RecNo": 1
        },
        {
            "UserType": 0,
            "Handicap": false,
            "CardType": 0,
            "CardName": "Петров К.С.",
            "CardNo": "0087D4B7",
            "CardStatus": 0,
            "CitizenIDNo": "",
            "Doors": [0],
            "DynamicCheckCode": "",
            "FirstEnter": false,
            "IsValid": false,
            "Password": "",
            "RepeatEnterRouteTimeout": 4294967295,
            "TimeSections": [255],
            "UseTime": 200,
            "UserID": 2,
            "VTOPosition": "",
            "ValidDateStart": "2026-04-28 09:39:18",
            "ValidDateEnd": "2037-12-31 23:59:59",
            "RecNo": 2
        },
        {
            "UserType": 0,
            "Handicap": false,
            "CardType": 0,
            "CardName": "test.user3",
            "CardNo": "123456",
            "CardStatus": 0,
            "CitizenIDNo": "",
            "Doors": [1],
            "DynamicCheckCode": "",
            "FirstEnter": false,
            "IsValid": false,
            "Password": "",
            "RepeatEnterRouteTimeout": 4294967295,
            "TimeSections": [1],
            "UseTime": 0,
            "UserID": 1001,
            "VTOPosition": "",
            "ValidDateStart": "",
            "ValidDateEnd": "",
            "RecNo": 4
        }
    ]
}
```

**Примечания:**
- Ответ содержит массив `cards` с полной информацией о каждой карте доступа.
- Все поля приведены к соответствующим типам: числа (`UserType`, `CardStatus`, `UserID`, `RecNo`, `UseTime`), булевы значения (`Handicap`, `FirstEnter`, `IsValid`), строки (`CardName`, `CardNo`), списки (`Doors`, `TimeSections`).
- Поля `Doors` и `TimeSections` представлены массивами целых чисел. Если массив отсутствует, поле может отсутствовать в ответе.
- Поля `ValidDateStart` и `ValidDateEnd` могут быть пустыми строками для карт без ограничения срока действия.
- Поле `RepeatEnterRouteTimeout` представлено как число (может быть большим, например 4294967295).

## 15. Добавление новой карты доступа (addNewUserCard)
**Метод:** POST
**Эндпоинт:** `/api/addNewUserCard`
**Заголовки:**
- `Content-Type: application/json`

**Тело запроса (JSON):**
```json
{
    "card_name": "Иван Иванов",
    "card_no": "02908E73",
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
```

**Параметры:**
- `card_name` (обязательный) – имя владельца карты (до 32 символов)
- `card_no` (обязательный) – номер карты в виде 8-значной строки с 16-ричным HEX номером прочитанной RFID карты (например, "02908E73", "0087D4B7")
- `user_id` (обязательный) – уникальный идентификатор пользователя (число)
- `card_status` (опциональный, по умолчанию 0) – статус карты
- `card_type` (опциональный, по умолчанию 0) – тип карты
- `password` (опциональный) – пароль для доступа
- `doors` (опциональный) – массив номеров дверей, к которым есть доступ
- `time_sections` (опциональный) – массив номеров временных сегментов
- `vto_position` (опциональный) – позиция VTO
- `valid_date_start` (опциональный) – дата начала действия в формате "YYYY-MM-DD"
- `valid_date_end` (опциональный) – дата окончания действия
- `is_valid` (опциональный, по умолчанию true) – активна ли карта

**Важное замечание о формате card_no:**
Сервер ожидает `card_no` в виде 8-значной строки с 16-ричным HEX номером прочитанной RFID карты. Например, если RFID-ридер выдал номер `02908E73`, именно эту строку нужно передавать. Если номер короче 8 символов, его нужно дополнить ведущими нулями до 8 символов (например, `0A6ABA` → `000A6ABA`).

**Пример запроса в Postman:**
1. Выберите метод **POST**.
2. Введите URL: `http://localhost:8080/api/addNewUserCard`
3. На вкладке **Headers** добавьте ключ `Content-Type` со значением `application/json`.
4. На вкладке **Body** выберите **raw** и тип **JSON**, вставьте JSON из примера выше.

**Успешный ответ (200 OK):**
Ответ зависит от устройства Dahua. Пример:
```json
{
  "result": "OK",
  "status_code": 200
}
```

**Возможные ошибки:**
| Код | Тело ответа | Причина |
|-----|-------------|---------|
| 400 | `{"error": "Content-Type должен быть application/json"}` | Неверный заголовок |
| 400 | `{"error": "Пустое тело запроса"}` | Пустой JSON |
| 400 | `{"error": "Отсутствует обязательное поле: card_name"}` | Не указано обязательное поле |
| 500 | `{"error": "Внутренняя ошибка сервера при обращении к устройству Dahua"}` | Ошибка устройства |

## 16. Экспорт коллекции Postman

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