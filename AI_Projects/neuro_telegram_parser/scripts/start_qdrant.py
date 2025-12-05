#!/usr/bin/env python3
"""
Скрипт для запуска Qdrant через Docker

Использование:
    python scripts/start_qdrant.py
"""

import subprocess
import sys
import time
import requests

def check_qdrant_running(host="127.0.0.1", port=6333):
    """Проверить, запущен ли Qdrant"""
    try:
        response = requests.get(f"http://{host}:{port}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def start_qdrant_docker():
    """Запустить Qdrant через Docker"""
    print("🐳 Запуск Qdrant через Docker...")
    
    # Проверяем, запущен ли уже контейнер
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=qdrant", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        
        if "qdrant" in result.stdout:
            print("📦 Контейнер Qdrant найден")
            # Проверяем, запущен ли
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=qdrant", "--format", "{{.Names}}"],
                capture_output=True,
                text=True
            )
            
            if "qdrant" in result.stdout:
                print("✅ Qdrant уже запущен")
                return True
            else:
                print("🔄 Запуск существующего контейнера...")
                subprocess.run(["docker", "start", "qdrant"], check=True)
        else:
            print("🆕 Создание нового контейнера Qdrant...")
            subprocess.run([
                "docker", "run", "-d",
                "--name", "qdrant",
                "-p", "6333:6333",
                "-p", "6334:6334",
                "qdrant/qdrant:latest"
            ], check=True)
        
        # Ждем запуска
        print("⏳ Ожидание запуска Qdrant (10 секунд)...")
        time.sleep(10)
        
        # Проверяем доступность
        if check_qdrant_running():
            print("✅ Qdrant успешно запущен и доступен")
            return True
        else:
            print("⚠️ Qdrant запущен, но еще не отвечает. Подождите еще немного.")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при запуске Docker: {e}")
        return False
    except FileNotFoundError:
        print("❌ Docker не найден")
        print("💡 Установите Docker Desktop: https://www.docker.com/products/docker-desktop")
        return False

def main():
    """Основная функция"""
    print("=" * 60)
    print("ЗАПУСК QDRANT")
    print("=" * 60)
    print()
    
    # Проверяем, запущен ли уже Qdrant
    if check_qdrant_running():
        print("✅ Qdrant уже запущен и доступен")
        return 0
    
    print("⚠️ Qdrant не запущен")
    
    # Пробуем запустить через Docker
    if start_qdrant_docker():
        print("\n✅ Qdrant успешно запущен!")
        print(f"   Доступен по адресу: http://127.0.0.1:6333")
        return 0
    else:
        print("\n❌ Не удалось запустить Qdrant")
        print("\n💡 Альтернативные способы запуска:")
        print("   1. Установите Docker Desktop")
        print("   2. Или запустите Qdrant вручную:")
        print("      docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest")
        return 1

if __name__ == "__main__":
    sys.exit(main())

