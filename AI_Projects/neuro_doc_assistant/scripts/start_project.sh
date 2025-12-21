#!/bin/bash
# Скрипт для пошагового запуска проекта Neuro_Doc_Assistant
# Автор: Neuro_Doc_Assistant Team
# Дата: 2024-12-19

set -e

echo "========================================"
echo "Neuro_Doc_Assistant - Запуск проекта"
echo "========================================"
echo

# Шаг 1: Проверка виртуального окружения
echo "[Шаг 1/5] Проверка виртуального окружения..."
if [ ! -d "venv" ]; then
    echo "[ОШИБКА] Виртуальное окружение не найдено!"
    echo "Создайте его командой: python -m venv venv"
    exit 1
fi
echo "[OK] Виртуальное окружение найдено"
echo

# Шаг 2: Активация виртуального окружения
echo "[Шаг 2/5] Активация виртуального окружения..."
source venv/bin/activate
echo "[OK] Виртуальное окружение активировано"
echo

# Шаг 3: Проверка .env файла
echo "[Шаг 3/5] Проверка конфигурации (.env)..."
if [ ! -f ".env" ]; then
    echo "[ВНИМАНИЕ] Файл .env не найден!"
    if [ -f ".env.example" ]; then
        echo "Создаю .env из .env.example..."
        cp .env.example .env
        echo "[OK] Файл .env создан. Пожалуйста, заполните его реальными значениями!"
        echo
        read -p "Нажмите Enter после настройки .env..."
    else
        echo "[ОШИБКА] Файл .env.example не найден!"
        exit 1
    fi
fi
echo "[OK] Файл .env найден"
echo

# Шаг 4: Проверка зависимостей
echo "[Шаг 4/5] Проверка зависимостей..."
if ! python -c "import fastapi, uvicorn, streamlit, qdrant_client" 2>/dev/null; then
    echo "[ВНИМАНИЕ] Некоторые зависимости не установлены"
    echo "Устанавливаю зависимости..."
    pip install -r requirements.txt
fi
echo "[OK] Зависимости установлены"
echo

# Шаг 5: Меню выбора действия
echo "[Шаг 5/5] Выбор действия:"
echo
echo "1. Запустить тесты"
echo "2. Запустить FastAPI сервер"
echo "3. Запустить Streamlit UI"
echo "4. Запустить все тесты и показать статистику"
echo "5. Выход"
echo
read -p "Выберите действие (1-5): " choice

case $choice in
    1)
        echo
        echo "Запуск тестов..."
        python -m pytest tests/ -v
        ;;
    2)
        echo
        echo "Запуск FastAPI сервера..."
        echo "API будет доступен по адресу: http://localhost:8000"
        echo "Документация: http://localhost:8000/docs"
        echo
        echo "Для остановки нажмите Ctrl+C"
        echo
        python app/main.py
        ;;
    3)
        echo
        echo "Запуск Streamlit UI..."
        echo "UI будет доступен по адресу: http://localhost:8501"
        echo
        echo "Для остановки нажмите Ctrl+C"
        echo
        streamlit run app/ui/streamlit_app.py
        ;;
    4)
        echo
        echo "Запуск всех тестов..."
        python scripts/run_tests.py all
        ;;
    5)
        echo "Выход..."
        exit 0
        ;;
    *)
        echo "[ОШИБКА] Неверный выбор!"
        exit 1
        ;;
esac

