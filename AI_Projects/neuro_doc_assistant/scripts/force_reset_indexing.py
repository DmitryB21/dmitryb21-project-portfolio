#!/usr/bin/env python
"""
Принудительный сброс статуса индексации (если зависла)

Использование:
    python scripts/force_reset_indexing.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

from app.api.indexing_status import get_tracker


def force_reset():
    """Принудительный сброс статуса индексации"""
    print("=" * 80)
    print("Принудительный сброс статуса индексации")
    print("=" * 80)
    print()
    
    try:
        tracker = get_tracker()
        current_status = tracker.get_status()
        
        print(f"Текущий статус: {current_status['status']}")
        print(f"Прогресс: {current_status['progress']:.1f}%")
        print(f"Текущий шаг: {current_status.get('current_step', 'N/A')}")
        if current_status.get('started_at'):
            print(f"Запущена: {current_status['started_at']}")
        print()
        
        # Выполняем сброс
        tracker.reset()
        print("✅ Статус индексации сброшен")
        
        # Проверяем результат
        new_status = tracker.get_status()
        print(f"Новый статус: {new_status['status']}")
        print()
        print("=" * 80)
        print("✅ Сброс выполнен успешно")
        print("=" * 80)
        
        return 0
    except Exception as e:
        print(f"❌ Ошибка при сбросе статуса: {e}")
        return 1


if __name__ == "__main__":
    exit_code = force_reset()
    sys.exit(exit_code)

