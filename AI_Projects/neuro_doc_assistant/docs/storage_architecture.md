# Архитектура хранения базы знаний

## 📋 Обзор

Документ описывает варианты развертывания исходных файлов (базы знаний) в Docker и выбора базы данных для метаданных, с учетом возможности развертывания в SberCloud.

---

## 🎯 Текущее состояние

### Текущая архитектура хранения

**Локальное хранение:**
- Файлы документов: `data/NeuroDoc_Data/` (локальная файловая система)
- Структура:
  - `hr/` - HR-документы (50+ .md файлов)
  - `it/` - IT-документы (50+ .md файлов)
  - `compliance/` - Документы по комплаенсу (.md, .pdf, .docx)
  - `onboarding/` - Документы для онбординга
  - `policies/`, `procedures/`, `faq/` - Дополнительные категории

**Векторное хранилище:**
- Qdrant - хранит embeddings и метаданные чанков в payload

**Метаданные:**
- Временно хранятся в Qdrant payload
- `ExperimentRepository` использует in-memory хранилище (TODO: PostgreSQL)

### Проблемы текущего подхода

1. **Не масштабируется**: Локальная файловая система не подходит для production
2. **Нет версионирования**: Сложно отслеживать изменения документов
3. **Нет централизованного хранилища метаданных**: Метаданные разбросаны между Qdrant и кодом
4. **Сложность развертывания**: Требуется копирование файлов в каждый контейнер
5. **Нет резервного копирования**: Риск потери данных

---

## 🏗️ Рекомендуемая архитектура

### Production (SberCloud)

```
┌─────────────────────────────────────────────────────────────┐
│                    SberCloud Infrastructure                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐      ┌──────────────────────┐         │
│  │  FastAPI App    │      │  Ingestion Service   │         │
│  │  (Compute VM)   │◄─────┤  (Compute VM)        │         │
│  └────────┬────────┘      └──────────┬───────────┘         │
│           │                          │                      │
│           │                          │                      │
│  ┌────────▼────────┐      ┌─────────▼──────────┐          │
│  │  Qdrant         │      │  SberCloud Object   │          │
│  │  (Compute VM)   │      │  Storage            │          │
│  │                 │      │  (S3-compatible)    │          │
│  └─────────────────┘      └─────────────────────┘          │
│                                    │                        │
│                           ┌────────▼──────────┐            │
│                           │  Managed          │            │
│                           │  PostgreSQL      │            │
│                           │  (Metadata DB)   │            │
│                           └──────────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### Development (Docker)

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  FastAPI     │  │  Ingestion   │  │  Qdrant      │     │
│  │  Container   │  │  Container   │  │  Container   │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                  │              │
│         └─────────────────┼──────────────────┘             │
│                            │                                 │
│                   ┌────────▼──────────┐                     │
│                   │  MinIO Container  │                     │
│                   │  (S3-compatible)  │                     │
│                   └─────────┬─────────┘                     │
│                             │                                 │
│                   ┌─────────▼─────────┐                      │
│                   │  PostgreSQL       │                      │
│                   │  Container        │                      │
│                   └───────────────────┘                      │
│                                                              │
│  ┌──────────────────────────────────────────────┐           │
│  │  Docker Volume: data/NeuroDoc_Data/          │           │
│  │  (для локальной разработки)                  │           │
│  └──────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

---

## 💾 Варианты хранения документов

### Вариант 1: SberCloud Object Storage (Production) ✅ Рекомендуется

**Описание:**
- S3-совместимое объектное хранилище
- Управляемый сервис SberCloud
- Высокая доступность и масштабируемость

**Преимущества:**
- ✅ Полностью управляемый сервис
- ✅ Автоматическое резервное копирование
- ✅ Высокая доступность (99.9%+ SLA)
- ✅ Масштабируется до петабайт
- ✅ Интеграция с другими сервисами SberCloud
- ✅ S3-совместимый API (boto3, aioboto3)

**Недостатки:**
- ⚠️ Требует настройки доступа (IAM, ключи)
- ⚠️ Стоимость зависит от объема и запросов

**Реализация:**
```python
# app/storage/s3_storage.py
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
from typing import List, Optional

