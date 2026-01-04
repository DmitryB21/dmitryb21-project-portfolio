#!/usr/bin/env python
"""
Скрипт для настройки GigaChat API OAuth 2.0 аутентификации
"""

import base64
import os
import sys
from pathlib import Path

def generate_auth_key(client_id: str, client_secret: str) -> str:
    """
    Генерирует Base64 encoded auth key из Client ID и Client Secret
    
    Args:
        client_id: Client ID от GigaChat
        client_secret: Client Secret от GigaChat
        
    Returns:
        Base64 encoded строка "Client ID:Client Secret"
    """
    auth_string = f"{client_id}:{client_secret}"
    auth_key = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    return auth_key

def update_env_file(auth_key: str, scope: str = "GIGACHAT_API_PERS", mock_mode: bool = False):
    """
    Обновляет .env файл с настройками GigaChat API
    
    Args:
        auth_key: Base64 encoded auth key
        scope: Scope для OAuth (GIGACHAT_API_PERS, GIGACHAT_API_B2B, GIGACHAT_API_CORP)
        mock_mode: Использовать ли mock mode
    """
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    # Читаем существующий .env файл
    env_lines = []
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            env_lines = f.readlines()
    
    # Обновляем или добавляем настройки
    updated = {
        'GIGACHAT_AUTH_KEY': False,
        'GIGACHAT_SCOPE': False,
        'GIGACHAT_MOCK_MODE': False
    }
    
    new_lines = []
    for line in env_lines:
        line_stripped = line.strip()
        if line_stripped.startswith('GIGACHAT_AUTH_KEY='):
            new_lines.append(f"GIGACHAT_AUTH_KEY={auth_key}\n")
            updated['GIGACHAT_AUTH_KEY'] = True
        elif line_stripped.startswith('GIGACHAT_SCOPE='):
            new_lines.append(f"GIGACHAT_SCOPE={scope}\n")
            updated['GIGACHAT_SCOPE'] = True
        elif line_stripped.startswith('GIGACHAT_MOCK_MODE='):
            new_lines.append(f"GIGACHAT_MOCK_MODE={str(mock_mode).lower()}\n")
            updated['GIGACHAT_MOCK_MODE'] = True
        else:
            new_lines.append(line)
    
    # Добавляем недостающие настройки
    if not updated['GIGACHAT_AUTH_KEY']:
        new_lines.append(f"GIGACHAT_AUTH_KEY={auth_key}\n")
    if not updated['GIGACHAT_SCOPE']:
        new_lines.append(f"GIGACHAT_SCOPE={scope}\n")
    if not updated['GIGACHAT_MOCK_MODE']:
        new_lines.append(f"GIGACHAT_MOCK_MODE={str(mock_mode).lower()}\n")
    
    # Записываем обновлённый файл
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"✅ Настройки обновлены в {env_file}")

def main():
    print("=" * 80)
    print("GigaChat API - Настройка OAuth 2.0 аутентификации")
    print("=" * 80)
    print()
    print("Для получения Client ID и Client Secret:")
    print("1. Перейдите: https://developers.sber.ru/portal/products/gigachat")
    print("2. Зарегистрируйте приложение")
    print("3. Получите Client ID и Client Secret")
    print()
    
    # Вариант 1: Ввод Client ID и Client Secret
    print("Вариант 1: Ввод Client ID и Client Secret")
    print("-" * 80)
    client_id = input("Введите Client ID: ").strip()
    if not client_id:
        print("❌ Client ID не может быть пустым")
        return 1
    
    client_secret = input("Введите Client Secret: ").strip()
    if not client_secret:
        print("❌ Client Secret не может быть пустым")
        return 1
    
    # Генерируем auth key
    auth_key = generate_auth_key(client_id, client_secret)
    print()
    print(f"✅ Сгенерирован GIGACHAT_AUTH_KEY: {auth_key[:50]}...")
    print()
    
    # Выбор scope
    print("Выберите Scope:")
    print("1. GIGACHAT_API_PERS (для физических лиц) - по умолчанию")
    print("2. GIGACHAT_API_B2B (для ИП и юридических лиц по платным пакетам)")
    print("3. GIGACHAT_API_CORP (для ИП и юридических лиц по схеме pay-as-you-go)")
    scope_choice = input("Выберите вариант (1-3) [1]: ").strip() or "1"
    
    scope_map = {
        "1": "GIGACHAT_API_PERS",
        "2": "GIGACHAT_API_B2B",
        "3": "GIGACHAT_API_CORP"
    }
    scope = scope_map.get(scope_choice, "GIGACHAT_API_PERS")
    
    # Mock mode
    mock_mode_choice = input("Использовать mock mode? (y/N): ").strip().lower()
    mock_mode = mock_mode_choice == 'y'
    
    # Обновляем .env файл
    update_env_file(auth_key, scope, mock_mode)
    
    print()
    print("=" * 80)
    print("✅ Настройка завершена!")
    print("=" * 80)
    print()
    print("Следующие шаги:")
    print("1. Перезапустите FastAPI сервер")
    print("2. Проверьте статус GigaChat API в Streamlit UI")
    print("3. Если есть проблемы с подключением, проверьте:")
    print("   - Доступность интернета")
    print("   - Правильность Client ID и Client Secret")
    print("   - Правильность выбранного Scope")
    print()
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

