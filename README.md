# Мониторинг баланса Novofon в Zabbix

Веб-сервис на Flask, который запрашивает баланс аккаунта [Novofon](https://novofon.com) через [Data API](https://novofon.github.io/data_api/) и отдаёт его по HTTP в формате JSON. Используется как прослойка для Zabbix — агент или внешний вызов забирают баланс с эндпоинта `/balance`.

---

## Содержание

1. [Где взять ключи](#1-где-взять-ключи)
2. [Запуск](#2-запуск)
3. [Проверка](#3-проверка)
4. [Прокси](#4-прокси-если-нужен)
5. [Подключение к Zabbix](#5-подключение-к-zabbix)
6. [Диагностика](#6-диагностика)
7. [Структура проекта](#7-структура-проекта)

---

## 1. Где взять ключи

| Параметр | Где найти |
|---|---|
| **API_KEY** | Настройки → Виртуальная АТС → SIP-номера. Номера имеют формат `XXXXXX-100`, где `XXXXXX` — номер учётной записи. Ключ пишется как `appid_XXXXXX` |
| **API_SECRET** | Настройки → Сотрудники → Настройки пользователя → Дополнительные настройки |

---

## 2. Запуск

### 2.1. Структура файлов

```
novofon-balance/
├── app.py
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

### 2.2. Сборка и запуск

```bash
docker compose up -d --build
```

Контейнер поднимается на порту `5000`.

---

## 3. Проверка

```bash
curl -H "Authorization: appid_XXXXXX:ВАШ_API_SECRET" http://localhost:5000/balance
```

Ожидаемый ответ при успехе:

```json
{
  "status": "success",
  "balance": "100.50",
  "currency": "RUB"
}
```

Ответ при ошибке авторизации (HTTP 401):

```json
{
  "error": "Missing or invalid Authorization header. Expected format: API_KEY:API_SECRET"
}
```

Ответ при ошибке Novofon (HTTP 502):

```json
{
  "error": "Novofon API error: <текст ошибки>"
}
```

---

## 4. Прокси (если нужен)

Если Novofon блокирует прямые запросы с вашего IP, раскомментируйте в `docker-compose.yml`:

```yaml
environment:
  - PROXY_URL=socks5h://192.168.1.55:9051
```

и пересоберите:

```bash
docker compose up -d --build
```

---

## 5. Подключение к Zabbix

### Вариант A — UserParameter (Zabbix Agent)

На хосте с Zabbix Agent создайте файл:

**`/etc/zabbix/zabbix_agentd.d/novofon_balance.conf`**

```ini
UserParameter=novofon.balance,/usr/bin/curl -s -H "Authorization: appid_XXXXXX:ВАШ_API_SECRET" http://localhost:5000/balance | /usr/bin/jq -r '.balance'
```

Пакет `jq` должен быть установлен на хосте с агентом. Перезапустите агент:

```bash
systemctl restart zabbix-agent
```

### Вариант B — HTTP Agent (без curl на хосте)

В веб-интерфейсе Zabbix: **Configuration → Hosts → Items → Create item**

| Поле | Значение |
|---|---|
| Name | Баланс Novofon |
| Type | HTTP agent |
| Key | `novofon.balance` |
| URL | `http://localhost:5000/balance` |
| Type of information | Numeric (float) |

**Preprocessing:** добавить шаг → **JSONPath** → `$.balance`

**Headers** (раздел HTTP Agent):

| Name | Value |
|---|---|
| `Authorization` | `appid_XXXXXX:ВАШ_API_SECRET` |

Save → **Test**.

### Триггер

| Поле | Значение |
|---|---|
| Name | Баланс Novofon ниже порога |
| Expression | `last(/Хост/novofon.balance) < 500` |
| Priority | Warning |

Замените `500` на свою пороговую сумму и `Хост` на имя хоста в Zabbix.

---

## 6. Диагностика

### Логи контейнера

```bash
docker logs novofon_balance_novofon-api_1
```

В логах виден полный ответ от Novofon — статус-код и тело. Если приходит 502, ищите строку:

```
Novofon response: status_code=..., body=...
```

### Типичные проблемы

| Симптом | Причина |
|---|---|
| 401 от контейнера | Неверный формат заголовка `Authorization` |
| 502, в логе `status_code=403` | Неверный API_KEY или API_SECRET |
| 502, в логе `status_code=429` | Превышен лимит (100 запросов/мин) |
| 502, в логе timeout | Novofon недоступен или нужен прокси |
| Connection refused | Контейнер не запущен — `docker compose ps` |

---

## 7. Структура проекта

```
novofon-balance/
├── app.py              # Flask-приложение, эндпоинт /balance
├── requirements.txt    # Зависимости (flask, requests, PySocks)
├── Dockerfile          # Образ python:3.12-slim
└── docker-compose.yml  # Конфиг сборки и запуска
```

### Эндпоинты

| Метод | Путь | Описание |
|---|---|---|
| GET | `/balance` | Запрос баланса Novofon (требует заголовок `Authorization`) |
| GET | `/health` | Healthcheck для Docker |
