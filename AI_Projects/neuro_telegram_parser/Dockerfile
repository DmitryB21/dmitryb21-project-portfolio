# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Копируем Docker конфигурацию (если существует)
RUN if [ -f "config.ini.docker" ]; then cp config.ini.docker config.ini; fi

# Создаем директории для данных
RUN mkdir -p /app/data/qdrant /app/data/models /app/data/sessions /app/artifacts

# Устанавливаем переменные окружения для Hugging Face
ENV HF_HOME=/app/data/models
ENV TRANSFORMERS_CACHE=/app/data/models

# Открываем порт для Flask
EXPOSE 5000

# Команда по умолчанию (будет переопределена в docker-compose)
CMD ["python", "app.py"]

