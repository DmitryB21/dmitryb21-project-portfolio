# Переход на реальный RAGAS

## Обзор

Проект поддерживает два режима работы RAGAS:
- **Mock Mode** - упрощённая оценка без реальных вызовов LLM (быстро, для тестирования)
- **Real RAGAS** - полная интеграция с библиотекой RAGAS и GigaChat API (точная оценка)

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install ragas langchain-core langchain-community
```

Или обновите зависимости из `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

В файле `.env` установите:

```env
# Для использования реального RAGAS (по умолчанию)
RAGAS_MOCK_MODE=false

# Или для mock mode (быстрая работа без API)
RAGAS_MOCK_MODE=true
```

### 3. Настройка GigaChat API

Для работы реального RAGAS требуются GigaChat API ключи:

```env
GIGACHAT_AUTH_KEY=your_base64_encoded_client_id_client_secret
GIGACHAT_SCOPE=GIGACHAT_API_PERS
```

**Примечание:** Если `GIGACHAT_AUTH_KEY` не установлен, система автоматически переключится на mock mode для GigaChat, но RAGAS всё равно будет использовать реальные вызовы (если `RAGAS_MOCK_MODE=false`).

## Как это работает

### Автоматическое переключение

В `app/main.py` реализована автоматическая инициализация:

```python
# Определяем, использовать ли реальный RAGAS или mock mode
use_ragas_mock = os.getenv("RAGAS_MOCK_MODE", "false").lower() == "true"

if use_ragas_mock:
    ragas_evaluator = RAGASEvaluator(mock_mode=True)
else:
    # Создаём адаптеры для RAGAS
    llm_adapter = GigaChatLLMAdapter(llm_client=llm_client)
    embeddings_adapter = GigaChatEmbeddingsAdapter(embedding_service=embedding_service)
    
    # Инициализируем RAGAS evaluator с реальными адаптерами
    ragas_evaluator = RAGASEvaluator(
        mock_mode=False,
        llm_adapter=llm_adapter,
        embeddings_adapter=embeddings_adapter
    )
```

### Адаптеры

Для интеграции с RAGAS созданы LangChain-совместимые адаптеры:

- **`GigaChatLLMAdapter`** - обёртка для `LLMClient` (GigaChat API)
- **`GigaChatEmbeddingsAdapter`** - обёртка для `EmbeddingService` (GigaChat Embeddings API)

Эти адаптеры позволяют использовать существующие GigaChat клиенты с RAGAS без дополнительной настройки.

## Тестирование

Для проверки интеграции запустите:

```bash
python scripts/test_ragas_integration.py
```

Скрипт проверит:
- ✅ Импорт всех необходимых модулей
- ✅ Создание адаптеров
- ✅ Инициализацию RAGASEvaluator
- ✅ Выполнение оценки метрик (если доступны API ключи)

## Метрики

Реальный RAGAS рассчитывает следующие метрики:

### Faithfulness
- **Описание:** Насколько ответ основан на предоставленном контексте
- **Цель проекта:** ≥ 0.85
- **Диапазон:** 0.0 - 1.0

### Answer Relevancy
- **Описание:** Насколько ответ релевантен вопросу
- **Цель проекта:** ≥ 0.80
- **Диапазон:** 0.0 - 1.0

## Обработка ошибок

Система автоматически обрабатывает ошибки:

1. **Если RAGAS не установлен** → автоматический переход на mock mode
2. **Если адаптеры не предоставлены** → автоматический переход на mock mode
3. **Если произошла ошибка при оценке** → fallback к значению 0.75

## Примеры использования

### В коде

```python
from app.evaluation.ragas_evaluator import RAGASEvaluator
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

# Используем для оценки
metrics = ragas_evaluator.evaluate_all(
    question="Какой SLA у сервиса?",
    answer="SLA составляет 99.9%",
    contexts=["SLA сервиса составляет 99.9%", "Время отклика не более 200мс"]
)

print(f"Faithfulness: {metrics['faithfulness']:.3f}")
print(f"Answer Relevancy: {metrics['answer_relevancy']:.3f}")
```

### В API Response

Метрики автоматически включаются в ответ API:

```json
{
  "answer": "SLA сервиса составляет 99.9%",
  "metrics": {
    "faithfulness": 1.0,
    "answer_relevancy": 0.504
  }
}
```

## Производительность

- **Mock Mode:** ~0.001 секунды на оценку
- **Real RAGAS:** ~5-10 секунд на оценку (зависит от доступности GigaChat API)

## Рекомендации

1. **Для разработки и тестирования:** Используйте `RAGAS_MOCK_MODE=true`
2. **Для production:** Используйте `RAGAS_MOCK_MODE=false` с настроенными GigaChat API ключами
3. **Для отладки:** Проверьте логи на наличие ошибок при оценке

## Дополнительная информация

- [Документация RAGAS](https://docs.ragas.io/)
- [Документация по использованию RAGAS в проекте](docs/ragas_usage.md)
- [Архитектура системы](docs/architecture.md)

