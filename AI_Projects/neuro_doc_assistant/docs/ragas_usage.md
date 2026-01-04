# Использование RAGAS в проекте

## Обзор

RAGAS (Retrieval-Augmented Generation Assessment) используется в проекте для автоматической оценки качества ответов RAG-системы. В текущей реализации RAGAS работает в **mock mode** для тестирования, но архитектура готова для интеграции с реальной библиотекой RAGAS.

## Текущее состояние

### Mock Mode (по умолчанию)

**Статус:** ✅ Реализовано и активно используется

**Расположение:** `app/evaluation/ragas_evaluator.py`

**Инициализация:**
```python
# Mock mode (по умолчанию, если RAGAS_MOCK_MODE=true)
ragas_evaluator = RAGASEvaluator(mock_mode=True)

# Реальный RAGAS (если RAGAS_MOCK_MODE не установлен или false)
from app.evaluation.ragas_adapters import GigaChatLLMAdapter, GigaChatEmbeddingsAdapter

llm_adapter = GigaChatLLMAdapter(llm_client=llm_client)
embeddings_adapter = GigaChatEmbeddingsAdapter(embedding_service=embedding_service)

ragas_evaluator = RAGASEvaluator(
    mock_mode=False,
    llm_adapter=llm_adapter,
    embeddings_adapter=embeddings_adapter
)
```

### Реальный RAGAS

**Статус:** ✅ Реализовано и готово к использованию

**Требования:**
- Установлена библиотека `ragas` (>= 0.4.0)
- Установлены `langchain-core` и `langchain-community`
- Настроены GigaChat API ключи (для LLM и Embeddings)
- Переменная окружения `RAGAS_MOCK_MODE` не установлена или равна `false`

## Где используется RAGAS

### 1. В Agent Layer

RAGAS метрики рассчитываются автоматически для каждого ответа агента:

**Файл:** `app/agent/agent.py`

**Код:**
```python
# Шаг 6: Calculate metrics
metrics = {}

# RAGAS метрики
contexts = [chunk.text for chunk in retrieved_chunks]
ragas_metrics = self.ragas_evaluator.evaluate_all(
    question=query,
    answer=answer,
    contexts=contexts,
    ground_truth=None
)
metrics.update(ragas_metrics)
```

**Когда вызывается:**
- После генерации ответа через LLM
- Перед возвратом ответа пользователю
- В состоянии `VALIDATE_ANSWER` state machine

### 2. В API Response

RAGAS метрики включаются в ответ API:

**Endpoint:** `POST /ask`

**Response:**
```json
{
  "answer": "Текст ответа...",
  "sources": [...],
  "metrics": {
    "faithfulness": 0.90,
    "answer_relevancy": 0.85
  }
}
```

### 3. В Streamlit UI

RAGAS метрики отображаются в UI для каждого ответа:

- **Faithfulness** — насколько ответ основан на контексте
- **Answer Relevancy** — насколько ответ релевантен запросу

### 4. В экспериментальном цикле

RAGAS метрики сохраняются в ExperimentRepository для сравнения конфигураций:

**Файл:** `app/agent/agent.py`

```python
experiment_metrics = metrics.copy()  # Включает RAGAS метрики
experiment_metrics["latency_ms"] = end_to_end_latency * 1000

self.experiment_repository.save_experiment(
    config=experiment_config,
    metrics=experiment_metrics,
    description=f"Experiment: query='{query[:50]}...', k={k}, reranking={use_reranking}"
)
```

## Собираемые метрики

### 1. Faithfulness

**Описание:** Измеряет, насколько ответ основан на предоставленном контексте (retrieved chunks).

**Целевое значение:** ≥ 0.85

**Mock Mode логика:**
- Если ответ содержит текст из контекстов → 0.90
- Если ответ не содержит текст из контекстов → 0.50

**Использование:**
- Обнаружение галлюцинаций
- Проверка, что ответ основан на документации
- Оценка качества retrieval

### 2. Answer Relevancy

**Описание:** Измеряет, насколько ответ релевантен вопросу пользователя.

**Целевое значение:** ≥ 0.80

**Mock Mode логика:**
- Если ответ содержит ключевые слова из вопроса → 0.85
- Если ответ не содержит ключевые слова → 0.60

