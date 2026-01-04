@echo off
REM Скрипт для пошагового запуска проекта Neuro_Doc_Assistant
REM Автор: Neuro_Doc_Assistant Team
REM Дата: 2024-12-19

setlocal enabledelayedexpansion

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
REM Переходим в корневую директорию проекта
cd /d "%~dp0.."
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ОШИБКА] Не удалось активировать виртуальное окружение
    pause
    exit /b 1
)
REM Устанавливаем PYTHONPATH
set PYTHONPATH=%CD%
echo [OK] Виртуальное окружение активировано
echo [OK] PYTHONPATH установлен: %CD%
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
echo 5. Запустить Full Stack (FastAPI + Streamlit)
echo 6. Выход
echo.
set /p choice="Выберите действие (1-6): "

REM Удаляем пробелы и другие невидимые символы из переменной choice
for /f "delims=" %%i in ("!choice!") do set choice=%%i
set choice=!choice: =!
set choice=!choice: =!

REM Переход к соответствующей метке в зависимости от выбора
if /i "!choice!"=="1" goto :option1
if /i "!choice!"=="2" goto :option2
if /i "!choice!"=="3" goto :option3
if /i "!choice!"=="4" goto :option4
if /i "!choice!"=="5" goto :option5
if /i "!choice!"=="6" goto :option6

echo [ОШИБКА] Неверный выбор: [!choice!]
pause
goto :end

:option1
echo.
echo Запуск тестов...
cd /d "%~dp0.."
set PYTHONPATH=%CD%
python -m pytest tests/ -v
pause
goto :end

:option2
echo.
echo Запуск FastAPI сервера...
cd /d "%~dp0.."
set PYTHONPATH=%CD%

REM Проверка доступности порта 8000
netstat -ano | findstr :8000 >nul 2>&1
if not errorlevel 1 (
    echo [ВНИМАНИЕ] Порт 8000 уже занят!
    echo.
    echo Варианты решения:
    echo 1. Остановить процесс, занимающий порт 8000
    echo 2. Использовать другой порт (например, 8001)
    echo.
    set /p port_choice="Выберите вариант (1/2) или нажмите Enter для использования порта 8001: "
    if "!port_choice!"=="1" (
        echo.
        echo Поиск процесса на порту 8000...
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
            echo Остановка процесса с PID %%a...
            taskkill /F /PID %%a >nul 2>&1
        )
        echo [OK] Процесс остановлен. Запускаю сервер...
        echo.
    ) else (
        echo.
        echo Использую порт 8001...
        set API_PORT=8001
    )
) else (
    set API_PORT=8000
)

if "!API_PORT!"=="" set API_PORT=8000
echo.
echo API будет доступен по адресу: http://localhost:!API_PORT!
echo Документация: http://localhost:!API_PORT!/docs
echo.
echo Для остановки нажмите Ctrl+C
echo.
REM Устанавливаем переменную окружения для Python (важно: без пробелов вокруг =)
REM Передаем переменную напрямую в команду Python, чтобы она имела приоритет над .env
echo [DEBUG] API_PORT установлен: !API_PORT!
REM Запускаем Python с передачей порта через переменную окружения
set API_PORT=!API_PORT! && python app/main.py
pause
goto :end

:option3
echo.
echo Запуск Streamlit UI...
cd /d "%~dp0.."
set PYTHONPATH=%CD%

REM Автоматическое определение порта API
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
    )
) else (
    echo [OK] API найден на порту 8000
)

REM Устанавливаем API_BASE_URL для Streamlit
set API_BASE_URL=http://localhost:%API_PORT%
echo [OK] API_BASE_URL установлен: %API_BASE_URL%
echo UI будет доступен по адресу: http://localhost:8501
echo.
echo Для остановки нажмите Ctrl+C
echo.
streamlit run app/ui/streamlit_app.py
pause
goto :end

:option4
echo.
echo Запуск всех тестов...
cd /d "%~dp0.."
set PYTHONPATH=%CD%
python scripts/run_tests.py all
pause
goto :end

:option5
echo.
echo Запуск Full Stack (FastAPI + Streamlit)...
cd /d "%~dp0.."
set PYTHONPATH=%CD%
python scripts/start_full_stack.py
pause
goto :end

:option6
echo Выход...
goto :end

:end
endlocal

