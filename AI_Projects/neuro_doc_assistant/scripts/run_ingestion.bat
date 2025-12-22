@echo off
REM Скрипт для запуска Ingestion Pipeline (Windows)

echo ========================================
echo Запуск Ingestion Pipeline
echo ========================================
echo.

REM Переходим в корневую директорию проекта
cd /d "%~dp0.."
set PYTHONPATH=%CD%

REM Активация виртуального окружения (если существует)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Запуск ingestion pipeline
python scripts/run_ingestion.py

pause