**Использование:**
- Проверка релевантности ответа
- Обнаружение нерелевантных ответов
- Оценка качества генерации

## Архитектура RAGASEvaluator

### Класс: `RAGASEvaluator`

**Файл:** `app/evaluation/ragas_evaluator.py`

**Методы:**

1. **`evaluate_faithfulness(question, answer, contexts)`**
   - Рассчитывает Faithfulness score
   - Возвращает: `float` (0.0-1.0)

2. **`evaluate_answer_relevancy(question, answer, contexts)`**
   - Рассчитывает Answer Relevancy score
   - Возвращает: `float` (0.0-1.0)

3. **`evaluate_all(question, answer, contexts, ground_truth=None)`**
   - Рассчитывает все RAGAS метрики
   - Возвращает: `Dict[str, float]` с ключами `faithfulness` и `answer_relevancy`

### Mock Mode vs Real RAGAS

#### Mock Mode (текущая реализация)

**Преимущества:**
- ✅ Не требует установки дополнительных зависимостей
- ✅ Быстрая работа (без вызовов LLM)
- ✅ Подходит для тестирования и разработки

**Недостатки:**
- ❌ Упрощённая логика оценки
- ❌ Не использует реальные LLM для оценки
- ❌ Менее точные метрики

**Логика:**
```python
# Faithfulness: проверка наличия текста из контекста в ответе
if any(context.lower() in answer_lower for context in contexts):
    return 0.90
else:
    return 0.50

# Answer Relevancy: проверка пересечения ключевых слов
question_keywords = set(question_lower.split())
answer_keywords = set(answer_lower.split())
overlap = len(question_keywords.intersection(answer_keywords))
if overlap > 0:
    return 0.85
else:
    return 0.60
```

#### Real RAGAS (реализовано)

**Статус:** ✅ Реализовано и готово к использованию

**Преимущества:**
- ✅ Точная оценка через LLM
- ✅ Соответствие стандартам RAGAS
- ✅ Поддержка дополнительных метрик
- ✅ Автоматический fallback к mock mode при ошибках

**Требования:**
- Установка библиотеки `ragas` (>= 0.4.0)
- Установка `langchain-core` и `langchain-community`
- Настройка GigaChat API ключей (для LLM и Embeddings)

**Реализация:**
```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from datasets import Dataset

def evaluate_faithfulness(self, question, answer, contexts):
    # Создаём dataset для RAGAS
    dataset_dict = {
        "question": [question],
        "answer": [answer],
        "contexts": [contexts]  # contexts - список строк
    }
    dataset = Dataset.from_dict(dataset_dict)
    
    # Выполняем оценку
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness],
        llm=self.llm_adapter,  # GigaChat LLM адаптер
        embeddings=self.embeddings_adapter  # GigaChat Embeddings адаптер
    )
    
    # Извлекаем score
    faithfulness_score = result["faithfulness"].iloc[0]
    return float(faithfulness_score)
```

**Адаптеры:**
- `GigaChatLLMAdapter` - LangChain-совместимая обёртка для `LLMClient`
- `GigaChatEmbeddingsAdapter` - LangChain-совместимая обёртка для `EmbeddingService`

## Интеграция в систему

### 1. Инициализация

**Файл:** `app/main.py`

```python
ragas_evaluator = RAGASEvaluator(mock_mode=True)
```

### 2. Передача в AgentController

```python
controller = AgentController(
    ...
    ragas_evaluator=ragas_evaluator,
    ...
)
```

### 3. Использование в Agent.ask()

```python
# После генерации ответа
ragas_metrics = self.ragas_evaluator.evaluate_all(
    question=query,
    answer=answer,
    contexts=contexts,
    ground_truth=None
)
metrics.update(ragas_metrics)
```

## Примеры использования

### Пример 1: Получение метрик через API

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Какой SLA у сервиса платежей?",
    "k": 3
  }'
