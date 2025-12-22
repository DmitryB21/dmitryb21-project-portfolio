#!/bin/bash
# Скрипт для запуска Ingestion Pipeline (Linux/Mac)

# Получаем директорию скрипта и переходим в корневую директорию проекта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

# Устанавливаем PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT"

# Активация виртуального окружения (если существует)
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Запуск ingestion pipeline
python scripts/run_ingestion.py

