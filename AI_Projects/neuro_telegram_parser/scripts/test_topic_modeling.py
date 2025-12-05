#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы TopicModelingService

Использование:
    python scripts/test_topic_modeling.py

Этот скрипт проверяет:
1. Импорт модуля
2. Инициализацию сервиса
3. Загрузку конфигурации
4. Создание коллекций Qdrant
5. Индексацию тестовых данных (опционально)
"""

import asyncio
import sys
import os
from datetime import datetime

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pro_mode.topic_modeling_service import (
    TopicModelingService,
    TopicModelingConfig,
    FRIDAEmbedder,
    GTEEmbedder
)


async def test_imports():
    """Тест 1: Проверка импортов"""
    print("=" * 60)
    print("ТЕСТ 1: Проверка импортов")
    print("=" * 60)
    
    try:
        from pro_mode.topic_modeling_service import (
            TopicModelingService,
            TopicModelingConfig,
            FRIDAEmbedder,
            GTEEmbedder,
            QwenTitleGenerator
        )
        print("✅ Все модули успешно импортированы")
        return True
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False


async def test_config():
    """Тест 2: Проверка конфигурации"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Проверка конфигурации")
    print("=" * 60)
    
    try:
        config = TopicModelingConfig.from_config_file()
        print(f"✅ Конфигурация загружена:")
        print(f"   - FRIDA модель: {config.frida_model_name}")
        print(f"   - GTE модель: {config.gte_model_name}")
        print(f"   - Qdrant: {config.qdrant_host}:{config.qdrant_port}")
        print(f"   - Search коллекция: {config.search_collection}")
        print(f"   - Clustering коллекция: {config.clustering_collection}")
        if config.qwen_model_path:
            print(f"   - Qwen модель: {config.qwen_model_path}")
        else:
            print(f"   - Qwen модель: не указана (будет использован fallback)")
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        return False


async def test_service_init():
    """Тест 3: Инициализация сервиса"""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Инициализация TopicModelingService")
    print("=" * 60)
    
    try:
        service = TopicModelingService()
        print("✅ Сервис успешно инициализирован")
        return service
    except Exception as e:
        print(f"❌ Ошибка инициализации сервиса: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_qdrant_connection(service: TopicModelingService):
    """Тест 4: Проверка подключения к Qdrant"""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Проверка подключения к Qdrant")
    print("=" * 60)
    
    try:
        # Проверяем подключение
        collections = service.qdrant_client.get_collections().collections
        print(f"✅ Подключение к Qdrant успешно")
        print(f"   - Найдено коллекций: {len(collections)}")
        for col in collections:
            print(f"   - Коллекция: {col.name}")
        
        # Проверяем наличие нужных коллекций
        collection_names = [c.name for c in collections]
        if service.config.search_collection in collection_names:
            print(f"   ✅ Коллекция {service.config.search_collection} существует")
        else:
            print(f"   ⚠️ Коллекция {service.config.search_collection} не найдена (будет создана при индексации)")
        
        if service.config.clustering_collection in collection_names:
            print(f"   ✅ Коллекция {service.config.clustering_collection} существует")
        else:
            print(f"   ⚠️ Коллекция {service.config.clustering_collection} не найдена (будет создана при индексации)")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к Qdrant: {e}")
        print("   Убедитесь, что Qdrant запущен и доступен")
        return False


async def test_embedders(service: TopicModelingService):
    """Тест 5: Проверка embedders (без загрузки моделей)"""
    print("\n" + "=" * 60)
    print("ТЕСТ 5: Проверка embedders")
    print("=" * 60)
    
    try:
        # Проверяем, что embedders можно получить (ленивая загрузка)
        print("Проверка FRIDA embedder...")
        frida = service.frida_embedder
        print(f"   ✅ FRIDA embedder создан")
        print(f"   - Модель: {frida.model_name}")
        print(f"   - Размерность: {frida.get_dimension()}")
        
        print("\nПроверка GTE embedder...")
        gte = service.gte_embedder
        print(f"   ✅ GTE embedder создан")
        print(f"   - Модель: {gte.model_name}")
        print(f"   - Размерность: {gte.get_dimension()}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка проверки embedders: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_indexing(service: TopicModelingService, run_indexing: bool = False):
    """Тест 6: Тестовая индексация (опционально)"""
    print("\n" + "=" * 60)
    print("ТЕСТ 6: Тестовая индексация")
    print("=" * 60)
    
    if not run_indexing:
        print("⚠️ Индексация пропущена (для запуска установите run_indexing=True)")
        return True
    
    try:
        # Создаем тестовые посты
        test_posts = [
            {
                "post_id": 999999 + i,
                "text": f"Тестовый пост номер {i}. Это пример текста для проверки индексации в Qdrant.",
                "timestamp": datetime.now()
            }
            for i in range(3)
        ]
        
        print(f"Индексация {len(test_posts)} тестовых постов...")
        await service.upsert_to_search_index(test_posts)
        await service.upsert_to_clustering_index(test_posts)
        print("✅ Тестовые посты успешно проиндексированы")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка индексации: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Основная функция тестирования"""
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ TOPIC MODELING SERVICE")
    print("=" * 60)
    print()
    
    results = {}
    
    # Тест 1: Импорты
    results['imports'] = await test_imports()
    if not results['imports']:
        print("\n❌ Критическая ошибка: не удалось импортировать модули")
        return
    
    # Тест 2: Конфигурация
    results['config'] = await test_config()
    if not results['config']:
        print("\n⚠️ Предупреждение: не удалось загрузить конфигурацию")
    
    # Тест 3: Инициализация сервиса
    service = await test_service_init()
    if not service:
        print("\n❌ Критическая ошибка: не удалось инициализировать сервис")
        return
    results['service_init'] = True
    
    # Тест 4: Qdrant
    results['qdrant'] = await test_qdrant_connection(service)
    if not results['qdrant']:
        print("\n⚠️ Предупреждение: не удалось подключиться к Qdrant")
    
    # Тест 5: Embedders
    results['embedders'] = await test_embedders(service)
    if not results['embedders']:
        print("\n⚠️ Предупреждение: ошибка при проверке embedders")
    
    # Тест 6: Индексация (опционально)
    # Установите run_indexing=True для запуска реальной индексации
    results['indexing'] = await test_indexing(service, run_indexing=False)
    
    # Итоги
    print("\n" + "=" * 60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name:20} {status}")
    
    print(f"\nПройдено тестов: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 Все тесты пройдены успешно!")
    elif passed >= total - 1:
        print("\n⚠️ Большинство тестов пройдено, но есть предупреждения")
    else:
        print("\n❌ Есть критические ошибки, требующие исправления")


if __name__ == "__main__":
    asyncio.run(main())

