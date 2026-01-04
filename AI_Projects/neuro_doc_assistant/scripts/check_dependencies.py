#!/usr/bin/env python
"""
Проверка наличия всех необходимых зависимостей для индексации
"""

import sys
from pathlib import Path

def check_dependency(module_name, package_name=None):
    """Проверка наличия модуля"""
    try:
        __import__(module_name)
        print(f"✅ {module_name}")
        return True
    except ImportError:
        print(f"❌ {module_name} не установлен")
        if package_name:
            print(f"   Установите: pip install {package_name}")
        return False

def main():
    """Проверка всех зависимостей"""
    print("=" * 80)
    print("Проверка зависимостей для Neuro_Doc_Assistant")
    print("=" * 80)
    print()
    print(f"Python: {sys.executable}")
    print(f"Версия: {sys.version}")
    print()
    
    dependencies = [
        ("boto3", "boto3"),
        ("qdrant_client", "qdrant-client"),
        ("fastapi", "fastapi"),
        ("streamlit", "streamlit"),
        ("sqlalchemy", "sqlalchemy"),
        ("psycopg2", "psycopg2-binary"),
        ("dotenv", "python-dotenv"),
        ("requests", "requests"),
    ]
    
    all_ok = True
    for module, package in dependencies:
        if not check_dependency(module, package):
            all_ok = False
    
    print()
    if all_ok:
        print("=" * 80)
        print("✅ Все зависимости установлены")
        print("=" * 80)
        return 0
    else:
        print("=" * 80)
        print("❌ Некоторые зависимости отсутствуют")
        print("   Установите все зависимости: pip install -r requirements.txt")
        print("=" * 80)
        return 1

if __name__ == "__main__":
    sys.exit(main())

