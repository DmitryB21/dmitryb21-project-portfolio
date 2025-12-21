@echo off
REM Скрипт для запуска Streamlit UI (Windows)

echo ========================================
echo Запуск Streamlit UI для Neuro_Doc_Assistant
echo ========================================
echo.

REM Проверка переменной окружения API_BASE_URL
if "%API_BASE_URL%"=="" (
    echo API_BASE_URL не установлен, используется значение по умолчанию: http://localhost:8000
    echo Для изменения установите переменную: set API_BASE_URL=http://your-api-url:port
    echo.
)

REM Запуск Streamlit
streamlit run app/ui/streamlit_app.py --server.port 8501 --server.address localhost

pause

