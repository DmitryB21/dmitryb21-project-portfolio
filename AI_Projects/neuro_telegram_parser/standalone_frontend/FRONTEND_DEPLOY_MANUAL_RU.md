# Руководство по ручному развертыванию standalone фронтенда

Этот фронт — статический (HTML/CSS/JS). Он обращается к существующему backend по REST `/pro/api/*`.
Исходники фронта находятся в папке `standalone_frontend/` и НЕ затрагивают текущий серверный код.

## 1. Подготовка

1) Убедитесь, что backend доступен и открывает API, например:
   - `GET https://your-backend.example.com/pro/api/stats`
   - `GET https://your-backend.example.com/pro/api/trends?period=daily&limit=5`
   - `GET https://your-backend.example.com/pro/api/search?query=...`

2) На backend включите CORS для путей `/pro/api/*` (если фронт будет открыт с другого домена).

## 2. Настройка адреса API

В файле `standalone_frontend/env.js` укажите адрес backend API (без завершающего слеша):

```js
window.__APP_CONFIG__ = {
  API_BASE_URL: "https://your-backend.example.com"
};
```

## 3. Сборка архива

Вариант A (Linux/macOS):

```bash
cd standalone_frontend/scripts
chmod +x build_frontend.sh
./build_frontend.sh
```

Скрипт создаст архив `standalone_frontend_YYYYMMDD_HHMMSS.tar.gz` в соседней с build папке.

Вариант B (Windows PowerShell):

```powershell
cd standalone_frontend\scripts
.\build_frontend.ps1
```

Скрипт создаст архив `standalone_frontend_YYYYMMDD_HHMMSS.zip`.

## 4. Ручной деплой на сервер (Nginx)

1) Скопируйте архив на сервер, распакуйте, положите в каталог, например `/var/www/standalone_frontend`:

```bash
sudo mkdir -p /var/www/standalone_frontend
sudo tar -xzf standalone_frontend_YYYYMMDD_HHMMSS.tar.gz -C /var/www/
# Или для zip:
# sudo unzip standalone_frontend_YYYYMMDD_HHMMSS.zip -d /var/www/
# Убедитесь, что конечный путь содержит index.html: /var/www/standalone_frontend/index.html
```

2) Примените конфиг Nginx (пример прилагается `standalone_frontend/nginx.conf.example`):

```nginx
server {
    listen 80;
    server_name frontend.example.com;

    root /var/www/standalone_frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }
}
```

Сохраните файл конфига (например, `/etc/nginx/sites-available/standalone_frontend.conf`), создайте ссылку в `sites-enabled`, проверьте конфигурацию и перезапустите Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/standalone_frontend.conf /etc/nginx/sites-enabled/standalone_frontend.conf
sudo nginx -t
sudo systemctl reload nginx
```

3) Откройте в браузере `http://frontend.example.com` и проверьте:
   - Главная (статистика, топ тренды, последние события)
   - Тренды (`/trends.html`)
   - Поиск (`/search.html`)

## 5. Проверка и отладка

- При проблемах с CORS:
  - Проверьте заголовки CORS на backend (разрешённый origin).
  - Проверьте, что фронт обращается к правильному `API_BASE_URL` (см. `env.js`).

- При 404/500:
  - Проверьте доступность backend эндпоинтов напрямую (curl или браузер).
  - Проверьте логи Nginx на frontend и backend.

## 6. Обновление фронта

1) Обновите файлы в `standalone_frontend/` в репозитории.
2) Пересоберите архив скриптом.
3) Скопируйте архив на сервер, распакуйте поверх `/var/www/standalone_frontend` (или в новую версию, затем переключите symlink).
4) Перезагрузите Nginx (обычно не требуется, если не менялся конфиг).

## 7. Структура фронта

```
standalone_frontend/
  index.html            — Главная (статистика, топ-5 трендов, последние события)
  trends.html           — Список трендов с выбором периода
  search.html           — Семантический поиск по сообщениям
  env.js                — Конфигурация API_BASE_URL
  assets/
    css/styles.css      — Минималистичные стили
    js/common.js        — Общие функции (apiGet, escapeHtml, formatNumber)
  scripts/
    build_frontend.sh   — Сборка tar.gz (Linux/macOS)
    build_frontend.ps1  — Сборка zip (Windows)
  nginx.conf.example    — Пример конфига Nginx
```

---

При необходимости можно добавить дополнительные страницы (например, список событий/каналов), скопировав логику вызовов из UI, и заменить относительные пути API на `API_BASE_URL`.


