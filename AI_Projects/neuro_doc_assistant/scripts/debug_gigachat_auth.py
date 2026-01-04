#!/usr/bin/env python
"""
Скрипт для детальной диагностики GigaChat OAuth аутентификации
"""

import os
import sys
import base64
import requests
import uuid
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def main():
    print("=" * 80)
    print("Детальная диагностика GigaChat OAuth аутентификации")
    print("=" * 80)
    print()
    
    auth_key = os.getenv("GIGACHAT_AUTH_KEY")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    
    if not auth_key:
        print("❌ GIGACHAT_AUTH_KEY не установлен")
        return 1
    
    print(f"✅ GIGACHAT_AUTH_KEY найден: {auth_key[:50]}...")
    print(f"✅ Scope: {scope}")
    print()
    
    # Проверяем декодирование Base64
    print("=" * 80)
    print("Шаг 1: Проверка декодирования Base64")
    print("=" * 80)
    try:
        decoded = base64.b64decode(auth_key).decode('utf-8')
        print(f"✅ Base64 декодирован успешно")
        print(f"   Декодированная строка: {decoded[:100]}...")
        
        parts = decoded.split(':')
        if len(parts) >= 2:
            print(f"✅ Формат правильный (ClientID:ClientSecret)")
            print(f"   ClientID: {parts[0]}")
            print(f"   ClientSecret: {parts[1][:30]}...")
        else:
            print(f"❌ Неправильный формат: ожидается 'ClientID:ClientSecret'")
            print(f"   Найдено частей: {len(parts)}")
            return 1
    except Exception as e:
        print(f"❌ Ошибка декодирования Base64: {e}")
        return 1
    
    print()
    print("=" * 80)
    print("Шаг 2: Проверка OAuth запроса")
    print("=" * 80)
    
    # Формируем запрос
    rq_uid = str(uuid.uuid4())
    oauth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": rq_uid,
        "Authorization": f"Basic {auth_key}"
    }
    
    data = {
        "scope": scope
    }
    
    print(f"URL: {oauth_url}")
    print(f"RqUID: {rq_uid}")
    print(f"Authorization header: Basic {auth_key[:50]}...")
    print(f"Scope: {scope}")
    print()
    
    print("🔄 Отправка запроса...")
    try:
        # Отключаем проверку SSL для OAuth endpoint
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = requests.post(
            oauth_url,
            headers=headers,
            data=data,
            timeout=30,
            verify=False  # Отключаем проверку SSL
        )
        
        print(f"Статус код: {response.status_code}")
        print(f"Ответ: {response.text[:500]}")
        
        if response.status_code == 200:
            print("✅ Токен получен успешно!")
            response_data = response.json()
            access_token = response_data.get("access_token", "")
            print(f"Access token: {access_token[:50]}...")
            return 0
        elif response.status_code == 400:
            print("❌ Ошибка 400: Неправильный формат запроса")
            print()
            print("Возможные причины:")
            print("  1. Неправильный формат GIGACHAT_AUTH_KEY")
            print("  2. ClientID или ClientSecret неверны")
            print("  3. Аккаунт не имеет доступа к API")
            print()
            print("Проверьте:")
            print("  - Правильность ClientID и ClientSecret в личном кабинете")
            print("  - Что они правильно закодированы в Base64")
            print("  - Формат: base64(ClientID:ClientSecret)")
            return 1
        elif response.status_code == 429:
            print("⚠️  Ошибка 429: Слишком много запросов")
            print("   Подождите несколько минут и попробуйте снова")
            return 1
        else:
            print(f"❌ Неожиданный статус код: {response.status_code}")
            return 1
            
    except Exception as e:
        print(f"❌ Ошибка при отправке запроса: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

