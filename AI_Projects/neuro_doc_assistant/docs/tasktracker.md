# Task Tracker — Neuro_Doc_Assistant

Документ для отслеживания прогресса задач проекта. Статус каждой задачи отражает реальное состояние разработки.

## Формат записи задачи

- **Status**: Not started | In progress | Completed | Blocked
- **Priority**: Критический | Высокий | Средний | Низкий
- **Description**: Чёткое описание задачи
- **Execution steps**: Чек-лист шагов выполнения
- **Dependencies**: Связанные задачи или компоненты
- **Assignee**: Ответственный (если назначен)
- **Updated**: Дата последнего обновления

---

## Task: Формализация UC-1 и подготовка документации

- **Status**: Completed
- **Priority**: Критический
- **Description**: Формализация тестов UC-1, обновление project.md с деталями Ingestion module, создание структуры документации (tasktracker.md, diary.md, qa.md, changelog.md)
- **Execution steps**:
  - [x] Анализ тестов UC-1 и формализация acceptance criteria
  - [x] Обновление docs/project.md с деталями Ingestion & Indexing module
  - [x] Создание docs/tasktracker.md
  - [x] Создание docs/diary.md
  - [x] Создание docs/qa.md
  - [x] Создание docs/changelog.md
- **Dependencies**: Нет
- **Updated**: 2024-12-19

---

## Task: Ingestion & Indexing Module (Tests First)

- **Status**: Completed
- **Priority**: Критический
- **Description**: Разработка модуля Ingestion & Indexing с подходом test-first. Модуль должен загружать документы из data/NeuroDoc_Data/hr/ и data/NeuroDoc_Data/it/, чанковать их, генерировать embeddings и индексировать в Qdrant.
- **Execution steps**:
  - [x] Проектирование тестов для DocumentLoader (загрузка MD файлов, нормализация текста) → `tests/ingestion/test_loader.py`
  - [x] Проектирование тестов для Chunker (разбиение на чанки 200-400 токенов, overlap) → `tests/ingestion/test_chunker.py`
  - [x] Проектирование тестов для EmbeddingService (интеграция с GigaChat Embeddings API) → `tests/ingestion/test_embedding_service.py`
  - [x] Проектирование тестов для QdrantIndexer (создание коллекции, запись векторов с метаданными) → `tests/ingestion/test_indexer.py`
  - [x] Проектирование интеграционного теста для полного ingestion pipeline → `tests/ingestion/test_pipeline.py`
  - [x] Создание фикстуры prepared_vector_store → `tests/fixtures/vector_store.py`
  - [x] Создание общих фикстур → `tests/conftest.py`
  - [x] Реализация DocumentLoader (app/ingestion/loader.py)
  - [x] Реализация Chunker (app/ingestion/chunker.py)
  - [x] Реализация EmbeddingService (app/ingestion/embedding_service.py)
  - [x] Реализация QdrantIndexer (app/ingestion/indexer.py)
  - [x] Проверка, что все тесты проходят ✅ (40/40 тестов прошли успешно)
  - [ ] Проверка, что тесты UC-1 проходят с реальным ingestion pipeline
- **Dependencies**: Нет (базовый модуль)
- **Updated**: 2024-12-19

---

## Task: Retrieval Layer Module (Tests First)

- **Status**: Completed
- **Priority**: Критический
- **Description**: Разработка модуля Retrieval Layer для semantic search по Qdrant с поддержкой фильтрации по метаданным и параметризацией K.
- **Execution steps**:
  - [x] Проектирование тестов для Retriever (semantic search с K=3, K=5, K=8) → `tests/retrieval/test_retriever.py`
  - [x] Проектирование тестов для MetadataFilter (фильтрация по category, source, file_path) → `tests/retrieval/test_metadata_filter.py`
  - [x] Проектирование интеграционных тестов → `tests/retrieval/test_retrieval_integration.py`
  - [x] Реализация Retriever (app/retrieval/retriever.py)
  - [x] Реализация MetadataFilter (app/retrieval/metadata_filter.py)
  - [x] Интеграция с Qdrant
  - [x] Проверка, что все тесты проходят ✅ (23/23 тестов прошли успешно)
  - [ ] Проверка метрик Precision@K (будет в Evaluation module)
- **Dependencies**: Ingestion & Indexing Module ✅
- **Updated**: 2024-12-19

---

## Task: Generation Layer Module (Tests First)

