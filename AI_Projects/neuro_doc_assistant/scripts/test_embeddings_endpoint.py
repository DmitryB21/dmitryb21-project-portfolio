#!/usr/bin/env python
"""
Тестирование GigaChat Embeddings API endpoint
"""

import os
import sys
import requests
import json
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from app.generation.gigachat_auth import GigaChatAuth

# Загружаем переменные окружения
load_dotenv()

def test_embeddings_endpoint():
    """Тестирование embeddings endpoint с разными моделями"""
    print("=" * 80)
    print("Тестирование GigaChat Embeddings API")
    print("=" * 80)
    print()
    
    # Получаем токен
    auth = GigaChatAuth()
    token = auth.get_access_token()
    
    if not token:
        print("❌ Не удалось получить access token")
        return
    
    print(f"✅ Access token получен: {token[:50]}...")
    print()
    
    # URL endpoint
    embeddings_url = "https://gigachat.devices.sberbank.ru/api/v1/embeddings"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Тестируем разные модели
    models_to_test = [
        "Embeddings",
        "embedding",
        "GigaChat-Embeddings",
        "gigachat-embedding",
        "GigaChat",
        "GigaChat:latest",
        "embedding-v1",
        "Embeddings-v1"
    ]
    
    test_text = "Тестовый текст для проверки API"
    
    print(f"URL: {embeddings_url}")
    print(f"Тестовый текст: {test_text}")
    print()
    print("Тестирование разных моделей:")
    print("-" * 80)
    
    for model in models_to_test:
        payload = {
            "model": model,
            "input": test_text
        }
        
        try:
            response = requests.post(
                embeddings_url,
                json=payload,
                headers=headers,
                verify=False,
                timeout=10
            )
            
            print(f"Model: {model:25} | Status: {response.status_code}", end="")
            
            if response.status_code == 200:
                data = response.json()
                print(f" | ✅ Успешно!")
                if "data" in data:
                    print(f"   Структура ответа: {json.dumps(data, ensure_ascii=False, indent=2)[:300]}")
                else:
                    print(f"   Ответ: {json.dumps(data, ensure_ascii=False)[:200]}")
                return model  # Возвращаем рабочую модель
            else:
                error_text = response.text[:100]
                print(f" | ❌ {error_text}")
                
        except Exception as e:
            print(f"Model: {model:25} | ❌ Ошибка: {e}")
    
    print()
    print("=" * 80)
    print("❌ Ни одна модель не работает")
    print("=" * 80)
    return None

def test_alternative_formats():
    """Тестирование альтернативных форматов запроса"""
    print()
    print("=" * 80)
    print("Тестирование альтернативных форматов запроса")
    print("=" * 80)
    print()
    
    auth = GigaChatAuth()
    token = auth.get_access_token()
    
    if not token:
        print("❌ Не удалось получить access token")
        return
    
    embeddings_url = "https://gigachat.devices.sberbank.ru/api/v1/embeddings"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Альтернативные форматы
    formats = [
        {"model": "Embeddings", "input": "test"},
        {"model": "Embeddings", "inputs": ["test"]},
        {"input": "test"},  # Без модели
        {"text": "test"},  # Альтернативное поле
    ]
    
    for i, payload in enumerate(formats, 1):
        print(f"Формат {i}: {json.dumps(payload, ensure_ascii=False)}")
        try:
            response = requests.post(
                embeddings_url,
                json=payload,
                headers=headers,
                verify=False,
                timeout=10
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   ✅ Успешно! Ответ: {response.text[:200]}")
                return payload
            else:
                print(f"   ❌ {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
        print()
    
    return None

if __name__ == "__main__":
    working_model = test_embeddings_endpoint()
    
    if not working_model:
        test_alternative_formats()
    
    print()
    print("=" * 80)
    print("Тестирование завершено")
    print("=" * 80)

