#!/usr/bin/env python
"""
Скрипт для проверки подключения к GigaChat API
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from app.generation.gigachat_auth import GigaChatAuth
from app.ingestion.embedding_service import EmbeddingService

# Загружаем переменные окружения
load_dotenv()

def test_oauth_token():
    """Тест получения OAuth токена"""
    print("=" * 80)
    print("Тест 1: Получение OAuth токена")
    print("=" * 80)
    
    auth_key = os.getenv("GIGACHAT_AUTH_KEY")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    
    if not auth_key:
        print("❌ GIGACHAT_AUTH_KEY не установлен в .env файле")
        print("   Запустите: python scripts/setup_gigachat_auth.py")
        return False
    
    print(f"✅ GIGACHAT_AUTH_KEY найден: {auth_key[:30]}...")
    print(f"✅ Scope: {scope}")
    print()
    
    try:
        auth = GigaChatAuth(auth_key=auth_key, scope=scope)
        print("🔄 Запрос access token...")
        token = auth.get_access_token()
        
        if token:
            print(f"✅ Access token получен: {token[:50]}...")
            return True
        else:
            print("❌ Не удалось получить access token")
            print("   Проверьте:")
            print("   - Правильность GIGACHAT_AUTH_KEY")
            print("   - Правильность GIGACHAT_SCOPE")
            print("   - Доступность интернета")
            print("   - Доступность https://ngw.devices.sberbank.ru:9443")
            return False
    except Exception as e:
        print(f"❌ Ошибка при получении токена: {e}")
        return False

def test_embeddings_api():
    """Тест вызова Embeddings API"""
    print()
    print("=" * 80)
    print("Тест 2: Вызов Embeddings API")
    print("=" * 80)
    
    auth_key = os.getenv("GIGACHAT_AUTH_KEY")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    mock_mode = os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true"
    
    if mock_mode:
        print("⚠️  Mock mode включен (GIGACHAT_MOCK_MODE=true)")
        print("   Тест будет использовать mock embeddings")
    
    try:
        embedding_service = EmbeddingService(
            model_version=os.getenv("EMBEDDING_MODEL_VERSION", "GigaChat"),
            embedding_dim=int(os.getenv("EMBEDDING_DIM", "1536")),
            auth_key=auth_key,
            scope=scope,
            mock_mode=mock_mode
        )
        
        test_text = "Тестовый текст для проверки API"
        print(f"🔄 Генерация embedding для: '{test_text}'...")
        
        embeddings = embedding_service.generate_embeddings([test_text])
        
        if embeddings and len(embeddings) > 0:
            embedding = embeddings[0]
            print(f"✅ Embedding получен: размерность {len(embedding)}")
            if mock_mode:
                print("   ⚠️  Использован mock embedding (GIGACHAT_MOCK_MODE=true)")
            else:
                print("   ✅ Использован реальный GigaChat API")
            return True
        else:
            print("❌ Не удалось получить embedding")
            return False
    except Exception as e:
        print(f"❌ Ошибка при вызове Embeddings API: {e}")
        return False

def main():
    print()
    print("=" * 80)
    print("GigaChat API - Проверка подключения")
    print("=" * 80)
    print()
    
    # Проверяем настройки
    auth_key = os.getenv("GIGACHAT_AUTH_KEY")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    mock_mode = os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true"
    
    print("Текущие настройки:")
    print(f"  GIGACHAT_AUTH_KEY: {'✅ Установлен' if auth_key else '❌ Не установлен'}")
    print(f"  GIGACHAT_SCOPE: {scope}")
    print(f"  GIGACHAT_MOCK_MODE: {mock_mode}")
    print()
    
    if not auth_key:
        print("❌ GIGACHAT_AUTH_KEY не установлен!")
        print()
        print("Для настройки запустите:")
        print("  python scripts/setup_gigachat_auth.py")
        return 1
    
    if mock_mode:
        print("⚠️  ВНИМАНИЕ: Mock mode включен!")
        print("   Тесты будут использовать mock данные вместо реального API")
        print()
    
    # Запускаем тесты
    test1_result = test_oauth_token()
    test2_result = test_embeddings_api()
    
    print()
    print("=" * 80)
    print("Результаты тестирования")
    print("=" * 80)
    print(f"OAuth Token: {'✅ Успешно' if test1_result else '❌ Ошибка'}")
    print(f"Embeddings API: {'✅ Успешно' if test2_result else '❌ Ошибка'}")
    print()
    
    if test1_result and test2_result:
        print("✅ Все тесты пройдены! GigaChat API настроен правильно.")
        return 0
    else:
        print("❌ Некоторые тесты не пройдены. Проверьте настройки.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