- **Status**: Completed
- **Priority**: Критический
- **Description**: Разработка модуля Generation Layer для генерации ответов через GigaChat API с строгим контролем контекста (защита от галлюцинаций).
- **Execution steps**:
  - [x] Проектирование тестов для PromptBuilder (формирование prompt с контекстом и инструкцией) → `tests/generation/test_prompt_builder.py`
  - [x] Проектирование тестов для LLMClient (интеграция с GigaChat API) → `tests/generation/test_gigachat_client.py`
  - [x] Проектирование тестов на отсутствие галлюцинаций → `tests/generation/test_no_hallucinations.py`
  - [x] Проектирование интеграционных тестов → `tests/generation/test_generation_integration.py`
  - [x] Реализация PromptBuilder (app/generation/prompt_builder.py)
  - [x] Реализация LLMClient (app/generation/gigachat_client.py)
  - [x] Проверка, что все тесты проходят ✅ (22/22 тестов прошли успешно)
  - [ ] Интеграция с реальным GigaChat API (требует API ключ)
- **Dependencies**: Retrieval Layer Module ✅
- **Updated**: 2024-12-19

---

## Task: Evaluation & Metrics Module (Tests First)

- **Status**: Completed
- **Priority**: Высокий
- **Description**: Разработка модуля Evaluation & Metrics для расчёта Precision@K, интеграции RAGAS и сбора latency/throughput метрик.
- **Execution steps**:
  - [x] Проектирование тестов для MetricsCollector (расчёт Precision@K) → `tests/evaluation/test_metrics.py`
  - [x] Проектирование тестов для RAGASEvaluator (Faithfulness, Answer Relevancy) → `tests/evaluation/test_ragas_evaluator.py`
  - [x] Проектирование интеграционных тестов → `tests/evaluation/test_evaluation_integration.py`
  - [x] Реализация MetricsCollector (app/evaluation/metrics.py)
  - [x] Реализация RAGASEvaluator (app/evaluation/ragas_evaluator.py)
  - [x] Проверка, что все тесты проходят ✅ (21/21 тестов прошли успешно)
  - [ ] Интеграция с реальным RAGAS (опционально, для production, требует установку ragas)
  - [x] Сбор latency метрик (реализовано в MetricsCollector)
- **Dependencies**: Generation Layer Module ✅
- **Updated**: 2024-12-19

---

## Task: Agent Layer Module (Tests First)

- **Status**: Completed
- **Priority**: Критический
- **Description**: Разработка Agent Layer с детерминированной state machine для оркестрации всех модулей и управления экспериментальными прогонами.
- **Execution steps**:
  - [x] Проектирование тестов для AgentStateMachine (все состояния: IDLE → VALIDATE_QUERY → RETRIEVE → GENERATE → VALIDATE_ANSWER → RETURN_RESPONSE) → `tests/agent/test_state_machine.py`
  - [x] Проектирование тестов для AgentController (оркестрация модулей) → `tests/agent/test_agent_controller.py`
  - [x] Проектирование тестов для DecisionLog (трассировка решений) → `tests/agent/test_decision_log.py`
  - [x] Проектирование интеграционных тестов → `tests/agent/test_agent_integration.py`
  - [x] Реализация AgentStateMachine (app/agent/state_machine.py)
  - [x] Реализация AgentController (app/agent/agent.py)
  - [x] Реализация DecisionLog (app/agent/decision_log.py)
  - [x] Интеграция всех модулей через Agent Layer
  - [x] Проверка, что все тесты проходят ✅ (25/25 тестов прошли успешно)
  - [x] Проверка, что тесты UC-1 проходят полностью через Agent Layer ✅ (2/2 теста UC-1 прошли успешно)
- **Dependencies**: Все предыдущие модули (Ingestion ✅, Retrieval ✅, Generation ✅, Evaluation ✅)
- **Updated**: 2024-12-19

---

## Task: API & UI Layer

