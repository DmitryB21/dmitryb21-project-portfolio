# Быстрая настройка GigaChat API

## Шаг 1: Получение Client ID и Client Secret

1. Перейдите на https://developers.sber.ru/portal/products/gigachat
2. Зарегистрируйте приложение
3. Получите **Client ID** и **Client Secret**

## Шаг 2: Автоматическая настройка

Запустите скрипт настройки:

```bash
python scripts/setup_gigachat_auth.py
```

Скрипт попросит ввести:
- Client ID
- Client Secret
- Scope (GIGACHAT_API_PERS, GIGACHAT_API_B2B, GIGACHAT_API_CORP)
- Использовать ли mock mode (обычно `N`)

Скрипт автоматически:
- Сгенерирует Base64 encoded `GIGACHAT_AUTH_KEY`
- Обновит `.env` файл с правильными настройками
- Установит `GIGACHAT_MOCK_MODE=false`

## Шаг 3: Проверка подключения

После настройки проверьте подключение:

```bash
python scripts/test_gigachat_connection.py
```

Скрипт проверит:
- ✅ Получение OAuth токена
- ✅ Вызов Embeddings API

## Шаг 4: Ручная настройка (альтернатива)

Если хотите настроить вручную, отредактируйте `.env` файл:

```env
# Генерация GIGACHAT_AUTH_KEY (Python):
# import base64
# auth_key = base64.b64encode(b"ClientID:ClientSecret").decode('utf-8')

GIGACHAT_AUTH_KEY=ваш_base64_encoded_auth_key
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_MOCK_MODE=false
```

## Возможные проблемы

### Ошибка: "Failed to resolve 'ngw.devices.sberbank.ru'"

**Причина:** Нет доступа к интернету или проблемы с DNS

**Решение:**
1. Проверьте интернет-соединение
2. Проверьте, что домены доступны:
   - `ngw.devices.sberbank.ru:9443` (OAuth)
   - `gigachat.devices.sberbank.ru` (API)
3. Если нет интернета, используйте mock mode: `GIGACHAT_MOCK_MODE=true`

### Ошибка: "404 Not Found" для embeddings

**Причина:** Неправильный endpoint или проблемы с API

**Решение:**
1. Проверьте, что используете актуальные endpoints
2. Убедитесь, что ваш аккаунт имеет доступ к Embeddings API
3. Проверьте правильность Scope (GIGACHAT_API_PERS/B2B/CORP)

### Ошибка: "Не удалось получить access token"

**Причина:** Неправильный GIGACHAT_AUTH_KEY или Scope

**Решение:**
1. Проверьте правильность Base64 кодирования
2. Убедитесь, что формат: `base64(ClientID:ClientSecret)`
3. Проверьте, что Scope соответствует типу вашего аккаунта

## Проверка в UI

После настройки:

1. Запустите FastAPI сервер
2. Откройте Streamlit UI
3. В разделе "Статус сервисов" проверьте статус GigaChat API
4. Должно быть: ✅ GigaChat API доступен

## Дополнительная информация

Подробная документация: `docs/gigachat_oauth_setup.md`

