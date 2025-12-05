# Развертывание приложения на внешнем сервере с Docker

Пошаговая инструкция по развертыванию Telegram Parser на внешнем сервере с использованием Docker.

## 📋 Предварительные требования

1. **Сервер с Docker и Docker Compose:**
   - Ubuntu 20.04+ / Debian 11+ / CentOS 8+
   - Docker 20.10+
   - Docker Compose 2.0+

2. **Минимальные системные требования:**
   - CPU: 4+ ядер
   - RAM: 8+ GB
   - Диск: 50+ GB (для моделей и данных)
   - Сеть: стабильное подключение к интернету
   - **Локальные сервисы (должны быть установлены на том же сервере):**
     - PostgreSQL: `127.0.0.1:5432` (база: `indlab_db`, пользователь: `indlab_user`)
     - Redis: `127.0.0.1:6379` (пароль: `indlab_redis_pass`)
     - Qdrant: `127.0.0.1:6333`

3. **Внешние сервисы:**
   - Telegram API credentials (API ID и API Hash)
   - OpenAI API key (для генерации заголовков)
   - Доменное имя (опционально, для HTTPS)

## 🚀 Шаг 1: Подготовка сервера

### 1.1 Установка Docker и Docker Compose

```bash
# Обновление пакетов
sudo apt-get update

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker --version
docker-compose --version
```

### 1.2 Клонирование проекта

```bash
# Клонирование репозитория
git clone https://github.com/your-username/telegram_parser.git
cd telegram_parser

# Или загрузка проекта через scp/sftp
```

## 🔧 Шаг 2: Настройка переменных окружения

### 2.1 Создание файла .env

Создайте файл `.env` в корне проекта на основе `.env.example`:

```bash
cp .env.example .env
nano .env
```

### 2.2 Заполнение переменных окружения

**⚠️ ВАЖНО:** PostgreSQL, Redis и Qdrant должны быть установлены и запущены на том же сервере, что и приложение.

```env
# Telegram API credentials (ОБЯЗАТЕЛЬНО)
TELEGRAM_API_ID=your_telegram_api_id
TELEGRAM_API_HASH=your_telegram_api_hash
TELEGRAM_PHONE_NUMBER=+1234567890

# PostgreSQL (локальный сервер)
POSTGRES_DSN=postgresql://indlab_user:indlab_pass@127.0.0.1:5432/indlab_db
POSTGRES_CUSTOMER_DSN=postgresql://indlab_user:indlab_pass@127.0.0.1:5432/telegram_data_customer

# Redis (локальный сервер)
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=indlab_redis_pass

# Qdrant (локальный сервер)
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333

# OpenAI API (ОБЯЗАТЕЛЬНО для генерации заголовков)
OPENAI_API_KEY=sk-your-openai-api-key

# JWT и безопасность (ОБЯЗАТЕЛЬНО изменить!)
SECRET_KEY=your_very_strong_secret_key_min_32_chars_change_in_production
DEFAULT_ADMIN_PASSWORD=strong_admin_password_change_me
DEFAULT_ADMIN_EMAIL=admin@yourdomain.com
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

**⚠️ ВАЖНО:** 
- Измените все пароли и секретные ключи!
- Используйте сильные пароли (минимум 32 символа для SECRET_KEY)
- Не коммитьте `.env` файл в Git!

## 📱 Шаг 3: Настройка Telegram сессии

### 3.1 Создание сессии локально (рекомендуется)

**На вашем локальном компьютере:**

```bash
# Активация виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Создание Telegram сессии
python setup_main_session.py
```

После выполнения будет создан файл `telegram_parser.session`.

### 3.2 Копирование сессии на сервер

```bash
# С локального компьютера на сервер
scp telegram_parser.session user@your-server:/path/to/telegram_parser/
```

**⚠️ ВАЖНО:** Файл `telegram_parser.session` содержит ключи аутентификации. Храните его в безопасности!

## 🗄️ Шаг 4: Настройка конфигурации

### 4.1 Настройка config.ini для Docker

Приложение автоматически использует `config.ini.docker` при сборке Docker образа. Этот файл настроен для работы с удаленными сервисами и использует переменные окружения для хостов.

**Важно:** Убедитесь, что в `.env` файле указаны правильные адреса локальных сервисов:
- PostgreSQL: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`
- Qdrant: `127.0.0.1:6333`

Конфигурация `config.ini.docker` автоматически использует переменные окружения:
- `REDIS_HOST`, `REDIS_PORT` для Redis
- `QDRANT_HOST`, `QDRANT_PORT` для Qdrant
- `POSTGRES_DSN` для PostgreSQL

**Примечание:** Все сервисы (PostgreSQL, Redis, Qdrant) должны быть установлены и запущены на том же сервере, что и приложение. Docker контейнеры используют `network_mode: host` для доступа к localhost сервисам.

## 🐳 Шаг 5: Установка и запуск локальных сервисов

