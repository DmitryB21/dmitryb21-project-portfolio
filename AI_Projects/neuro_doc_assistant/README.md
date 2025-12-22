# Neuro_Doc_Assistant

RAG + Lightweight AI-Agent для работы с внутренней документацией компании.

## Описание проекта

Neuro_Doc_Assistant — это production-ready AI-агент для работы с корпоративной документацией, построенный на базе:
- GigaChat API для генерации ответов
- RAG (Retrieval-Augmented Generation) для поиска по документации
- Qdrant для векторного поиска
- Детерминированный Agent Layer для оркестрации

## Технологический стек

- **Python** >= 3.8
- **FastAPI** — REST API
- **GigaChat API** — LLM и embeddings
- **Qdrant** — векторная база данных
- **PostgreSQL** — метаданные и логи
- **Streamlit** — демо-интерфейс
- **RAGAS** — оценка качества
- **Prometheus/Grafana** — мониторинг

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository_url>
cd neuro_doc_assistant
```

### 2. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

```bash
cp .env.example .env
# Отредактируйте .env и заполните реальными значениями
```

### 5. Запуск Qdrant (обязательно для работы с реальными данными)

Qdrant можно запустить через Docker:

```bash
# Запуск Qdrant в Docker
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

Или установить локально (см. [документацию Qdrant](https://qdrant.tech/documentation/guides/installation/)).

**Проверка работы Qdrant:**
```bash
curl http://localhost:6333/collections
```

### 6. Загрузка документов в Qdrant (Ingestion Pipeline)

Перед использованием системы необходимо загрузить документы в Qdrant:

**Windows:**
```bash
scripts\run_ingestion.bat
```

**Linux/Mac:**
```bash
chmod +x scripts/run_ingestion.sh
./scripts/run_ingestion.sh
```

**Или через Python:**
```bash
python scripts/run_ingestion.py
```

Скрипт автоматически:
- Загрузит документы из `data/NeuroDoc_Data/hr/` и `data/NeuroDoc_Data/it/`
- Разобьёт их на чанки
- Сгенерирует embeddings
- Создаст коллекцию `neuro_docs` в Qdrant (если не существует)
- Индексирует все чанки в Qdrant

**Важно:** Убедитесь, что:
- Qdrant запущен и доступен
- В директории `data/NeuroDoc_Data/` есть документы (MD файлы)
- `GIGACHAT_API_KEY` настроен в `.env` (или используется mock mode)

## Структура проекта

```
neuro_doc_assistant/
├── app/
│   ├── ingestion/      # Модуль загрузки и индексации документов
│   ├── retrieval/      # Модуль семантического поиска
│   ├── reranking/      # Модуль переупорядочивания документов (опциональный)
│   ├── generation/     # Модуль генерации ответов
│   ├── evaluation/     # Модуль оценки качества и метрик
│   ├── agent/          # Agent Layer (оркестрация)
│   ├── api/            # REST API endpoints (QueryAPI, AdminAPI)
│   ├── monitoring/     # Prometheus метрики для мониторинга
│   ├── storage/        # ExperimentRepository для хранения результатов экспериментов
│   └── ui/             # Streamlit Demo UI
├── tests/
│   ├── ingestion/      # Тесты для Ingestion module
│   ├── retrieval/      # Тесты для Retrieval module
│   ├── reranking/      # Тесты для Reranking module
│   ├── generation/     # Тесты для Generation module
│   ├── evaluation/     # Тесты для Evaluation module
│   ├── agent/          # Тесты для Agent Layer
│   ├── api/            # Тесты для API Layer
│   ├── monitoring/     # Тесты для Monitoring module
│   ├── storage/        # Тесты для Storage module (Experimental Cycle)
│   ├── use_cases/      # Тесты Use Cases (UC-1, UC-2, ...)
│   └── fixtures/       # Фикстуры для тестов
├── data/
│   └── NeuroDoc_Data/  # Исходные документы (HR, IT, Compliance)
└── docs/
    ├── project.md      # Архитектура и описание проекта
    ├── tasktracker.md  # Отслеживание задач
    ├── diary.md        # Дневник наблюдений
    └── qa.md           # Вопросы по архитектуре
```

## Запуск тестов

### Запуск тестов

#### Быстрый запуск

```bash
# Все тесты
pytest tests/ -v

# Конкретный модуль
pytest tests/ingestion/ -v
pytest tests/retrieval/ -v
```

#### Запуск с логированием (рекомендуется)

Используйте скрипты для запуска тестов с сохранением логов:

**Windows:**
```bash
# Все тесты
scripts\run_tests.bat

# Конкретный модуль
scripts\run_tests.bat ingestion
scripts\run_tests.bat retrieval
```

**Linux/Mac:**
```bash
# Все тесты
./scripts/run_tests.sh

# Конкретный модуль
./scripts/run_tests.sh ingestion
./scripts/run_tests.sh retrieval
```

**Python (кроссплатформенный):**
```bash
# Все тесты
python scripts/run_tests.py

# Конкретный модуль
python scripts/run_tests.py ingestion
python scripts/run_tests.py retrieval
python scripts/run_tests.py generation
python scripts/run_tests.py evaluation
python scripts/run_tests.py agent
python scripts/run_tests.py use_cases
python scripts/run_tests.py api
```

#### Результаты тестирования

После запуска скриптов результаты сохраняются в `tests/logs/`:
- `test_results_YYYY-MM-DD_HH-MM-SS.txt` - текстовый лог
- `junit.xml` - JUnit XML отчет (для CI/CD)
- `report.html` - HTML отчет (если установлен pytest-html)

#### Статистика тестов

- **Ingestion Module**: 40 тестов ✅
- **Retrieval Module**: 23 теста ✅
- **Generation Module**: 22 теста ✅
- **Evaluation Module**: 21 тест ✅
- **Agent Layer Module**: 25 тестов ✅
- **API Layer Module**: 11 тестов ✅
- **Reranking Module**: 8 тестов ✅
- **Monitoring Module**: 11 тестов ✅
- **Storage Module (Experimental Cycle)**: 12 тестов ✅
- **Use Cases (UC-1)**: 2 интеграционных теста ✅
- **Всего**: 175 тестов ✅ (все проходят успешно)

Подробный отчёт см. `docs/test_report.md`.

## Разработка

Проект следует подходу **test-first**: сначала создаются тесты, затем реализуются компоненты.

### Текущий статус

- ✅ **Ingestion & Indexing Module**: Реализован и протестирован
  - DocumentLoader — загрузка MD файлов
  - Chunker — разбиение на чанки с overlap
  - EmbeddingService — генерация embeddings
  - QdrantIndexer — индексация в Qdrant

- ✅ **Retrieval Layer**: Реализован и протестирован
- ✅ **Generation Layer**: Реализован и протестирован
- ✅ **Evaluation & Metrics Module**: Реализован и протестирован
- ✅ **Agent Layer**: Реализован и протестирован
- ✅ **API Layer**: Реализован и протестирован
  - QueryAPI (POST /ask, GET /health)
  - AdminAPI (GET /metrics, GET /logs)
- ✅ **DemoUI (Streamlit)**: Реализован
  - Chat-интерфейс для взаимодействия с агентом
  - Отображение ответов, источников и метрик
- ✅ **Reranking Module** (опциональный): Реализован и протестирован
  - Переупорядочивание retrieved документов для повышения Precision@3
  - Keyword-based reranking с комбинацией semantic search score
- ✅ **Monitoring & Observability**: Реализован и протестирован
  - Prometheus метрики для latency (end-to-end, retrieval, generation)
  - Метрики QPS и ошибок
  - Endpoint для Prometheus scrape (GET /admin/metrics/prometheus)
- ✅ **Experimental Cycle (UC-6)**: Реализован и протестирован
  - ExperimentRepository для хранения результатов экспериментов
  - Сохранение конфигураций (chunk_size, K, reranking) и метрик
  - Сравнение экспериментов по метрикам
  - Интеграция с Agent Layer для автоматического сохранения

Подробнее см. `docs/tasktracker.md`.

## Запуск API

### Запуск FastAPI сервера

```bash
# Через uvicorn напрямую
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Или через Python
python app/main.py
```

API будет доступен по адресу `http://localhost:8000`

### API Endpoints

#### QueryAPI

- **POST /ask** — Запрос к агенту
  ```json
  {
    "query": "Какой SLA у сервиса платежей?",
    "k": 3,
    "ground_truth_relevant": null
  }
  ```

- **GET /health** — Проверка здоровья сервиса

#### AdminAPI

- **GET /admin/metrics** — Получение метрик системы и агента
- **GET /admin/metrics/prometheus** — Endpoint для Prometheus scrape
- **GET /admin/logs?limit=100** — Получение логов решений агента

### Документация API

После запуска сервера доступна автоматическая документация:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Экспериментальный цикл (UC-6)

Для запуска batch экспериментов с разными конфигурациями используйте скрипт `scripts/run_experiments.py`:

```bash
# Минимальный набор экспериментов (быстро)
python scripts/run_experiments.py --query "Какой SLA у сервиса платежей?" --configs minimal

# Эксперименты с разными размерами чанков
python scripts/run_experiments.py --queries scripts/sample_queries.txt --configs chunk_size --output results_chunk_size.json

# Эксперименты с разными значениями K
python scripts/run_experiments.py --queries scripts/sample_queries.txt --configs k --output results_k.json

# Эксперименты с reranking
python scripts/run_experiments.py --queries scripts/sample_queries.txt --configs reranking --output results_reranking.json

# Полный набор экспериментов (все комбинации)
python scripts/run_experiments.py --queries scripts/sample_queries.txt --configs all --output results_all.json
```

Результаты сохраняются в JSON файл с метриками для каждой конфигурации.

## Быстрый старт

Для быстрого запуска проекта используйте скрипт:

```bash
# Windows:
scripts\start_project.bat

# Linux/Mac:
chmod +x scripts/start_project.sh
./scripts/start_project.sh
```

Скрипт поможет:
1. Проверить виртуальное окружение
2. Настроить .env файл
3. Установить зависимости
4. Запустить тесты, API или UI

Подробнее см. `docs/quick_start.md`

## Документация

- `docs/quick_start.md` — быстрый старт проекта
- `docs/project.md` — полное описание проекта, архитектуры и модулей
- `docs/agent_flow.md` — логика работы агента и state machine
- `docs/tasktracker.md` — отслеживание прогресса задач
- `docs/diary.md` — дневник наблюдений проекта
- `docs/qa.md` — вопросы по архитектуре
- `docs/test_report.md` — подробный отчёт о тестировании всех модулей (187 тестов)

## Use Cases

- **UC-1**: Базовый поиск информации (✅ реализован)
- **UC-2**: Уточнение контекста (✅ реализован)
- **UC-3**: Фильтрация по метаданным (✅ реализован через MetadataFilter)
- **UC-4**: Reranking (✅ реализован)
- **UC-5**: Обработка отсутствия информации
- **UC-6**: Экспериментальный цикл (✅ реализован)
- **UC-7**: Мониторинг (✅ реализован)
- **UC-8**: Демонстрация

## Лицензия

[Указать лицензию]

## Контакты

[Указать контакты]