class S3DocumentStorage:
    """Хранилище документов в SberCloud Object Storage"""
    
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket_name: str):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        self.bucket_name = bucket_name
    
    def upload_document(self, file_path: Path, object_key: str) -> str:
        """Загружает документ в Object Storage"""
        self.s3_client.upload_file(str(file_path), self.bucket_name, object_key)
        return f"s3://{self.bucket_name}/{object_key}"
    
    def download_document(self, object_key: str, local_path: Path) -> None:
        """Скачивает документ из Object Storage"""
        self.s3_client.download_file(self.bucket_name, object_key, str(local_path))
    
    def list_documents(self, prefix: str = "") -> List[str]:
        """Список документов по префиксу"""
        response = self.s3_client.list_objects_v2(
            Bucket=self.bucket_name,
            Prefix=prefix
        )
        return [obj['Key'] for obj in response.get('Contents', [])]
```

**Конфигурация:**
```env
# .env
SBERCLOUD_STORAGE_ENDPOINT=https://s3.sbercloud.ru
SBERCLOUD_STORAGE_ACCESS_KEY=your_access_key
SBERCLOUD_STORAGE_SECRET_KEY=your_secret_key
SBERCLOUD_STORAGE_BUCKET=neuro-doc-assistant-docs
```

---

### Вариант 2: MinIO в Docker (Development) ✅ Рекомендуется для локальной разработки

**Описание:**
- S3-совместимое хранилище в Docker
- Полная совместимость с SberCloud Object Storage API
- Легко мигрировать на SberCloud в production

**Преимущества:**
- ✅ Полная совместимость с S3 API
- ✅ Работает локально без внешних зависимостей
- ✅ Легкая миграция на SberCloud
- ✅ Можно использовать те же библиотеки (boto3)

**Недостатки:**
- ⚠️ Требует Docker
- ⚠️ Данные хранятся в volume (нужно резервное копирование)

**Docker Compose конфигурация:**
```yaml
# docker-compose.yml
version: '3.8'

services:
  minio:
    image: minio/minio:latest
    container_name: minio
    ports:
      - "9000:9000"  # API
      - "9001:9001"  # Console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin123
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    networks:
      - app-network

volumes:
  minio_data:

networks:
  app-network:
    driver: bridge
```

---

### Вариант 3: Docker Volume (Только для простых случаев)

**Описание:**
- Монтирование локальной директории в контейнер
- Простейший вариант для разработки

**Преимущества:**
- ✅ Простота настройки
- ✅ Нет дополнительных сервисов

**Недостатки:**
- ❌ Не масштабируется
- ❌ Нет версионирования
- ❌ Сложно синхронизировать между контейнерами
- ❌ Не подходит для production

**Использование:**
```yaml
services:
  ingestion:
    volumes:
      - ./data/NeuroDoc_Data:/app/data/NeuroDoc_Data:ro
```

---

## 🗄️ Варианты баз данных для метаданных

### Вариант 1: PostgreSQL (Managed) ✅ Рекомендуется

**Описание:**
- Управляемый PostgreSQL в SberCloud
- Уже указан в архитектуре проекта
- Стандарт для структурированных метаданных

**Преимущества:**
- ✅ ACID транзакции
- ✅ Реляционная модель (связи между документами, версиями, экспериментами)
- ✅ Богатые возможности запросов (JOIN, агрегации)
- ✅ Управляемый сервис (автоматические бэкапы, обновления)
- ✅ Интеграция с SberCloud экосистемой
- ✅ Поддержка JSONB для гибких метаданных

**Схема данных:**
```sql
-- Таблица документов
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path VARCHAR(500) NOT NULL,
    s3_key VARCHAR(500),  -- Ключ в Object Storage
    category VARCHAR(50),  -- hr, it, compliance
    filename VARCHAR(255),
    file_size BIGINT,
    mime_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    indexed_at TIMESTAMP,
    version INTEGER DEFAULT 1,
    metadata JSONB  -- Дополнительные метаданные
);

-- Таблица чанков (связь с Qdrant)
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    chunk_id VARCHAR(255) UNIQUE NOT NULL,  -- ID в Qdrant
    chunk_index INTEGER,  -- Порядковый номер чанка в документе
    text_preview TEXT,  -- Первые 200 символов
    text_length INTEGER,
    embedding_version VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Таблица экспериментов
