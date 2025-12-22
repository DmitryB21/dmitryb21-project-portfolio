@echo off
REM Скрипт для запуска Streamlit UI (Windows)

echo ========================================
echo Запуск Streamlit UI для Neuro_Doc_Assistant
echo ========================================
echo.

REM Переходим в корневую директорию проекта
cd /d "%~dp0.."
set PYTHONPATH=%CD%

REM Проверка доступности API на портах 8000 и 8001
set API_PORT=8000
netstat -ano | findstr :8000 >nul 2>&1
if errorlevel 1 (
    netstat -ano | findstr :8001 >nul 2>&1
    if not errorlevel 1 (
        set API_PORT=8001
        echo [OK] API найден на порту 8001
    ) else (
        echo [ВНИМАНИЕ] API не найден на портах 8000 и 8001
        echo Убедитесь, что FastAPI сервер запущен!
        echo.
        echo Для запуска API используйте:
        echo   scripts\start_project.bat (опция 2)
        echo   или
        echo   python app/main.py
        echo.
        pause
        exit /b 1
    )
) else (
    echo [OK] API найден на порту 8000
)

REM Устанавливаем API_BASE_URL, если не установлен
if "%API_BASE_URL%"=="" (
    set API_BASE_URL=http://localhost:%API_PORT%
    echo [OK] API_BASE_URL установлен: %API_BASE_URL%
) else (
    echo [OK] Используется API_BASE_URL: %API_BASE_URL%
)
echo.

REM Запуск Streamlit
echo Запуск Streamlit UI...
echo UI будет доступен по адресу: http://localhost:8501
echo Для остановки нажмите Ctrl+C
echo.
streamlit run app/ui/streamlit_app.py --server.port 8501 --server.address localhost

pause

