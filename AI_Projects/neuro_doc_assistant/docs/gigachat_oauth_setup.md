# Настройка OAuth 2.0 аутентификации для GigaChat API

## Обзор

GigaChat API использует OAuth 2.0 для аутентификации. Это означает, что вместо прямого API ключа используется схема получения access token через OAuth endpoint.

## Шаг 1: Получение Client ID и Client Secret

1. Перейдите в личный кабинет GigaChat: https://developers.sber.ru/portal/products/gigachat
2. Зарегистрируйте приложение и получите:
   - **Client ID**
   - **Client Secret**

## Шаг 2: Создание Authorization Key

Authorization Key - это Base64 encoded строка в формате `Client ID:Client Secret`.

### Пример создания (Python):

```python
import base64

client_id = "ваш_client_id"
client_secret = "ваш_client_secret"

# Формируем строку "Client ID:Client Secret"
auth_string = f"{client_id}:{client_secret}"

# Кодируем в Base64
auth_key = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

print(f"GIGACHAT_AUTH_KEY={auth_key}")
```

### Пример создания (командная строка):

**Windows (PowerShell):**
```powershell
$clientId = "ваш_client_id"
$clientSecret = "ваш_client_secret"
$authString = "$clientId`:$clientSecret"
$bytes = [System.Text.Encoding]::UTF8.GetBytes($authString)
$authKey = [Convert]::ToBase64String($bytes)
Write-Host "GIGACHAT_AUTH_KEY=$authKey"
```

**Linux/Mac:**
```bash
echo -n "ваш_client_id:ваш_client_secret" | base64
```

## Шаг 3: Выбор Scope

GigaChat API поддерживает три типа scope:

- **GIGACHAT_API_PERS** - для физических лиц (по умолчанию)
- **GIGACHAT_API_B2B** - для ИП и юридических лиц по платным пакетам
- **GIGACHAT_API_CORP** - для ИП и юридических лиц по схеме pay-as-you-go

## Шаг 4: Настройка .env файла

Добавьте в ваш `.env` файл:

```env
# GigaChat OAuth 2.0
GIGACHAT_AUTH_KEY=ваш_base64_encoded_auth_key
GIGACHAT_SCOPE=GIGACHAT_API_PERS

# Опционально: для работы без интернета
GIGACHAT_MOCK_MODE=false
```

## Шаг 5: Проверка подключения

После настройки перезапустите FastAPI сервер и проверьте статус в UI:

1. Откройте Streamlit UI
2. В sidebar проверьте секцию "Статус сервисов"
3. Должен отображаться статус GigaChat API

## Официальные Endpoints

- **OAuth Token:** `https://ngw.devices.sberbank.ru:9443/api/v2/oauth`
- **Chat Completions:** `https://gigachat.devices.sberbank.ru/api/v1/chat/completions`
- **Embeddings:** `https://gigachat.devices.sberbank.ru/api/v1/embeddings`

## Важные замечания

1. **SSL сертификаты:** GigaChat API использует самоподписанные SSL сертификаты, поэтому проверка SSL отключена в коде.

2. **Токен кэширование:** Access token кэшируется и автоматически обновляется перед истечением (действителен 30 минут).

3. **Mock Mode:** Если `GIGACHAT_AUTH_KEY` не установлен или `GIGACHAT_MOCK_MODE=true`, система автоматически использует mock mode для работы без интернета.

4. **Обратная совместимость:** Старый параметр `GIGACHAT_API_KEY` всё ещё поддерживается, но рекомендуется использовать `GIGACHAT_AUTH_KEY` для OAuth 2.0.

## Устранение проблем

### Ошибка: "Не удалось получить access token"

**Причины:**
- Неверный `GIGACHAT_AUTH_KEY` (неправильно закодирован Base64)
- Неверный `GIGACHAT_SCOPE`
- Проблемы с интернет-соединением

**Решение:**
1. Проверьте правильность Base64 кодирования
2. Убедитесь, что scope соответствует вашему типу аккаунта
3. Проверьте интернет-соединение

### Ошибка: "DNS resolution failed"

**Причина:** Нет интернета или проблемы с DNS

**Решение:**
- Используйте mock mode: `GIGACHAT_MOCK_MODE=true`
- Или настройте интернет-соединение

## Пример использования

После настройки система автоматически:

1. Получает access token через OAuth 2.0 при первом запросе
2. Кэширует токен на 30 минут
3. Автоматически обновляет токен перед истечением
4. Использует токен для всех API запросов (chat completions и embeddings)

