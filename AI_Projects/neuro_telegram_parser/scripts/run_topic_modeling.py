#!/usr/bin/env python3
"""
Скрипт для запуска Topic Modeling Service

Использование:
    python scripts/run_topic_modeling.py [--limit N] [--days-back N] [--skip-indexing]
"""

import asyncio
import sys
import os
import argparse
import logging
from datetime import datetime

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настройка логирования ПЕРЕД импортом модулей
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('topic_modeling.log', encoding='utf-8')
    ],
    force=True  # Переопределяем существующую конфигурацию
)

# Устанавливаем уровень логирования для всех модулей
logging.getLogger('pro_mode').setLevel(logging.INFO)
logging.getLogger('pro_mode.topic_modeling_service').setLevel(logging.INFO)

# Создаем logger для скрипта
logger = logging.getLogger(__name__)
logger.info("=" * 60)
logger.info("ИНИЦИАЛИЗАЦИЯ СКРИПТА")
logger.info("=" * 60)

from pro_mode.topic_modeling_service import TopicModelingService


async def main():
    """Основная функция запуска"""
    parser = argparse.ArgumentParser(description='Запуск Topic Modeling Service')
    parser.add_argument('--limit', type=int, default=None, help='Лимит постов для обработки')
    parser.add_argument('--days-back', type=int, default=30, help='Количество дней назад для загрузки постов')
    parser.add_argument('--skip-indexing', action='store_true', help='Пропустить индексацию новых постов')
    parser.add_argument('--new-posts-only', action='store_true', help='Обработать только новые посты (не загружать из БД)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("ЗАПУСК TOPIC MODELING SERVICE")
    print("=" * 60)
    print()
    logger.info("=" * 60)
    logger.info("ЗАПУСК TOPIC MODELING SERVICE")
    logger.info("=" * 60)
    
    try:
        # Инициализация сервиса
        print("🔧 Инициализация сервиса...")
        logger.info("Инициализация сервиса...")
        service = TopicModelingService()
        print("✅ Сервис инициализирован")
        logger.info("✅ Сервис инициализирован")
        print()
        
        # Проверка подключения к Qdrant
        print("🔍 Проверка подключения к Qdrant...")
        logger.info("Проверка подключения к Qdrant...")
        try:
            collections = service.qdrant_client.get_collections().collections
            print(f"✅ Qdrant доступен (найдено коллекций: {len(collections)})")
            logger.info(f"✅ Qdrant доступен (найдено коллекций: {len(collections)})")
        except Exception as e:
            print(f"❌ Ошибка подключения к Qdrant: {e}")
            logger.error(f"❌ Ошибка подключения к Qdrant: {e}")
            print("💡 Запустите Qdrant: python scripts/start_qdrant.py")
            return 1
        print()
        
        # Запуск пайплайна
        if args.new_posts_only:
            print("⚠️ Режим: только новые посты (не загружаем из БД)")
            new_posts = []  # Пустой список - пользователь должен передать посты через API
            result = await service.run_full_pipeline(new_posts=new_posts, fetch_from_db=False)
        elif args.skip_indexing:
            print("⚠️ Режим: пропуск индексации, только построение модели")
            # Пропускаем индексацию, сразу строим модель
            print("🔨 Построение тематической модели...")
            await service.build_topic_model()
            topic_info = service.get_topic_info()
            print(f"✅ Модель построена, найдено тем: {len(topic_info['topic_sizes'])}")
            
            print("💾 Сохранение результатов...")
            save_stats = await service.save_topics_to_db()
            print(f"✅ Сохранено кластеров: {save_stats['clusters_created']}")
            result = {
                "posts_indexed": 0,
                "topics_found": len(topic_info['topic_sizes']),
                "clusters_created": save_stats['clusters_created'],
                "posts_linked": save_stats['posts_linked'],
                "execution_time": 0
            }
        else:
            print("🚀 Запуск полного пайплайна...")
            print(f"   - Лимит постов: {args.limit or 'без ограничений'}")
            print(f"   - Дней назад: {args.days_back}")
            print()
            logger.info("🚀 Запуск полного пайплайна...")
            logger.info(f"   - Лимит постов: {args.limit or 'без ограничений'}")
            logger.info(f"   - Дней назад: {args.days_back}")
            
            # Модифицируем метод загрузки для поддержки параметров
            original_fetch = service._fetch_posts_from_db
            async def fetch_with_params(limit=None, days_back=30):
                return await original_fetch(limit=args.limit or limit, days_back=args.days_back or days_back)
            service._fetch_posts_from_db = fetch_with_params
            
            result = await service.run_full_pipeline(fetch_from_db=True)
        
        # Вывод результатов
        print()
        print("=" * 60)
        print("РЕЗУЛЬТАТЫ")
        print("=" * 60)
        print(f"Проиндексировано постов: {result['posts_indexed']}")
        print(f"Найдено тем: {result['topics_found']}")
        print(f"Создано кластеров: {result['clusters_created']}")
        print(f"Привязано постов: {result['posts_linked']}")
        print(f"Время выполнения: {result['execution_time']:.2f} сек")
        print()
        print("✅ Пайплайн завершен успешно!")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем")
        return 1
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