### 5.1 Установка PostgreSQL

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Создание базы данных и пользователя
sudo -u postgres psql
CREATE DATABASE indlab_db;
CREATE USER indlab_user WITH PASSWORD 'indlab_pass';
GRANT ALL PRIVILEGES ON DATABASE indlab_db TO indlab_user;
\q

# Настройка доступа (редактировать /etc/postgresql/*/main/pg_hba.conf)
# Добавить: host    all    all    127.0.0.1/32    md5
sudo systemctl restart postgresql
```

### 5.2 Установка Redis

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# Настройка пароля (редактировать /etc/redis/redis.conf)
# requirepass indlab_redis_pass
sudo systemctl restart redis-server
```

### 5.3 Установка Qdrant

```bash
# Использование Docker для Qdrant (рекомендуется)
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant:latest

# Или установка через бинарный файл
# См. https://qdrant.tech/documentation/guides/installation/
```

## 🐳 Шаг 6: Запуск приложения с Docker Compose

### 6.1 Базовый запуск

```bash
# Сборка образов
docker-compose build

# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Проверка статуса
docker-compose ps
```

### 5.2 Production запуск с Nginx

```bash
# Создание директории для SSL сертификатов
mkdir -p nginx/ssl

# Генерация самоподписанного сертификата (для тестирования)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem

# Или использование Let's Encrypt (рекомендуется для production)
# Установите certbot и получите сертификаты

# Запуск с production конфигурацией
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 🔍 Шаг 7: Проверка работы

### 7.1 Проверка локальных сервисов

```bash
# Проверка PostgreSQL
sudo systemctl status postgresql
psql -h 127.0.0.1 -p 5432 -U indlab_user -d indlab_db -c "SELECT 1;"

# Проверка Redis
sudo systemctl status redis-server
redis-cli -h 127.0.0.1 -p 6379 -a indlab_redis_pass ping

# Проверка Qdrant
curl http://127.0.0.1:6333/health
# Или если используется Docker:
docker ps | grep qdrant
```

### 7.2 Проверка приложения

```bash
# Проверка статуса всех контейнеров
docker-compose ps

# Проверка логов
docker-compose logs web
docker-compose logs worker

# Проверка подключения к локальной базе данных PostgreSQL
docker-compose exec web python -c "import asyncpg; import asyncio; import os; asyncio.run(asyncpg.connect(os.environ['POSTGRES_DSN']))"

# Проверка Redis (локальный сервер)
docker-compose exec web python -c "import redis; import os; r = redis.Redis(host=os.environ['REDIS_HOST'], port=int(os.environ['REDIS_PORT']), password=os.environ.get('REDIS_PASSWORD')); print(r.ping())"

# Проверка Qdrant (локальный сервер)
curl http://127.0.0.1:6333/health
```

### 7.3 Инициализация базы данных

```bash
# Выполнение миграций
docker-compose exec web python init_db.py

# Создание дефолтного администратора (если нужно)
docker-compose exec web python scripts/create_user.py admin admin@example.com admin_password admin

# Выполнение миграций Pro-режима (если нужно)
docker-compose exec web python migrations/001_pro_mode_tables.py
docker-compose exec web python migrations/002_onboarding_and_prefs.py
docker-compose exec web python migrations/003_seed_topics.py
docker-compose exec web python migrations/004_auth_users.py
docker-compose exec web python migrations/005_add_collection_name_to_embeddings.py
docker-compose exec web python migrations/006_replace_topics_with_universal.py
```

### 7.4 Доступ к приложению

- **HTTP:** http://your-server-ip:5000
- **HTTPS (с nginx):** https://your-domain.com

## 🔒 Шаг 8: Настройка безопасности (Production)

### 8.1 Firewall

```bash
# Разрешение только необходимых портов
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 8.2 SSL сертификаты (Let's Encrypt)

```bash
# Установка certbot
sudo apt-get install certbot

# Получение сертификата
sudo certbot certonly --standalone -d your-domain.com

# Копирование сертификатов в nginx/ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem
sudo chmod 644 nginx/ssl/cert.pem
sudo chmod 600 nginx/ssl/key.pem
```

### 7.3 Обновление nginx.conf

Обновите `nginx/nginx.conf` с правильным доменным именем:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;  # Замените на ваш домен
    # ...
}
```

## 📊 Шаг 9: Мониторинг и обслуживание

### 9.1 Просмотр логов

```bash
# Все логи
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f web
docker-compose logs -f worker

# Последние 100 строк
docker-compose logs --tail=100 web
```

### 9.2 Обновление приложения

```bash
# Остановка контейнеров
docker-compose down

# Обновление кода (если используется Git)
git pull

# Пересборка образов
docker-compose build

