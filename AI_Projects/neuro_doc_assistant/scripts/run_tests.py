"""
@file: run_tests.py
@description: Скрипт для запуска всех тестов проекта с логированием результатов
@dependencies: pytest, pytest-html (опционально)
@created: 2024-12-19
"""

import sys
import subprocess
import os
from pathlib import Path
from datetime import datetime


def run_tests():
    """
    Запускает все тесты проекта и сохраняет логи в файл.
    
    Создаёт:
    - tests/logs/test_results_YYYY-MM-DD_HH-MM-SS.txt - текстовый лог
    - tests/logs/junit.xml - JUnit XML отчет (для CI/CD)
    - tests/logs/report.html - HTML отчет (если установлен pytest-html)
    """
    # Создаём директорию для логов, если её нет
    log_dir = Path("tests/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Генерируем имя файла с timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = log_dir / f"test_results_{timestamp}.txt"
    junit_xml = log_dir / "junit.xml"
    html_report = log_dir / "report.html"
    
    # Команда pytest с опциями
    pytest_args = [
        "python", "-m", "pytest",
        "tests/",  # Все тесты в директории tests/
        "-v",  # Подробный вывод
        "--tb=short",  # Короткий traceback
        "--strict-markers",  # Строгая проверка маркеров
        f"--junitxml={junit_xml}",  # JUnit XML отчет
        "--capture=no",  # Показывать print statements (но вывод пойдёт в файл)
    ]
    
    # Добавляем HTML отчет, если pytest-html установлен
    try:
        import pytest_html
        pytest_args.append(f"--html={html_report}")
        pytest_args.append("--self-contained-html")
    except ImportError:
        print("pytest-html не установлен. HTML отчет не будет создан.")
        print("Установите: pip install pytest-html")
    
    print("=" * 80)
    print("Запуск всех тестов проекта Neuro_Doc_Assistant")
    print("=" * 80)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Лог файл: {log_file}")
    print(f"JUnit XML: {junit_xml}")
    if "pytest_html" in sys.modules:
        print(f"HTML отчет: {html_report}")
    print("-" * 80)
    print()
    
    # Запускаем тесты с записью в файл и выводом в консоль одновременно
    try:
        class TeeOutput:
            """Класс для одновременной записи в файл и вывод в консоль (tee-like)"""
            def __init__(self, file, console):
                self.file = file
                self.console = console
            
            def write(self, text):
                self.file.write(text)
                self.file.flush()
                self.console.write(text)
                self.console.flush()
            
            def flush(self):
                self.file.flush()
                self.console.flush()
            
            def fileno(self):
                """Требуется для subprocess, возвращаем fileno консоли"""
                return self.console.fileno() if hasattr(self.console, 'fileno') else 1
        
        # Открываем файл для записи лога
        with open(log_file, "w", encoding="utf-8") as log_f:
            # Записываем заголовок
            header = (
                "=" * 80 + "\n" +
                "Запуск всех тестов проекта Neuro_Doc_Assistant\n" +
                "=" * 80 + "\n" +
                f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" +
                "-" * 80 + "\n\n"
            )
            log_f.write(header)
            print(header, end="")
            
            # Создаём TeeOutput для одновременной записи в файл и консоль
            tee = TeeOutput(log_f, sys.stdout)
            
            # Запускаем pytest с перенаправлением вывода через TeeOutput
            result = subprocess.run(
                pytest_args,
                stdout=tee,  # Перенаправляем stdout через TeeOutput (в файл и консоль)
                stderr=subprocess.STDOUT,  # Перенаправляем stderr в stdout
                text=True,
                check=False  # Не выбрасываем исключение при ошибках
            )
            
            exit_code = result.returncode
            
            # Записываем итоговую информацию
            footer = (
                "\n" + "=" * 80 + "\n" +
                f"Завершено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" +
                f"Exit code: {exit_code}\n" +
                "=" * 80 + "\n"
            )
            log_f.write(footer)
            print(footer, end="")
        
        # Записываем итоговую информацию в лог файл
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"Завершено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Exit code: {exit_code}\n")
            f.write("=" * 80 + "\n")
        
        # Выводим итоговую информацию
        print()
        print("=" * 80)
        print("ИТОГИ ТЕСТИРОВАНИЯ")
        print("=" * 80)
        print(f"Exit code: {exit_code}")
        print(f"Лог сохранён в: {log_file}")
        print(f"JUnit XML сохранён в: {junit_xml}")
        if "pytest_html" in sys.modules:
            print(f"HTML отчет сохранён в: {html_report}")
        
        if exit_code == 0:
            print("✅ Все тесты прошли успешно!")
        else:
            print("❌ Некоторые тесты провалились. Проверьте лог файл для деталей.")
        
        print("=" * 80)
        
        return exit_code
        
    except Exception as e:
        print(f"❌ Ошибка при запуске тестов: {e}")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\nОшибка при запуске тестов: {e}\n")
        return 1


