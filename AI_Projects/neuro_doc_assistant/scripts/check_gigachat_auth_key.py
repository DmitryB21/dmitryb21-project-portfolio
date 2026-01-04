#!/usr/bin/env python
"""
Скрипт для проверки формата GIGACHAT_AUTH_KEY
"""

import os
import sys
import base64
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

def check_auth_key_format(auth_key: str) -> tuple[bool, str]:
    """
    Проверяет формат GIGACHAT_AUTH_KEY
    
    Returns:
        (is_valid, message)
    """
    if not auth_key:
        return False, "GIGACHAT_AUTH_KEY не установлен"
    
    # Проверяем, что это Base64 строка
    try:
        decoded = base64.b64decode(auth_key)
        decoded_str = decoded.decode('utf-8')
        
        # Проверяем формат "ClientID:ClientSecret"
        if ':' not in decoded_str:
            return False, f"Неверный формат: должно быть 'ClientID:ClientSecret', получено: {decoded_str[:50]}..."
        
        parts = decoded_str.split(':', 1)
        if len(parts) != 2:
            return False, f"Неверный формат: должно быть 'ClientID:ClientSecret', получено: {decoded_str[:50]}..."
        
        client_id, client_secret = parts
        if not client_id or not client_secret:
            return False, "ClientID или ClientSecret пустые"
        
        return True, f"✅ Формат правильный. ClientID: {client_id[:20]}..., ClientSecret: {client_secret[:20]}..."
        
    except Exception as e:
        return False, f"Ошибка декодирования Base64: {e}"

def main():
    print("=" * 80)
    print("Проверка формата GIGACHAT_AUTH_KEY")
    print("=" * 80)
    print()
    
    auth_key = os.getenv("GIGACHAT_AUTH_KEY")
    
    if not auth_key:
        print("❌ GIGACHAT_AUTH_KEY не установлен в .env файле")
        print()
        print("Для настройки запустите:")
        print("  python scripts/setup_gigachat_auth.py")
        return 1
    
    print(f"GIGACHAT_AUTH_KEY найден: {auth_key[:30]}...{auth_key[-10:]}")
    print()
    
    is_valid, message = check_auth_key_format(auth_key)
    
    if is_valid:
        print(message)
        print()
        print("✅ GIGACHAT_AUTH_KEY имеет правильный формат!")
        print()
        print("Если всё ещё получаете ошибку 400, проверьте:")
        print("  1. Правильность Client ID и Client Secret")
        print("  2. Что они получены из личного кабинета GigaChat")
        print("  3. Что аккаунт имеет доступ к API")
        return 0
    else:
        print(f"❌ {message}")
        print()
        print("Исправление:")
        print("  1. Убедитесь, что GIGACHAT_AUTH_KEY = base64(ClientID:ClientSecret)")
        print("  2. Запустите: python scripts/setup_gigachat_auth.py")
        print("  3. Или сгенерируйте вручную:")
        print("     import base64")
        print("     auth_key = base64.b64encode(b'ClientID:ClientSecret').decode('utf-8')")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