# Запуск с обновленными образами
docker-compose up -d
```

### 9.3 Резервное копирование

**Примечание:** Так как PostgreSQL, Redis и Qdrant находятся на удаленном сервере, резервное копирование должно выполняться на удаленном сервере или через подключение к удаленным сервисам.

```bash
# Резервное копирование PostgreSQL (с удаленного сервера)
# Выполните на сервере 3.212.39.106 или через SSH:
pg_dump -h 3.212.39.106 -p 5432 -U indlab_user -d indlab_db > backup_$(date +%Y%m%d).sql

# Или через Docker контейнер (если есть доступ):
docker-compose exec web python -c "import asyncpg, asyncio, os; asyncio.run(asyncpg.connect(os.environ['POSTGRES_DSN']).execute('SELECT 1'))"

# Резервное копирование Qdrant (выполните на удаленном сервере 3.212.39.106)
# Qdrant данные находятся на удаленном сервере, резервное копирование должно выполняться там

# Резервное копирование сессии Telegram
cp telegram_parser.session telegram_parser.session.backup
```

### 9.4 Восстановление из резервной копии

```bash
# Восстановление PostgreSQL (на удаленном сервере)
psql -h 3.212.39.106 -p 5432 -U indlab_user -d indlab_db < backup_20231202.sql

# Восстановление Qdrant (выполните на удаленном сервере 3.212.39.106)
```

## 🛠️ Шаг 10: Устранение неполадок

### 10.1 Проблемы с подключением

```bash
# Проверка локальных сервисов на хосте
sudo systemctl status postgresql
sudo systemctl status redis-server
docker ps | grep qdrant  # если Qdrant в Docker

# Проверка доступности портов
nc -zv 127.0.0.1 5432  # PostgreSQL
nc -zv 127.0.0.1 6379  # Redis
nc -zv 127.0.0.1 6333  # Qdrant

# Проверка переменных окружения в контейнере
docker-compose exec web env | grep POSTGRES
docker-compose exec web env | grep REDIS
docker-compose exec web env | grep QDRANT

# Проверка подключения к PostgreSQL из контейнера
docker-compose exec web python -c "import asyncpg, asyncio, os; asyncio.run(asyncpg.connect(os.environ['POSTGRES_DSN']))"

# Проверка подключения к Redis из контейнера
docker-compose exec web python -c "import redis, os; r = redis.Redis(host=os.environ['REDIS_HOST'], port=int(os.environ['REDIS_PORT']), password=os.environ.get('REDIS_PASSWORD')); print(r.ping())"

# Проверка подключения к Qdrant из контейнера
docker-compose exec web curl http://127.0.0.1:6333/health
```

### 10.2 Проблемы с моделями

Модели Hugging Face скачиваются автоматически при первом использовании. Они сохраняются в volume `models_cache`.

```bash
# Проверка размера кеша моделей
docker volume inspect telegram_parser_models_cache

# Очистка кеша (если нужно)
docker volume rm telegram_parser_models_cache
```

### 10.3 Проблемы с памятью

Если не хватает памяти для моделей:

```bash
# Увеличение swap (временное решение)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 10.4 Перезапуск сервисов

```bash
# Перезапуск конкретного сервиса
docker-compose restart web
docker-compose restart worker

# Перезапуск всех сервисов
docker-compose restart
```

## 📝 Шаг 11: Дополнительные настройки

### 11.1 Настройка автоматического перезапуска

Docker Compose уже настроен на автоматический перезапуск (`restart: unless-stopped`). Для дополнительной надежности можно использовать systemd:

```bash
# Создание systemd service
sudo nano /etc/systemd/system/telegram-parser.service
```

```ini
[Unit]
Description=Telegram Parser Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/telegram_parser
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
# Активация сервиса
sudo systemctl enable telegram-parser
sudo systemctl start telegram-parser
```

### 11.2 Настройка мониторинга

Рекомендуется использовать мониторинг для отслеживания состояния приложения:

- **Prometheus + Grafana** для метрик
- **Sentry** для отслеживания ошибок
- **ELK Stack** для логов

## ✅ Чеклист развертывания

- [ ] Docker и Docker Compose установлены
- [ ] Проект склонирован на сервер
- [ ] Файл `.env` создан и заполнен с правильными адресами удаленных сервисов
- [ ] Telegram сессия создана и скопирована на сервер
- [ ] PostgreSQL, Redis и Qdrant установлены и запущены на том же сервере
- [ ] Проверена доступность локальных сервисов (PostgreSQL, Redis, Qdrant на 127.0.0.1)
- [ ] Все контейнеры запущены и работают
- [ ] База данных инициализирована
- [ ] Приложение доступно через браузер
- [ ] SSL сертификаты настроены (для production)
- [ ] Firewall настроен (разрешены порты для локальных сервисов)
- [ ] Резервное копирование настроено
- [ ] Мониторинг настроен (опционально)

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose logs -f`
2. Проверьте статус контейнеров: `docker-compose ps`
3. Проверьте переменные окружения: `docker-compose exec web env`
4. Проверьте подключение к сервисам: `docker-compose exec web ping <service>`

## 🔗 Полезные ссылки

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