- **Status**: Completed
- **Priority**: Высокий
- **Description**: Разработка REST API (FastAPI) и демо-интерфейса (Streamlit) для взаимодействия с агентом и отображения ответов, источников и метрик.
- **Execution steps**:
  - [x] Проектирование тестов для API endpoints (POST /ask, GET /health, GET /metrics, GET /logs) → `tests/api/test_query_api.py`, `tests/api/test_admin_api.py`
  - [x] Реализация QueryAPI (app/api/chat.py) с интеграцией Agent Layer
  - [x] Реализация AdminAPI (app/api/admin.py) для управления и мониторинга
  - [x] Создание main.py для FastAPI приложения
  - [x] Проверка, что все тесты проходят ✅ (11/11 тестов прошли успешно)
  - [x] Реализация DemoUI (Streamlit) → `app/ui/streamlit_app.py`
  - [x] Интеграция Streamlit UI с API через HTTP запросы
  - [x] Отображение ответов, источников и метрик в UI
  - [x] Создание скриптов запуска Streamlit UI → `scripts/run_streamlit.bat`, `scripts/run_streamlit.sh`
- **Dependencies**: Agent Layer Module ✅
- **Updated**: 2024-12-19

---

## Task: Reranking Module (Optional)

- **Status**: Completed
- **Priority**: Средний
- **Description**: Разработка опционального модуля Reranking для переупорядочивания retrieved документов и повышения Precision@3 (UC-4).
- **Execution steps**:
  - [x] Проектирование тестов для Reranker (сравнение Precision@3 с/без reranking) → `tests/reranking/test_reranker.py`
  - [x] Реализация Reranker (app/reranking/reranker.py) с keyword-based reranking
  - [x] Интеграция с Retrieval Layer
  - [x] Интеграция с Agent Layer (опциональный параметр use_reranking)
  - [x] Проверка, что все тесты проходят ✅ (8/8 тестов прошли успешно)
  - [ ] Эксперименты по влиянию reranking на метрики (для production)
- **Dependencies**: Retrieval Layer Module ✅
- **Updated**: 2024-12-19

---

## Task: Monitoring & Observability

- **Status**: Completed
- **Priority**: Средний
- **Description**: Настройка Prometheus и Grafana для мониторинга latency, QPS и ошибок (UC-7).
- **Execution steps**:
  - [x] Проектирование тестов для Prometheus метрик → `tests/monitoring/test_prometheus_metrics.py`
  - [x] Реализация PrometheusMetrics (app/monitoring/prometheus_metrics.py)
  - [x] Интеграция метрик в Agent Layer (latency, QPS, errors)
  - [x] Создание endpoint для Prometheus scrape (GET /admin/metrics/prometheus)
  - [x] Проверка, что все тесты проходят ✅ (11/11 тестов прошли успешно)
  - [ ] Настройка Grafana дашбордов (для production)
  - [ ] Проверка p95 latency < 1.3 сек (для production)
- **Dependencies**: Agent Layer Module ✅
- **Updated**: 2024-12-19

---

## Task: Experimental Cycle (UC-6)

- **Status**: Completed
- **Priority**: Средний
- **Description**: Реализация экспериментального цикла для оценки влияния конфигураций (chunk_size, K, reranking) на метрики качества.
- **Execution steps**:
  - [x] Проектирование тестов для ExperimentRepository → `tests/storage/test_experiment_repository.py` (12 тестов)
  - [x] Реализация ExperimentRepository (app/storage/experiment_repository.py)
  - [x] In-memory хранилище для тестов (PostgreSQL интеграция - TODO для production)
  - [x] Интеграция с Agent Layer для автоматического сохранения результатов экспериментов
  - [x] Автоматизация запуска экспериментов с разными конфигурациями → `scripts/run_experiments.py`
  - [x] Создан файл с примерами запросов → `scripts/sample_queries.txt`
  - [ ] Визуализация результатов в Grafana (для production)
- **Dependencies**: Evaluation & Metrics Module ✅, Metadata & Storage Module ✅
- **Updated**: 2024-12-19

---

## Task: UC-2 - Уточнение контекста (Agent Reasoning)

- **Status**: Completed
- **Priority**: Высокий
- **Description**: Реализация логики уточнения контекста для неоднозначных или слишком общих запросов (UC-2).
- **Execution steps**:
  - [x] Проектирование тестов для QueryValidator → `tests/agent/test_query_validator.py` (8 тестов)
  - [x] Реализация QueryValidator (app/agent/query_validator.py)
  - [x] Интеграция QueryValidator в Agent Layer
  - [x] Проектирование тестов для UC-2 → `tests/use_cases/test_uc2_clarification.py` (4 теста)
  - [x] Проверка, что все тесты проходят ✅ (12/12 тестов прошли успешно)
- **Dependencies**: Agent Layer Module ✅
- **Updated**: 2024-12-19