```

**Response:**
```json
{
  "answer": "SLA сервиса платежей составляет 99.9%",
  "sources": [...],
  "metrics": {
    "faithfulness": 0.90,
    "answer_relevancy": 0.85
  }
}
```

### Пример 2: Просмотр метрик в UI

1. Откройте Streamlit UI
2. Задайте вопрос
3. В ответе будут показаны метрики:
   - **Faithfulness:** 0.90
   - **Answer Relevancy:** 0.85

### Пример 3: Использование в экспериментах

```python
# Эксперимент с разными конфигурациями
for k in [3, 5, 8]:
    response = agent.ask(query="...", k=k)
    print(f"K={k}: faithfulness={response.metrics['faithfulness']}")
```

## Переход на реальный RAGAS

### Шаг 1: Установка библиотеки

```bash
pip install ragas
```

### Шаг 2: Настройка LLM для оценки

RAGAS требует LLM для оценки метрик. Можно использовать GigaChat:

```python
from ragas.llms import LangchainLLM
from langchain_community.llms import GigaChat

# Настройка GigaChat для RAGAS
gigachat_llm = GigaChat(
    credentials=os.getenv("GIGACHAT_AUTH_KEY"),
    scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
)

ragas_llm = LangchainLLM(llm=gigachat_llm)
```

### Шаг 3: Обновление RAGASEvaluator

Реализовать методы `evaluate_faithfulness` и `evaluate_answer_relevancy` с использованием реального RAGAS:

```python
def evaluate_faithfulness(self, question, answer, contexts):
    if self.mock_mode:
        # Существующая mock логика
        ...
    else:
        # Реальная интеграция с RAGAS
        from ragas import evaluate
        from ragas.metrics import faithfulness
        
        dataset = Dataset.from_dict({
            "question": [question],
            "answer": [answer],
            "contexts": [contexts]
        })
        
        result = evaluate(
            dataset=dataset,
            metrics=[faithfulness],
            llm=self.ragas_llm,
            embeddings=self.ragas_embeddings
        )
        
        return result["faithfulness"]
```

### Шаг 4: Переключение на реальный RAGAS

**Автоматическое переключение (рекомендуется):**

В `app/main.py` уже реализована автоматическая инициализация:
- Если `RAGAS_MOCK_MODE=true` → используется mock mode
- Если `RAGAS_MOCK_MODE` не установлен или `false` → используется реальный RAGAS (если доступны адаптеры)

**Ручное переключение:**

```python
from app.evaluation.ragas_adapters import GigaChatLLMAdapter, GigaChatEmbeddingsAdapter

# Создаём адаптеры
llm_adapter = GigaChatLLMAdapter(llm_client=llm_client)
embeddings_adapter = GigaChatEmbeddingsAdapter(embedding_service=embedding_service)

# Инициализируем RAGAS evaluator
ragas_evaluator = RAGASEvaluator(
    mock_mode=False,
    llm_adapter=llm_adapter,
    embeddings_adapter=embeddings_adapter
)
```

## Целевые метрики проекта

Согласно архитектуре проекта (`docs/architecture.md`):

| Метрика | Цель |
|---------|------|
| RAG Faithfulness (RAGAS) | ≥ 0.85 |
| Answer Relevancy (RAGAS) | ≥ 0.80 |

## Тестирование

### Unit тесты

**Файл:** `tests/evaluation/test_ragas_evaluator.py`

Тесты проверяют:
- Корректность расчёта метрик в mock mode
- Обработку граничных случаев
- Интеграцию с Agent Layer

### Integration тесты

**Файл:** `tests/evaluation/test_evaluation_integration.py`

Тесты проверяют:
- Полный pipeline оценки (Precision@K + RAGAS)
- Объединение метрик в response
- Сохранение метрик в экспериментах

## Полезные ссылки

- [RAGAS Documentation](https://docs.ragas.io/)
- [RAGAS GitHub](https://github.com/explodinggradients/ragas)
- [RAGAS Metrics](https://docs.ragas.io/concepts/metrics/)

## Выводы

1. **RAGAS интегрирован** в проект и используется для оценки каждого ответа
2. **Mock mode активен** по умолчанию для быстрой работы без зависимостей
3. **Архитектура готова** для перехода на реальный RAGAS
4. **Метрики собираются** и отображаются в UI и API
5. **Метрики сохраняются** в экспериментальном цикле для сравнения конфигураций

Для production рекомендуется перейти на реальный RAGAS для более точной оценки качества ответов.