CREATE TABLE experiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255),
    config JSONB,
    metrics JSONB,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_indexed_at ON documents(indexed_at);
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_chunk_id ON chunks(chunk_id);
```

**Реализация:**
```python
# app/storage/postgres_repository.py
from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

Base = declarative_base()

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_path = Column(String(500), nullable=False)
    s3_key = Column(String(500))
    category = Column(String(50))
    filename = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    indexed_at = Column(DateTime)
    metadata = Column(JSON)

class DocumentRepository:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def save_document(self, doc_data: dict) -> str:
        session = self.Session()
        doc = Document(**doc_data)
        session.add(doc)
        session.commit()
        doc_id = doc.id
        session.close()
        return doc_id
```

**Конфигурация:**
```env
# .env
POSTGRES_HOST=your-postgres-host.sbercloud.ru
POSTGRES_PORT=5432
POSTGRES_DB=neuro_doc_assistant
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_SSL_MODE=require
```

---

### Вариант 2: MongoDB (Альтернатива)

**Описание:**
- NoSQL база данных
- Гибкая схема для метаданных

**Преимущества:**
- ✅ Гибкая схема (легко добавлять поля)
- ✅ Хорошо подходит для JSON-метаданных
- ✅ Горизонтальное масштабирование

**Недостатки:**
- ⚠️ Нет ACID транзакций (частично в новых версиях)
- ⚠️ Сложнее делать JOIN-запросы
- ⚠️ Менее распространен в enterprise (PostgreSQL предпочтительнее)

**Рекомендация:** Использовать только если есть специфические требования к схеме данных.

---

### Вариант 3: SQLite (Только для тестов)

**Описание:**
- Встроенная БД в файл
- Подходит только для тестов и простых случаев

**Преимущества:**
- ✅ Не требует отдельного сервера
- ✅ Простота настройки

**Недостатки:**
- ❌ Не подходит для production (блокировки, производительность)
- ❌ Нет сетевого доступа
- ❌ Нет управления из SberCloud

**Рекомендация:** Использовать только для unit-тестов.

---

## 🐳 Docker Compose конфигурация

### Полная конфигурация для разработки

```yaml
# docker-compose.yml
version: '3.8'

services:
  # PostgreSQL для метаданных
  postgres:
    image: postgres:15-alpine
    container_name: neuro_doc_postgres
    environment:
      POSTGRES_DB: neuro_doc_assistant
      POSTGRES_USER: neuro_doc_user
      POSTGRES_PASSWORD: neuro_doc_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - app-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U neuro_doc_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  # MinIO для S3-совместимого хранилища
  minio:
    image: minio/minio:latest
    container_name: neuro_doc_minio
    ports:
      - "9000:9000"  # S3 API
      - "9001:9001"  # Web Console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin123
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  # Qdrant для векторного поиска
  qdrant:
    image: qdrant/qdrant:latest
    container_name: neuro_doc_qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    networks:
      - app-network

  # FastAPI приложение
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: neuro_doc_api
    ports:
      - "8000:8000"
    environment:
      - QDRANT_URL=http://qdrant:6333
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=neuro_doc_assistant
      - POSTGRES_USER=neuro_doc_user
      - POSTGRES_PASSWORD=neuro_doc_password
      - S3_ENDPOINT=http://minio:9000
      - S3_ACCESS_KEY=minioadmin
      - S3_SECRET_KEY=minioadmin123
      - S3_BUCKET=neuro-doc-docs
    volumes:
      - ./data/NeuroDoc_Data:/app/data/NeuroDoc_Data:ro  # Для локальной разработки
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
      qdrant:
        condition: service_started
    networks:
      - app-network

volumes:
  postgres_data:
  minio_data:
  qdrant_data:

networks:
  app-network:
    driver: bridge
```

---

## 🔄 Миграция с локального хранения

### Этап 1: Подготовка

1. **Создать S3-хранилище (MinIO или SberCloud Object Storage)**
2. **Настроить PostgreSQL**
3. **Обновить DocumentLoader для поддержки S3**

### Этап 2: Загрузка существующих документов

```python
# scripts/migrate_to_s3.py
from app.storage.s3_storage import S3DocumentStorage
from app.storage.postgres_repository import DocumentRepository
from pathlib import Path
import os

