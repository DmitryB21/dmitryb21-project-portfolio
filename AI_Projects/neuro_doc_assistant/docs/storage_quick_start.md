# Быстрый старт: Хранение базы знаний

## 🚀 Локальная разработка (Docker)

### 1. Запуск инфраструктуры

```bash
# Запуск всех сервисов (PostgreSQL, MinIO, Qdrant)
docker-compose up -d

# Проверка статуса
docker-compose ps
```

### 2. Настройка MinIO (S3-совместимое хранилище)

1. Откройте консоль MinIO: http://localhost:9001
2. Логин: `minioadmin` / Пароль: `minioadmin123`
3. Создайте bucket: `neuro-doc-docs`

### 3. Настройка переменных окружения

Добавьте в `.env`:

```env
# S3/MinIO
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin123
S3_BUCKET=neuro-doc-docs

# PostgreSQL
DATABASE_URL=postgresql://neuro_doc_user:neuro_doc_password@localhost:5432/neuro_doc_assistant
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=neuro_doc_assistant
POSTGRES_USER=neuro_doc_user
POSTGRES_PASSWORD=neuro_doc_password
```

### 4. Миграция документов в S3

```bash
# Установка зависимостей
pip install boto3 sqlalchemy psycopg2-binary

# Запуск миграции
python scripts/migrate_to_s3.py
```

---

## ☁️ Production (SberCloud)

### 1. Создание SberCloud Object Storage

1. Войдите в консоль SberCloud
2. Создайте Object Storage bucket
3. Получите Access Key и Secret Key

### 2. Создание Managed PostgreSQL

1. Создайте Managed PostgreSQL инстанс
2. Получите connection string

### 3. Настройка переменных окружения

```env
# SberCloud Object Storage
SBERCLOUD_STORAGE_ENDPOINT=https://s3.sbercloud.ru
SBERCLOUD_STORAGE_ACCESS_KEY=your_access_key
SBERCLOUD_STORAGE_SECRET_KEY=your_secret_key
SBERCLOUD_STORAGE_BUCKET=neuro-doc-assistant-docs

# Managed PostgreSQL
DATABASE_URL=postgresql://user:password@host.sbercloud.ru:5432/neuro_doc_assistant
```

### 4. Миграция документов

```bash
python scripts/migrate_to_s3.py
```

---

## 📝 Использование в коде

### Загрузка документов из S3

```python
from app.storage.s3_storage import S3DocumentStorage
from pathlib import Path

# Инициализация (автоматически загружает конфигурацию из .env)
storage = S3DocumentStorage()

# Загрузка документа
s3_uri = storage.upload_document(
    file_path=Path("data/NeuroDoc_Data/hr/hr_01.md"),
    object_key="hr/hr_01.md"
)

# Получение содержимого
content = storage.get_document_content("hr/hr_01.md")

# Список документов
documents = storage.list_documents(prefix="hr/")
```

### Сохранение метаданных в PostgreSQL

```python
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv("DATABASE_URL"))
with engine.connect() as conn:
    conn.execute(
        text("""
            INSERT INTO documents (file_path, s3_key, category, filename)
            VALUES (:file_path, :s3_key, :category, :filename)
        """),
        {
            "file_path": "/local/path/to/file.md",
            "s3_key": "hr/hr_01.md",
            "category": "hr",
            "filename": "hr_01.md"
        }
    )
    conn.commit()
```

---

## 🔍 Проверка

### Проверка S3 хранилища

```bash
# MinIO Console
open http://localhost:9001

# Или через Python
python -c "
from app.storage.s3_storage import S3DocumentStorage
storage = S3DocumentStorage()
print('Documents:', storage.list_documents())
"
```

### Проверка PostgreSQL

```bash
# Подключение к БД
psql -h localhost -U neuro_doc_user -d neuro_doc_assistant

# Проверка таблиц
\dt

# Просмотр документов
SELECT category, filename, s3_key FROM documents LIMIT 10;
```

---

## 📚 Дополнительная информация

- [Полная архитектура хранения](./storage_architecture.md)
- [Docker Compose конфигурация](../docker-compose.yml)
- [SQL схема БД](../scripts/init_db.sql)

