#!/bin/bash
# Скрипт для запуска всех тестов проекта с логированием результатов
# Использование: ./scripts/run_tests.sh [module_name]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="tests/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

if [ -z "$1" ]; then
    # Запуск всех тестов
    LOG_FILE="$LOG_DIR/test_results_$TIMESTAMP.txt"
    JUNIT_XML="$LOG_DIR/junit.xml"
    HTML_REPORT="$LOG_DIR/report.html"
    
    echo "=================================================================================="
    echo "Запуск всех тестов проекта Neuro_Doc_Assistant"
    echo "=================================================================================="
    echo "Время запуска: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Лог файл: $LOG_FILE"
    echo "JUnit XML: $JUNIT_XML"
    echo "----------------------------------------------------------------------------------"
    echo ""
    
    python -m pytest tests/ \
        -v \
        --tb=short \
        --strict-markers \
        --junitxml="$JUNIT_XML" \
        --log-file="$LOG_FILE" \
        --log-file-level=INFO \
        --capture=no \
        --html="$HTML_REPORT" \
        --self-contained-html 2>&1 | tee "$LOG_FILE"
    
    EXIT_CODE=${PIPESTATUS[0]}
    
    echo ""
    echo "=================================================================================="
    echo "ИТОГИ ТЕСТИРОВАНИЯ"
    echo "=================================================================================="
    echo "Exit code: $EXIT_CODE"
    echo "Лог сохранён в: $LOG_FILE"
    echo "JUnit XML сохранён в: $JUNIT_XML"
    echo "HTML отчет сохранён в: $HTML_REPORT"
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Все тесты прошли успешно!"
    else
        echo "❌ Некоторые тесты провалились. Проверьте лог файл для деталей."
    fi
    
    echo "=================================================================================="
    exit $EXIT_CODE
else
    # Запуск тестов для конкретного модуля
    MODULE=$1
    LOG_FILE="$LOG_DIR/test_results_${MODULE}_$TIMESTAMP.txt"
    
    echo "Запуск тестов для модуля: $MODULE"
    echo "Лог файл: $LOG_FILE"
    echo "----------------------------------------------------------------------------------"
    
    python -m pytest "tests/$MODULE/" \
        -v \
        --tb=short \
        --log-file="$LOG_FILE" \
        --log-file-level=INFO \
        2>&1 | tee "$LOG_FILE"
    
    exit ${PIPESTATUS[0]}
fi

