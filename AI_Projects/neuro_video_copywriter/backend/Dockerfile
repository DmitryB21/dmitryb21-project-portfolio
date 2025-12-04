# syntax=docker/dockerfile:1.5

FROM python:3.11-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=600 \
    PYTHONPATH=/app

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Установка Poetry
RUN pip install --upgrade pip && pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry config installer.max-workers 4

# Копирование файлов зависимостей (для лучшего кеширования)
COPY pyproject.toml poetry.lock /app/

# Установка зависимостей
# Примечание: openai-whisper требует PyTorch (~2GB), что значительно увеличивает время сборки
# Для быстрой разработки используйте Dockerfile.fast или API транскрибацию
RUN poetry install --only main --no-interaction --no-ansi || \
    (echo "First attempt failed, retrying in 30 seconds..." && sleep 30 && poetry install --only main --no-interaction --no-ansi) || \
    (echo "Second attempt failed, retrying in 60 seconds..." && sleep 60 && poetry install --only main --no-interaction --no-ansi)

# Копирование кода приложения
COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
