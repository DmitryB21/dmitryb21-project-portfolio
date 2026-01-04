#!/usr/bin/env python
"""
Тестирование рабочей схемы GigaChat Embeddings API
Проверяет разные URL и модели
"""

import os
import sys
import requests
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from app.generation.gigachat_auth import GigaChatAuth

# Загружаем переменные окружения
load_dotenv()

def test_embeddings_configs():
    """Тестирование разных конфигураций embeddings API"""
    print("=" * 80)
    print("Тестирование рабочей схемы GigaChat Embeddings API")
    print("=" * 80)
    print()
    
    # Получаем токен
    auth = GigaChatAuth()
    token = auth.get_access_token()
    
    if not token:
        print("❌ Не удалось получить access token")
        return None
    
    print(f"✅ Access token получен: {token[:50]}...")
    print()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Варианты для тестирования
    configs = [
        {
            "url": "https://gigachat.devices.sberbank.ru/api/v1/embeddings",
            "model": "GigaChat",
            "description": "Текущая конфигурация (devices.sberbank.ru + GigaChat)"
        },
        {
            "url": "https://gigachat.devices.sberbank.ru/api/v1/embeddings",
            "model": "Embeddings",
            "description": "Текущая конфигурация (devices.sberbank.ru + Embeddings)"
        },
        {
            "url": "https://api.gigachat.ai/v1/embeddings",
            "model": "GigaChat",
            "description": "Документация (api.gigachat.ai + GigaChat)"
        },
        {
            "url": "https://api.gigachat.ai/v1/embeddings",
            "model": "Embeddings",
            "description": "Документация (api.gigachat.ai + Embeddings)"
        },
    ]
    
    test_text = "Тестовый текст для проверки API"
    
    print("Тестирование конфигураций:")
    print("-" * 80)
    
    for i, config in enumerate(configs, 1):
        print(f"\n{i}. {config['description']}")
        print(f"   URL: {config['url']}")
        print(f"   Model: {config['model']}")
        
        payload = {
            "model": config["model"],
            "input": test_text
        }
        
        try:
            response = requests.post(
                config["url"],
                json=payload,
                headers=headers,
                verify=False,
                timeout=10
            )
            
            print(f"   Status: {response.status_code}", end="")
            
            if response.status_code == 200:
                data = response.json()
                print(f" | ✅ УСПЕШНО!")
                print(f"   Структура ответа: {list(data.keys())}")
                if "data" in data and len(data["data"]) > 0:
                    embedding = data["data"][0].get("embedding", [])
                    print(f"   Размерность embedding: {len(embedding)}")
                    print(f"   Первые 5 значений: {embedding[:5]}")
                return config  # Возвращаем рабочую конфигурацию
            elif response.status_code == 402:
                print(f" | ⚠️  Payment Required (требуется платная подписка)")
            elif response.status_code == 404:
                print(f" | ❌ Not Found")
                print(f"   Ответ: {response.text[:200]}")
            else:
                print(f" | ❌ Ошибка")
                print(f"   Ответ: {response.text[:200]}")
                
        except requests.exceptions.SSLError as e:
            print(f" | ❌ SSL Error: {str(e)[:100]}")
        except requests.exceptions.ConnectionError as e:
            print(f" | ❌ Connection Error: {str(e)[:100]}")
        except Exception as e:
            print(f" | ❌ Ошибка: {str(e)[:100]}")
    
    print()
    print("=" * 80)
    print("❌ Ни одна конфигурация не работает")
    print("=" * 80)
    return None

if __name__ == "__main__":
    working_config = test_embeddings_configs()
    
    if working_config:
        print()
        print("=" * 80)
        print("✅ НАЙДЕНА РАБОЧАЯ КОНФИГУРАЦИЯ!")
        print("=" * 80)
        print(f"URL: {working_config['url']}")
        print(f"Model: {working_config['model']}")
        print()
        print("Обновите код с этими параметрами.")
    else:
        print()
        print("=" * 80)
        print("⚠️  Рекомендация: Используйте mock mode для embeddings")
        print("=" * 80)

