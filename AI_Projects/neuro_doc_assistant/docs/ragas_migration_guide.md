# Руководство по переходу на реальный RAGAS

## Обзор

Проект теперь поддерживает **реальный RAGAS** для оценки качества ответов RAG-системы. Это обеспечивает более точные метрики Faithfulness и Answer Relevancy по сравнению с mock mode.

## Что изменилось

### ✅ Реализовано

1. **LangChain-совместимые адаптеры** (`app/evaluation/ragas_adapters.py`):
   - `GigaChatLLMAdapter` - обёртка для GigaChat LLM
   - `GigaChatEmbeddingsAdapter` - обёртка для GigaChat Embeddings

2. **Реальная интеграция RAGAS** (`app/evaluation/ragas_evaluator.py`):
   - Поддержка реальных вызовов RAGAS API
   - Автоматический fallback к mock mode при ошибках
   - Использование GigaChat LLM и Embeddings для оценки

3. **Автоматическая инициализация** (`app/main.py`):
   - Автоматическое определение режима работы (mock/real)
   - Настройка через переменную окружения `RAGAS_MOCK_MODE`

## Быстрый старт

### Шаг 1: Установка зависимостей

Убедитесь, что установлены все необходимые пакеты:

```bash
pip install ragas langchain-core langchain-community
```

Или используйте requirements.txt:

```bash
pip install -r requirements.txt
```

### Шаг 2: Настройка переменных окружения

В файле `.env`:

```env
# Для использования реального RAGAS (рекомендуется)
RAGAS_MOCK_MODE=false

# Для использования mock mode (для тестирования)
# RAGAS_MOCK_MODE=true
```

**Важно:** Для работы реального RAGAS также нужны:
- `GIGACHAT_AUTH_KEY` - для LLM и Embeddings
- `GIGACHAT_SCOPE` - scope для OAuth 2.0

### Шаг 3: Проверка работы

1. **Запустите API:**
   ```bash
   python app/main.py
   ```

2. **Отправьте тестовый запрос:**
   ```bash
   curl -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"query": "Что такое безопасность?"}'
   ```

3. **Проверьте метрики в ответе:**
   ```json
   {
     "answer": "...",
     "metrics": {
       "faithfulness": 0.85,
       "answer_relevancy": 0.82
     }
   }
   ```

## Режимы работы

### Реальный RAGAS (по умолчанию)

**Когда используется:**
- `RAGAS_MOCK_MODE=false` или не установлен
- Установлена библиотека `ragas`
- Настроены GigaChat API ключи

**Преимущества:**
- ✅ Точная оценка через LLM
- ✅ Соответствие стандартам RAGAS
- ✅ Более надёжные метрики

**Недостатки:**
- ⚠️ Требует вызовов LLM (дополнительное время и API запросы)
- ⚠️ Требует интернет-соединения

### Mock Mode

**Когда используется:**
- `RAGAS_MOCK_MODE=true`
- Или библиотека `ragas` не установлена
- Или не предоставлены адаптеры LLM/Embeddings

**Преимущества:**
- ✅ Быстрая работа (без вызовов LLM)
- ✅ Не требует интернета
- ✅ Подходит для тестирования

**Недостатки:**
- ❌ Упрощённая логика оценки
- ❌ Менее точные метрики

## Архитектура

### Компоненты

```
┌─────────────────┐
│  AgentController│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ RAGASEvaluator  │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────┐ ┌──────────────┐
│  Mock   │ │  Real RAGAS  │
│  Mode   │ │              │
└─────────┘ └──────┬───────┘
                   │
            ┌──────┴──────┐
            │             │
            ▼             ▼
    ┌─────────────┐ ┌──────────────┐
    │ LLM Adapter │ │Embeddings    │
    │ (GigaChat)  │ │Adapter       │
    └─────────────┘ │(GigaChat)    │
                    └──────────────┘
```

### Поток данных

1. **Agent получает запрос** → генерирует ответ через LLM
2. **Agent извлекает контексты** → retrieved chunks из Qdrant
3. **RAGASEvaluator оценивает:**
   - **Mock mode:** упрощённая проверка текста
   - **Real RAGAS:** вызов RAGAS API с LLM и Embeddings
4. **Метрики возвращаются** в ответе API

## Настройка

### Переключение между режимами

**Включить реальный RAGAS:**
```env
RAGAS_MOCK_MODE=false
```

**Включить mock mode:**
```env
RAGAS_MOCK_MODE=true
```

### Программная настройка

Если нужно настроить программно (например, в тестах):

```python
from app.evaluation.ragas_evaluator import RAGASEvaluator
from app.evaluation.ragas_adapters import GigaChatLLMAdapter, GigaChatEmbeddingsAdapter

# Реальный RAGAS
llm_adapter = GigaChatLLMAdapter(llm_client=llm_client)
embeddings_adapter = GigaChatEmbeddingsAdapter(embedding_service=embedding_service)

ragas_evaluator = RAGASEvaluator(
    mock_mode=False,
    llm_adapter=llm_adapter,
    embeddings_adapter=embeddings_adapter
)

# Mock mode
ragas_evaluator = RAGASEvaluator(mock_mode=True)
```

## Устранение неполадок

### Проблема: "RAGAS not available"

**Причина:** Библиотека `ragas` не установлена

**Решение:**
```bash
pip install ragas langchain-core langchain-community
```

### Проблема: "LLM or Embeddings adapter not provided"

**Причина:** Адаптеры не переданы в RAGASEvaluator

**Решение:** Убедитесь, что в `app/main.py` создаются адаптеры:
```python
llm_adapter = GigaChatLLMAdapter(llm_client=llm_client)
embeddings_adapter = GigaChatEmbeddingsAdapter(embedding_service=embedding_service)
```

### Проблема: Ошибки при оценке

**Причина:** Проблемы с GigaChat API или форматом данных

**Решение:**
1. Проверьте статус GigaChat API в UI
2. Убедитесь, что `GIGACHAT_AUTH_KEY` установлен
3. Проверьте логи на наличие ошибок

**Fallback:** При ошибках RAGAS автоматически возвращает значение 0.75 (средний score)

### Проблема: Медленная работа

**Причина:** Реальный RAGAS требует вызовов LLM

**Решение:**
- Используйте mock mode для тестирования: `RAGAS_MOCK_MODE=true`
- Для production реальный RAGAS даёт более точные метрики

## Целевые метрики

Согласно архитектуре проекта:

| Метрика | Цель | Mock Mode | Real RAGAS |
|---------|------|-----------|------------|
| Faithfulness | ≥ 0.85 | 0.50-0.90 | 0.0-1.0 (точная) |
| Answer Relevancy | ≥ 0.80 | 0.60-0.85 | 0.0-1.0 (точная) |

## Дополнительная информация

- [Документация RAGAS](https://docs.ragas.io/)
- [Использование RAGAS в проекте](docs/ragas_usage.md)
- [Архитектура проекта](docs/architecture.md)

## Выводы

✅ **Реальный RAGAS реализован и готов к использованию**

- Автоматическое переключение между режимами
- Fallback к mock mode при ошибках
- Полная интеграция с GigaChat API
- Готово к production использованию

**Рекомендация:** Используйте реальный RAGAS в production для точных метрик, mock mode - для тестирования и разработки.

