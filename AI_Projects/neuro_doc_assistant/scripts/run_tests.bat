@echo off
REM Скрипт для запуска всех тестов проекта с логированием результатов (Windows)
REM Использование: scripts\run_tests.bat [module_name]

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
cd /d "%PROJECT_ROOT%"

set LOG_DIR=tests\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%_%datetime:~8,2%-%datetime:~10,2%-%datetime:~12,2%

if "%1"=="" (
    REM Запуск всех тестов
    set LOG_FILE=%LOG_DIR%\test_results_%TIMESTAMP%.txt
    set JUNIT_XML=%LOG_DIR%\junit.xml
    set HTML_REPORT=%LOG_DIR%\report.html
    
    echo ==================================================================================
    echo Запуск всех тестов проекта Neuro_Doc_Assistant
    echo ==================================================================================
    echo Время запуска: %date% %time%
    echo Лог файл: %LOG_FILE%
    echo JUnit XML: %JUNIT_XML%
    echo ----------------------------------------------------------------------------------
    echo.
    
    python -m pytest tests\ ^
        -v ^
        --tb=short ^
        --strict-markers ^
        --junitxml=%JUNIT_XML% ^
        --log-file=%LOG_FILE% ^
        --log-file-level=INFO ^
        --capture=no ^
        --html=%HTML_REPORT% ^
        --self-contained-html > %LOG_FILE% 2>&1
    
    set EXIT_CODE=%ERRORLEVEL%
    
    echo.
    echo ==================================================================================
    echo ИТОГИ ТЕСТИРОВАНИЯ
    echo ==================================================================================
    echo Exit code: !EXIT_CODE!
    echo Лог сохранён в: %LOG_FILE%
    echo JUnit XML сохранён в: %JUNIT_XML%
    echo HTML отчет сохранён в: %HTML_REPORT%
    
    if !EXIT_CODE! equ 0 (
        echo ✅ Все тесты прошли успешно!
    ) else (
        echo ❌ Некоторые тесты провалились. Проверьте лог файл для деталей.
    )
    
    echo ==================================================================================
    exit /b !EXIT_CODE!
) else (
    REM Запуск тестов для конкретного модуля
    set MODULE=%1
    set LOG_FILE=%LOG_DIR%\test_results_%MODULE%_%TIMESTAMP%.txt
    
    echo Запуск тестов для модуля: %MODULE%
    echo Лог файл: %LOG_FILE%
    echo ----------------------------------------------------------------------------------
    
    python -m pytest tests\%MODULE%\ ^
        -v ^
        --tb=short ^
        --log-file=%LOG_FILE% ^
        --log-file-level=INFO > %LOG_FILE% 2>&1
    
    exit /b %ERRORLEVEL%
)

