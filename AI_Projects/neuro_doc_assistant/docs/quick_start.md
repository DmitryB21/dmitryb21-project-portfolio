# Quick Start Guide - Neuro_Doc_Assistant

Быстрый старт проекта для локальной разработки и тестирования.

## Предварительные требования

- Python >= 3.8
- Qdrant (опционально, для production; для тестов используется mock)
- GigaChat API ключ (опционально, для production; для тестов используется mock mode)

## Шаг 1: Клонирование и настройка окружения

```bash
# Клонирование репозитория (если еще не сделано)
git clone <repository_url>
cd neuro_doc_assistant

# Создание виртуального окружения
python -m venv venv

# Активация виртуального окружения
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

## Шаг 2: Настройка переменных окружения

```bash
# Создание .env файла из примера
cp .env.example .env

# Редактирование .env файла (заполните реальными значениями)
# Для тестирования можно оставить значения по умолчанию (mock mode)
```

**Важно**: Для работы с реальным GigaChat API и Qdrant укажите реальные значения в `.env`.

## Шаг 3: Запуск Qdrant

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

## Шаг 4: Загрузка документов в Qdrant (Ingestion Pipeline)

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
- **Создаст коллекцию `neuro_docs` в Qdrant** (если не существует)
- Индексирует все чанки в Qdrant

**Важно:** Убедитесь, что:
- Qdrant запущен и доступен
- В директории `data/NeuroDoc_Data/` есть документы (MD файлы)
- `GIGACHAT_API_KEY` настроен в `.env` (или используется mock mode)

## Шаг 5: Запуск проекта

### Вариант 1: Использование скрипта запуска (рекомендуется)

```bash
# Windows:
scripts\start_project.bat

# Linux/Mac:
chmod +x scripts/start_project.sh
./scripts/start_project.sh
```

Скрипт предложит выбрать действие:
1. Запустить тесты
2. Запустить FastAPI сервер
3. Запустить Streamlit UI
4. Запустить все тесты и показать статистику

### Вариант 2: Ручной запуск

#### Запуск тестов

```bash
# Все тесты
python -m pytest tests/ -v

# Конкретный модуль
python -m pytest tests/agent/ -v

# С использованием скрипта
python scripts/run_tests.py all
```

#### Запуск FastAPI сервера

```bash
# Через uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Или через Python
python app/main.py
```

API будет доступен по адресу:
- Основной: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

#### Запуск Streamlit UI

```bash
# Через streamlit
streamlit run app/ui/streamlit_app.py

# Или через скрипт
# Windows:
scripts\run_streamlit.bat
# Linux/Mac:
./scripts/run_streamlit.sh
```

UI будет доступен по адресу: `http://localhost:8501`

## Шаг 4: Проверка работы

### Тестирование API

```bash
# Проверка здоровья сервиса
curl http://localhost:8000/health

# Запрос к агенту
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "Какой SLA у сервиса платежей?", "k": 3}'
```

### Тестирование через UI

1. Откройте браузер: `http://localhost:8501`
2. Введите вопрос в поле ввода
3. Нажмите Enter или кнопку отправки
4. Просмотрите ответ, источники и метрики

## Шаг 5: Запуск экспериментов (опционально)

```bash
# Минимальный набор экспериментов
python scripts/run_experiments.py --query "Какой SLA у сервиса платежей?" --configs minimal

# Полный набор экспериментов
python scripts/run_experiments.py --queries scripts/sample_queries.txt --configs all --output results.json
```

## Troubleshooting

### Проблема: Модуль не найден

```bash
# Убедитесь, что виртуальное окружение активировано
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Переустановите зависимости
pip install -r requirements.txt
```

### Проблема: Qdrant недоступен

Для тестов Qdrant не требуется (используется mock). Для production:
- Установите Qdrant: https://qdrant.tech/documentation/quick-start/
- Укажите правильные `QDRANT_HOST` и `QDRANT_PORT` в `.env`

### Проблема: GigaChat API ошибки

Для тестов используется mock mode. Для production:
- Получите API ключ: https://developers.sber.ru/gigachat
- Укажите `GIGACHAT_API_KEY` в `.env`
- Убедитесь, что `GIGACHAT_MOCK_MODE=false` в `.env`

### Проблема: Порт уже занят

Измените порт в `.env` или в коде:
- FastAPI: `API_PORT=8001`
- Streamlit: измените в `app/ui/streamlit_app.py` или через параметры запуска

## Следующие шаги

- Прочитайте `README.md` для полного описания проекта
- Изучите `docs/architecture.md` для понимания архитектуры
- Посмотрите `docs/tasktracker.md` для отслеживания прогресса
- Запустите тесты: `python scripts/run_tests.py all`

## Полезные команды

```bash
# Активация виртуального окружения
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Запуск всех тестов
python scripts/run_tests.py all

# Запуск тестов конкретного модуля
python scripts/run_tests.py agent

# Проверка кода (если установлен)
pylint app/
black app/

# Просмотр логов тестов
cat tests/logs/test_results_*.txt
```