def run_specific_module(module_name: str):
    """
    Запускает тесты для конкретного модуля.
    
    Args:
        module_name: Имя модуля (ingestion, retrieval, reranking, generation, evaluation, agent, use_cases, api, monitoring, storage)
    """
    log_dir = Path("tests/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = log_dir / f"test_results_{module_name}_{timestamp}.txt"
    junit_xml = log_dir / f"junit_{module_name}.xml"
    
    pytest_args = [
        "python", "-m", "pytest",
        f"tests/{module_name}/",
        "-v",
        "--tb=short",
        "--capture=no",
        f"--junitxml={junit_xml}",
    ]
    
    # Добавляем HTML отчет, если pytest-html установлен
    try:
        import pytest_html
        html_report = log_dir / f"report_{module_name}.html"
        pytest_args.append(f"--html={html_report}")
        pytest_args.append("--self-contained-html")
    except ImportError:
        html_report = None
    
    print("=" * 80)
    print(f"Запуск тестов для модуля: {module_name}")
    print("=" * 80)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Лог файл: {log_file}")
    print(f"JUnit XML: {junit_xml}")
    if html_report:
        print(f"HTML отчет: {html_report}")
    print("-" * 80)
    print()
    
    # Записываем вывод в файл
    with open(log_file, "w", encoding="utf-8") as log_f:
        header = (
            "=" * 80 + "\n" +
            f"Запуск тестов для модуля: {module_name}\n" +
            "=" * 80 + "\n" +
            f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" +
            "-" * 80 + "\n\n"
        )
        log_f.write(header)
        print(header, end="")
        log_f.flush()
        
        result = subprocess.run(
            pytest_args,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            text=True,
            check=False
        )
        
        exit_code = result.returncode
        
        footer = (
            "\n" + "=" * 80 + "\n" +
            f"Завершено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" +
            f"Exit code: {exit_code}\n" +
            "=" * 80 + "\n"
        )
        log_f.write(footer)
        print(footer, end="")
    
    # Выводим содержимое файла в консоль
    print("\n" + "=" * 80)
    print("СОДЕРЖИМОЕ ЛОГА:")
    print("=" * 80)
    with open(log_file, "r", encoding="utf-8") as f:
        print(f.read())
    
    # Итоговая информация
    print("=" * 80)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 80)
    print(f"Exit code: {exit_code}")
    print(f"Лог сохранён в: {log_file}")
    print(f"JUnit XML сохранён в: {junit_xml}")
    if html_report:
        print(f"HTML отчет сохранён в: {html_report}")
    
    if exit_code == 0:
        print(f"✅ Все тесты модуля '{module_name}' прошли успешно!")
    else:
        print(f"❌ Некоторые тесты модуля '{module_name}' провалились. Проверьте лог файл для деталей.")
    print("=" * 80)
    
    return exit_code
    


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Запуск тестов Neuro_Doc_Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python scripts/run_tests.py                    # Запуск всех тестов
  python scripts/run_tests.py ingestion          # Запуск тестов модуля ingestion
  python scripts/run_tests.py retrieval           # Запуск тестов модуля retrieval
  python scripts/run_tests.py generation         # Запуск тестов модуля generation
  python scripts/run_tests.py evaluation         # Запуск тестов модуля evaluation
  python scripts/run_tests.py agent              # Запуск тестов модуля agent
  python scripts/run_tests.py use_cases          # Запуск тестов use cases
  python scripts/run_tests.py api                # Запуск тестов API Layer
  python scripts/run_tests.py reranking          # Запуск тестов Reranking Module
  python scripts/run_tests.py monitoring        # Запуск тестов Monitoring Module
  python scripts/run_tests.py storage          # Запуск тестов Storage Module (Experimental Cycle)
        """
    )
    parser.add_argument(
        "module",
        nargs="?",
        default="all",
        help="Имя модуля для запуска тестов (ingestion, retrieval, reranking, generation, evaluation, agent, use_cases, api, monitoring, storage) или 'all' для всех тестов"
    )
    
    args = parser.parse_args()
    
    if args.module == "all":
        exit_code = run_tests()
    elif args.module in ["ingestion", "retrieval", "reranking", "generation", "evaluation", "agent", "use_cases", "api", "monitoring", "storage"]:
        exit_code = run_specific_module(args.module)
    else:
        print(f"❌ Неизвестный модуль: {args.module}")
        print("Доступные модули: ingestion, retrieval, reranking, generation, evaluation, agent, use_cases, api, monitoring, storage, all")
        exit_code = 1
    
    sys.exit(exit_code)

