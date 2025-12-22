#!/bin/bash
# Скрипт для запуска Streamlit UI (Linux/Mac)

# Получаем директорию скрипта и переходим в корневую директорию проекта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

# Устанавливаем PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT"

echo "========================================"
echo "Запуск Streamlit UI для Neuro_Doc_Assistant"
echo "========================================"
echo

# Проверка доступности API на портах 8000 и 8001
API_PORT=8000
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 || nc -z localhost 8000 2>/dev/null; then
    echo "[OK] API найден на порту 8000"
    API_PORT=8000
elif lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1 || nc -z localhost 8001 2>/dev/null; then
    echo "[OK] API найден на порту 8001"
    API_PORT=8001
else
    echo "[ВНИМАНИЕ] API не найден на портах 8000 и 8001"
    echo "Убедитесь, что FastAPI сервер запущен!"
    echo
    echo "Для запуска API используйте:"
    echo "  ./scripts/start_project.sh (опция 2)"
    echo "  или"
    echo "  python app/main.py"
    echo
    exit 1
fi

# Устанавливаем API_BASE_URL, если не установлен
if [ -z "$API_BASE_URL" ]; then
    export API_BASE_URL="http://localhost:$API_PORT"
    echo "[OK] API_BASE_URL установлен: $API_BASE_URL"
else
    echo "[OK] Используется API_BASE_URL: $API_BASE_URL"
fi
echo

# Активация виртуального окружения
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Запуск Streamlit приложения
echo "Запуск Streamlit UI..."
echo "UI будет доступен по адресу: http://localhost:8501"
echo "Для остановки нажмите Ctrl+C"
echo
streamlit run app/ui/streamlit_app.py --server.port 8501 --server.address localhost