def migrate_documents():
    # Инициализация хранилищ
    s3_storage = S3DocumentStorage(
        endpoint_url=os.getenv("S3_ENDPOINT"),
        access_key=os.getenv("S3_ACCESS_KEY"),
        secret_key=os.getenv("S3_SECRET_KEY"),
        bucket_name=os.getenv("S3_BUCKET")
    )
    
    db_repo = DocumentRepository(os.getenv("DATABASE_URL"))
    
    # Загрузка всех документов
    data_dir = Path("data/NeuroDoc_Data")
    for category_dir in data_dir.iterdir():
        if category_dir.is_dir():
            category = category_dir.name
            for doc_file in category_dir.glob("*.md"):
                # Загружаем в S3
                s3_key = f"{category}/{doc_file.name}"
                s3_storage.upload_document(doc_file, s3_key)
                
                # Сохраняем метаданные в PostgreSQL
                db_repo.save_document({
                    "file_path": str(doc_file),
                    "s3_key": s3_key,
                    "category": category,
                    "filename": doc_file.name
                })
```

### Этап 3: Обновление DocumentLoader

```python
# app/ingestion/loader.py (обновленная версия)
class DocumentLoader:
    def __init__(self, storage_backend: str = "local"):
        """
        Args:
            storage_backend: "local" | "s3"
        """
        self.storage_backend = storage_backend
        if storage_backend == "s3":
            self.s3_storage = S3DocumentStorage(...)
    
    def load_documents(self, path: str) -> List[Document]:
        if self.storage_backend == "s3":
            return self._load_from_s3(path)
        else:
            return self._load_from_local(path)
```

---

## 📊 Сравнение вариантов

| Критерий | Локальная FS | MinIO (Docker) | SberCloud Object Storage | PostgreSQL (Metadata) |
|----------|--------------|----------------|---------------------------|----------------------|
| **Масштабируемость** | ❌ Низкая | ✅ Средняя | ✅ Высокая | ✅ Высокая |
| **Доступность** | ❌ Зависит от хоста | ✅ Высокая | ✅ Очень высокая (99.9%+) | ✅ Очень высокая |
| **Резервное копирование** | ❌ Ручное | ⚠️ Через volume | ✅ Автоматическое | ✅ Автоматическое |
| **Стоимость** | ✅ Бесплатно | ✅ Бесплатно (локально) | ⚠️ Платно | ⚠️ Платно |
| **Сложность настройки** | ✅ Простая | ⚠️ Средняя | ⚠️ Средняя | ⚠️ Средняя |
| **Версионирование** | ❌ Нет | ⚠️ Через S3 versioning | ✅ S3 versioning | ✅ Через схему БД |
| **Подходит для production** | ❌ Нет | ⚠️ Только dev/test | ✅ Да | ✅ Да |

---

## ✅ Рекомендации

### Для локальной разработки:
1. **MinIO** в Docker для документов (S3-совместимость)
2. **PostgreSQL** в Docker для метаданных
3. **Qdrant** в Docker для векторного поиска

### Для production (SberCloud):
1. **SberCloud Object Storage** для документов
2. **Managed PostgreSQL** для метаданных
3. **Qdrant** на Compute VM или Managed Service (если доступен)

### Приоритет реализации:
1. ✅ **Высокий**: Интеграция с PostgreSQL для метаданных
2. ✅ **Высокий**: Поддержка S3-совместимого хранилища (MinIO/SberCloud)
3. ⚠️ **Средний**: Миграция существующих документов
4. ⚠️ **Средний**: Версионирование документов

---

## 🔗 Связанные документы

- [Архитектура проекта](./architecture.md)
- [Процесс индексации](./indexing_process.md)
- [Настройка SberCloud](./sbercloud_setup.md) (TODO)

---

## 📝 TODO

- [ ] Реализовать `S3DocumentStorage`
- [ ] Реализовать `DocumentRepository` с PostgreSQL
- [ ] Обновить `DocumentLoader` для поддержки S3
- [ ] Создать миграционный скрипт
- [ ] Добавить Docker Compose конфигурацию
- [ ] Написать документацию по настройке SberCloud Object Storage
- [ ] Добавить тесты для нового хранилища

