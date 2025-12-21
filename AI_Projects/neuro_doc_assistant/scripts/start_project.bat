@echo off
REM Скрипт для пошагового запуска проекта Neuro_Doc_Assistant
REM Автор: Neuro_Doc_Assistant Team
REM Дата: 2024-12-19

setlocal

echo ========================================
echo Neuro_Doc_Assistant - Запуск проекта
echo ========================================
echo.

REM Шаг 1: Проверка виртуального окружения
echo [Шаг 1/5] Проверка виртуального окружения...
if not exist "venv\Scripts\activate.bat" (
    echo [ОШИБКА] Виртуальное окружение не найдено!
    echo Создайте его командой: python -m venv venv
    pause
    exit /b 1
)
echo [OK] Виртуальное окружение найдено
echo.

REM Шаг 2: Активация виртуального окружения
echo [Шаг 2/5] Активация виртуального окружения...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ОШИБКА] Не удалось активировать виртуальное окружение
    pause
    exit /b 1
)
echo [OK] Виртуальное окружение активировано
echo.

REM Шаг 3: Проверка .env файла
echo [Шаг 3/5] Проверка конфигурации (.env)...
if not exist ".env" (
    echo [ВНИМАНИЕ] Файл .env не найден!
    if exist ".env.example" (
        echo Создаю .env из .env.example...
        copy .env.example .env
        echo [OK] Файл .env создан. Пожалуйста, заполните его реальными значениями!
        echo.
        echo Нажмите любую клавишу после настройки .env...
        pause > nul
    ) else (
        echo [ОШИБКА] Файл .env.example не найден!
        pause
        exit /b 1
    )
)
echo [OK] Файл .env найден
echo.

REM Шаг 4: Проверка зависимостей
echo [Шаг 4/5] Проверка зависимостей...
python -c "import fastapi, uvicorn, streamlit, qdrant_client" 2>nul
if errorlevel 1 (
    echo [ВНИМАНИЕ] Некоторые зависимости не установлены
    echo Устанавливаю зависимости...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось установить зависимости
        pause
        exit /b 1
    )
)
echo [OK] Зависимости установлены
echo.

REM Шаг 5: Меню выбора действия
echo [Шаг 5/5] Выбор действия:
echo.
echo 1. Запустить тесты
echo 2. Запустить FastAPI сервер
echo 3. Запустить Streamlit UI
echo 4. Запустить все тесты и показать статистику
echo 5. Выход
echo.
set /p choice="Выберите действие (1-5): "

if "%choice%"=="1" (
    echo.
    echo Запуск тестов...
    python -m pytest tests/ -v
    pause
    goto :end
)

if "%choice%"=="2" (
    echo.
    echo Запуск FastAPI сервера...
    echo API будет доступен по адресу: http://localhost:8000
    echo Документация: http://localhost:8000/docs
    echo.
    echo Для остановки нажмите Ctrl+C
    echo.
    python app/main.py
    pause
    goto :end
)

if "%choice%"=="3" (
    echo.
    echo Запуск Streamlit UI...
    echo UI будет доступен по адресу: http://localhost:8501
    echo.
    echo Для остановки нажмите Ctrl+C
    echo.
    streamlit run app/ui/streamlit_app.py
    pause
    goto :end
)

if "%choice%"=="4" (
    echo.
    echo Запуск всех тестов...
    python scripts/run_tests.py all
    pause
    goto :end
)

if "%choice%"=="5" (
    echo Выход...
    goto :end
)

echo [ОШИБКА] Неверный выбор!
pause

:end
endlocal

