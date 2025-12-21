# Инструкция по установке и настройке — Neuro_Doc_Assistant

## Предварительные требования

- Python >= 3.8
- pip (менеджер пакетов Python)
- Git (для клонирования репозитория)

## Установка зависимостей

### 1. Создание виртуального окружения

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python -m venv venv
source venv/bin/activate
```

### 2. Установка пакетов

```bash
pip install -r requirements.txt
```

### 3. Проверка установки

```bash
python -c "import pytest; import tiktoken; import qdrant_client; import requests; print('All dependencies installed successfully')"
```

## Настройка переменных окружения

1. Скопируйте файл `.env.example` в `.env`:
   ```bash
   cp .env.example .env
   ```

2. Отредактируйте `.env` и заполните реальными значениями:
   - `GIGACHAT_API_KEY` — API ключ для GigaChat
   - `GIGACHAT_EMBEDDINGS_URL` — URL endpoint для embeddings API
   - `QDRANT_HOST`, `QDRANT_PORT` — параметры подключения к Qdrant

## Запуск тестов

### Тесты Ingestion module

```bash
# Все тесты Ingestion module
pytest tests/ingestion/ -v

# Конкретный тест
pytest tests/ingestion/test_loader.py::TestDocumentLoader::test_load_single_md_file -v

# Тесты с покрытием
pytest tests/ingestion/ --cov=app/ingestion --cov-report=html
```

### Тесты Use Cases

```bash
# Тесты UC-1
pytest tests/use_cases/test_uc1_basic_search.py -v

# Все тесты Use Cases
pytest tests/use_cases/ -v
```

### Все тесты проекта

```bash
pytest tests/ -v
```

## Запуск Ingestion pipeline

После установки зависимостей можно запустить ingestion pipeline для индексации документов:

```python
from app.ingestion.loader import DocumentLoader
from app.ingestion.chunker import Chunker
from app.ingestion.embedding_service import EmbeddingService
from app.ingestion.indexer import QdrantIndexer
from qdrant_client import QdrantClient

# Инициализация компонентов
loader = DocumentLoader()
chunker = Chunker()
embedding_service = EmbeddingService(model_version="GigaChat", embedding_dim=1536)
qdrant_client = QdrantClient(host="localhost", port=6333)
indexer = QdrantIndexer(qdrant_client=qdrant_client, collection_name="neuro_docs")

# Загрузка документов
hr_documents = loader.load_documents("data/NeuroDoc_Data/hr")
it_documents = loader.load_documents("data/NeuroDoc_Data/it")
all_documents = hr_documents + it_documents

# Чанкинг
all_chunks = []
for doc in all_documents:
    chunks = chunker.chunk_documents([doc], chunk_size=300, overlap_percent=0.25)
    all_chunks.extend(chunks)

# Генерация embeddings
chunk_texts = [chunk.text for chunk in all_chunks]
embeddings = embedding_service.generate_embeddings(chunk_texts)

# Индексация в Qdrant
indexer.index_chunks(all_chunks, embeddings)
```

## Устранение проблем

### Ошибка: "No module named pytest"

**Решение:** Установите зависимости:
```bash
pip install -r requirements.txt
```

### Ошибка: "tiktoken not found"

**Решение:** Установите tiktoken:
```bash
pip install tiktoken
```

### Ошибка: "qdrant_client not found"

**Решение:** Установите qdrant-client:
```bash
pip install qdrant-client
```

### Ошибка при подключении к Qdrant

**Решение:** 
1. Убедитесь, что Qdrant запущен:
   ```bash
   docker run -p 6333:6333 qdrant/qdrant
   ```
2. Проверьте параметры подключения в `.env`

### Ошибка при вызове GigaChat API

**Решение:**
1. Проверьте, что `GIGACHAT_API_KEY` установлен в `.env`
2. Убедитесь, что `GIGACHAT_EMBEDDINGS_URL` корректен
3. Для тестов можно использовать моковый режим (без API ключа)

## Следующие шаги

После успешной установки и запуска тестов:

1. Проверьте, что все тесты Ingestion module проходят
2. Запустите ingestion pipeline для индексации документов
3. Проверьте, что тесты UC-1 проходят с реальным ingestion pipeline
4. Приступайте к разработке следующих модулей (Retrieval Layer, Generation Layer)

