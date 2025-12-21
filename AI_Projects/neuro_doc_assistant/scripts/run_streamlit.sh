#!/bin/bash
# Скрипт для запуска Streamlit UI (Linux/Mac)

echo "========================================"
echo "Запуск Streamlit UI для Neuro_Doc_Assistant"
echo "========================================"
echo ""

# Проверка переменной окружения API_BASE_URL
if [ -z "$API_BASE_URL" ]; then
    echo "API_BASE_URL не установлен, используется значение по умолчанию: http://localhost:8000"
    echo "Для изменения установите переменную: export API_BASE_URL=http://your-api-url:port"
    echo ""
fi

# Запуск Streamlit
streamlit run app/ui/streamlit_app.py --server.port 8501 --server.address localhost

