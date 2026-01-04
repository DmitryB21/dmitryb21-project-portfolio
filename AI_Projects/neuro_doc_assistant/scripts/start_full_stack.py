#!/usr/bin/env python
"""
Скрипт для одновременного запуска FastAPI и Streamlit UI

Использование:
    python scripts/start_full_stack.py

Или через start_project.bat (опция 6)
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Устанавливаем PYTHONPATH
os.environ["PYTHONPATH"] = str(project_root)


def check_port(port: int) -> bool:
    """Проверка доступности порта"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0


def start_fastapi(port: int = 8000) -> subprocess.Popen:
    """Запуск FastAPI сервера"""
    print(f"🚀 Запуск FastAPI на порту {port}...")
    
    # Проверяем доступность порта
    if not check_port(port):
        print(f"⚠️  Порт {port} занят, пробую порт {port + 1}...")
        port = port + 1
        if not check_port(port):
            print(f"❌ Порты {port - 1} и {port} заняты!")
            sys.exit(1)
    
    env = os.environ.copy()
    env["API_PORT"] = str(port)
    env["PYTHONPATH"] = str(project_root)
    
    process = subprocess.Popen(
        [sys.executable, "app/main.py"],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Ждём запуска сервера
    print(f"⏳ Ожидание запуска FastAPI...")
    for i in range(10):
        time.sleep(1)
        if not check_port(port):
            print(f"✅ FastAPI запущен на http://localhost:{port}")
            print(f"   Документация: http://localhost:{port}/docs")
            return process, port
        if process.poll() is not None:
            # Процесс завершился с ошибкой
            stdout, stderr = process.communicate()
            print(f"❌ Ошибка запуска FastAPI:")
            print(stderr)
            sys.exit(1)
    
    print(f"⚠️  FastAPI не ответил, но процесс запущен")
    return process, port


def start_streamlit(api_port: int = 8000) -> subprocess.Popen:
    """Запуск Streamlit UI"""
    print(f"🚀 Запуск Streamlit UI...")
    
    env = os.environ.copy()
    env["API_BASE_URL"] = f"http://localhost:{api_port}"
    env["PYTHONPATH"] = str(project_root)
    
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app/ui/streamlit_app.py"],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Ждём запуска Streamlit
    print(f"⏳ Ожидание запуска Streamlit...")
    time.sleep(3)
    
    if process.poll() is None:
        print(f"✅ Streamlit UI запущен на http://localhost:8501")
        return process
    else:
        stdout, stderr = process.communicate()
        print(f"❌ Ошибка запуска Streamlit:")
        print(stderr)
        sys.exit(1)


def main():
    """Основная функция"""
    print("=" * 80)
    print("Neuro_Doc_Assistant - Запуск Full Stack")
    print("=" * 80)
    print()
    
    # Проверка виртуального окружения
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Виртуальное окружение не активировано")
        print("   Рекомендуется активировать виртуальное окружение перед запуском")
        print()
    
    processes = []
    
    try:
        # Запуск FastAPI
        api_process, api_port = start_fastapi()
        processes.append(("FastAPI", api_process))
        
        time.sleep(2)  # Небольшая задержка между запусками
        
        # Запуск Streamlit
        streamlit_process = start_streamlit(api_port)
        processes.append(("Streamlit", streamlit_process))
        
        print()
        print("=" * 80)
        print("✅ Все сервисы запущены!")
        print("=" * 80)
        print(f"📡 FastAPI: http://localhost:{api_port}")
        print(f"   Документация: http://localhost:{api_port}/docs")
        print(f"🌐 Streamlit UI: http://localhost:8501")
        print()
        print("Для остановки нажмите Ctrl+C")
        print("=" * 80)
        print()
        
        # Ожидание завершения процессов
        while True:
            time.sleep(1)
            for name, process in processes:
                if process.poll() is not None:
                    print(f"⚠️  {name} завершился с кодом {process.returncode}")
                    if process.returncode != 0:
                        stdout, stderr = process.communicate()
                        print(f"Ошибка {name}:")
                        print(stderr)
    
    except KeyboardInterrupt:
        print()
        print("🛑 Остановка сервисов...")
        
        for name, process in processes:
            if process.poll() is None:
                print(f"   Остановка {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                    print(f"   ✅ {name} остановлен")
                except subprocess.TimeoutExpired:
                    print(f"   ⚠️  Принудительное завершение {name}...")
                    process.kill()
                    process.wait()
                    print(f"   ✅ {name} завершён")
        
        print("✅ Все сервисы остановлены")
    
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        
        # Останавливаем все процессы при ошибке
        for name, process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except:
                    process.kill()
        
        sys.exit(1)


if __name__ == "__main__":
    main()

