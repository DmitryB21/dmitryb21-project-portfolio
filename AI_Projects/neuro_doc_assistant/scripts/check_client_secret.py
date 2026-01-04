#!/usr/bin/env python
"""
Проверка формата ClientSecret в GIGACHAT_AUTH_KEY
"""

import os
import sys
import base64
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def main():
    print("=" * 80)
    print("Проверка формата ClientSecret")
    print("=" * 80)
    print()
    
    auth_key = os.getenv("GIGACHAT_AUTH_KEY")
    
    if not auth_key:
        print("❌ GIGACHAT_AUTH_KEY не установлен")
        return 1
    
    try:
        # Декодируем Base64
        decoded = base64.b64decode(auth_key).decode('utf-8')
        parts = decoded.split(':')
        
        if len(parts) < 2:
            print("❌ Неправильный формат: ожидается 'ClientID:ClientSecret'")
            return 1
        
        client_id = parts[0]
        client_secret = parts[1]
        
        print(f"✅ ClientID: {client_id}")
        print(f"✅ ClientSecret (исходный): {client_secret[:50]}...")
        print()
        
        # Пробуем декодировать ClientSecret как Base64
        print("Проверка: является ли ClientSecret Base64-encoded строкой?")
        try:
            secret_decoded = base64.b64decode(client_secret).decode('utf-8')
            print(f"✅ ClientSecret является Base64-encoded")
            print(f"   Декодированный ClientSecret: {secret_decoded[:50]}...")
            print()
            print("⚠️  ВНИМАНИЕ: ClientSecret уже закодирован в Base64!")
            print("   Это может быть причиной ошибки 400.")
            print()
            print("Попробуйте использовать декодированный ClientSecret:")
            print(f"   ClientID: {client_id}")
            print(f"   ClientSecret (декодированный): {secret_decoded}")
            print()
            print("Создайте новый GIGACHAT_AUTH_KEY с декодированным ClientSecret:")
            auth_string = f"{client_id}:{secret_decoded}"
            new_auth_key = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
            print(f"   GIGACHAT_AUTH_KEY={new_auth_key}")
        except Exception:
            print("❌ ClientSecret не является Base64-encoded строкой")
            print("   Это нормально - ClientSecret должен быть в исходном виде")
            print()
            print("Если всё ещё получаете ошибку 400, проверьте:")
            print("   1. Правильность ClientID и ClientSecret в личном кабинете")
            print("   2. Что аккаунт имеет доступ к API")
            print("   3. Что используется правильный Scope (GIGACHAT_API_PERS)")
        
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

