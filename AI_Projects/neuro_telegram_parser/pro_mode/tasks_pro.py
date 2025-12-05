"""
Huey задачи для индексации сообщений в Qdrant (Pro-режим)
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import asyncpg

from huey_config import huey
from config_utils import get_config
from pro_mode import pro_mode_service
from pro_mode.embedding_service import embedding_service
from pro_mode.topic_modeling_progress import TopicModelingProgressTracker

logger = logging.getLogger(__name__)


async def _fetch_messages(conn, limit: int = 1000, since: Optional[str] = None):
    where = []
    params = []
    param_count = 0
    
    # Базовые условия
    base_where = [
        "m.text_content IS NOT NULL",
        "m.text_content != ''",
        "LENGTH(m.text_content) >= 10"
    ]
    
    # Условие для пропуска уже проиндексированных
    base_where.append("NOT EXISTS (SELECT 1 FROM embeddings e WHERE e.message_id = m.id)")
    
    if since:
        param_count += 1
        base_where.append(f"m.published_at >= ${param_count}")
        params.append(datetime.fromisoformat(since))
    
    where_sql = " AND ".join(base_where)
    
    param_count += 1
    limit_param = f"${param_count}"
    params.append(limit)
    
    sql = f"""
        SELECT m.id as message_id, m.channel_id, m.text_content as text, m.published_at
        FROM messages m
        WHERE {where_sql}
        ORDER BY m.published_at ASC
        LIMIT {limit_param}
    """
    logger.debug(f"🔍 Выполняем запрос для получения сообщений: {sql[:200]}...")
    rows = await conn.fetch(sql, *params)
    logger.info(f"📋 Получено {len(rows)} сообщений из базы данных для индексации")
    return rows


async def _index_batch(limit: int = 1000, since: Optional[str] = None):
    config = get_config()
    # ensure initialized
    await pro_mode_service.initialize()
    dsn = config['postgresql']['dsn']
    conn = await asyncpg.connect(dsn=dsn)
    try:
        rows = await _fetch_messages(conn, limit=limit, since=since)
        logger.info(f"Индексация: получено {len(rows)} сообщений")
        
        if not rows:
            logger.info("Нет сообщений для индексации")
            return {"processed": 0, "indexed": 0}
        
        processed = 0
        indexed = 0
        
        for row in rows:
            text = row['text'] or ''
            if not text.strip():
                logger.info(f"Пропускаем сообщение {row['message_id']} - пустой текст")
                continue
            
            try:
                await embedding_service.process_message(
                    message_id=row['message_id'],
                    text=text,
                    channel_id=row['channel_id'],
                    published_at=(row['published_at'].isoformat() if row['published_at'] else None)
                )
                indexed += 1
                logger.info(f"Сообщение {row['message_id']} успешно проиндексировано")
            except Exception as e:
                logger.error(f"Ошибка индексации сообщения {row['message_id']}: {e}")
            
            processed += 1
            
            if processed % 10 == 0:
                logger.info(f"Обработано {processed}/{len(rows)} сообщений, проиндексировано: {indexed}")
        
        logger.info(f"Индексация завершена: обработано {processed}, проиндексировано {indexed}")
        return {"processed": processed, "indexed": indexed}
        
    except Exception as e:
        logger.error(f"Ошибка в _index_batch: {e}")
        raise
    finally:
        await conn.close()


async def _index_batch_with_settings(settings: dict):
    """Индексация сообщений с расширенными настройками"""
    config = get_config()
    
    # Инициализируем сервисы
    await pro_mode_service.initialize()
    
    # Настройки из параметров
    batch_size = settings.get('batch_size', 50)
    limit = settings.get('limit', 1000)
    threads = settings.get('threads', 4)
    model = settings.get('model', 'sberbank-ai/sbert_large_nlu_ru')
    min_text_length = settings.get('min_text_length', 10)
    days_back = settings.get('days_back', 0)
    skip_existing = settings.get('skip_existing', True)
    
    logger.info(f"🚀 Запуск индексации с настройками:")
    logger.info(f"   📊 Размер батча: {batch_size}")
    logger.info(f"   📈 Лимит сообщений: {limit}")
    logger.info(f"   🧵 Потоков: {threads}")
    logger.info(f"   🤖 Модель: {model}")
    logger.info(f"   📏 Мин. длина текста: {min_text_length}")
    logger.info(f"   📅 Период: {days_back if days_back > 0 else 'за все время'}")
    logger.info(f"   ⏭️ Пропускать существующие: {skip_existing}")
    
    dsn = config['postgresql']['dsn']
    conn = await asyncpg.connect(dsn=dsn)
    
    try:
        # Получаем сообщения с учетом настроек
        rows = await _fetch_messages_with_settings(
            conn, 
            limit=limit, 
            min_text_length=min_text_length,
            days_back=days_back,
            skip_existing=skip_existing
        )
        
        total_messages = len(rows)
        logger.info(f"📋 Найдено {total_messages} сообщений для индексации")
        
        if not rows:
            logger.info("ℹ️ Нет сообщений для индексации")
            return {"processed": 0, "indexed": 0, "total": 0}
        
        processed = 0
        indexed = 0
        
        # Обрабатываем сообщения батчами
        for i in range(0, total_messages, batch_size):
            batch = rows[i:i + batch_size]
            logger.info(f"🔄 Обработка батча {i//batch_size + 1}/{(total_messages + batch_size - 1)//batch_size}")
            
            for row in batch:
                text = row['text'] or ''
                
                # Проверяем длину текста
                if len(text.strip()) < min_text_length:
                    logger.debug(f"Пропускаем сообщение {row['message_id']} - текст слишком короткий ({len(text)} < {min_text_length})")
                    processed += 1
                    continue
                
                try:
                    await embedding_service.process_message(
                        message_id=row['message_id'],
                        text=text,
                        channel_id=row['channel_id'],
                        published_at=(row['published_at'].isoformat() if row['published_at'] else None)
                    )
                    indexed += 1
                    logger.debug(f"✅ Сообщение {row['message_id']} проиндексировано")
                except Exception as e:
                    logger.error(f"❌ Ошибка индексации сообщения {row['message_id']}: {e}")
                
                processed += 1
            
            # Логируем прогресс
            progress_percent = round((processed / total_messages) * 100, 1)
            logger.info(f"📊 Прогресс: {processed}/{total_messages} ({progress_percent}%), проиндексировано: {indexed}")
        
        logger.info(f"🎉 Индексация завершена!")
        logger.info(f"   📊 Обработано: {processed}")
        logger.info(f"   🔍 Проиндексировано: {indexed}")
        logger.info(f"   📈 Эффективность: {round((indexed/processed)*100, 1) if processed > 0 else 0}%")
        
        return {
            "processed": processed, 
            "indexed": indexed, 
            "total": total_messages,
            "settings": settings
        }
        
    except Exception as e:
        logger.error(f"💥 Ошибка в _index_batch_with_settings: {e}")
        raise
    finally:
        await conn.close()


async def _fetch_messages_with_settings(conn, limit: int = 1000, min_text_length: int = 10, days_back: int = 0, skip_existing: bool = True):
    """Получение сообщений с учетом настроек"""
    try:
        # Базовый запрос
        query = """
            SELECT m.id as message_id, m.text_content as text, m.channel_id, m.published_at
            FROM messages m
            WHERE m.text_content IS NOT NULL 
            AND LENGTH(m.text_content) >= $1
        """
        params = [min_text_length]
        param_count = 1
        
        # Добавляем фильтр по дате
        if days_back > 0:
            param_count += 1
            query += f" AND m.published_at >= NOW() - INTERVAL '{days_back} days'"
        
        # Добавляем фильтр для пропуска уже проиндексированных
        if skip_existing:
            query += """
                AND NOT EXISTS (
                    SELECT 1 FROM embeddings e 
                    WHERE e.message_id = m.message_id 
                    AND e.model = 'sberbank-ai/sbert_large_nlu_ru'
                )
            """
        
        # Добавляем сортировку и лимит
        query += " ORDER BY m.published_at ASC"
        if limit > 0:
            query += f" LIMIT {limit}"
        
        logger.info(f"🔍 Выполняем запрос: {query[:100]}...")
        rows = await conn.fetch(query, *params)
        
        logger.info(f"📋 Получено {len(rows)} сообщений из базы данных")
        return rows
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении сообщений: {e}")
        raise


@huey.task()
def update_task_status(task_id: str, status: str, result: str = None, error: str = None):
    """Задача для обновления статуса задачи в Redis"""
    import redis
    from config_utils import get_config
    import time
    
    try:
        config = get_config()
        redis_client = redis.Redis(
            host=config['redis']['host'],
            port=int(config['redis']['port']),
            decode_responses=True
        )
        
        task_key = f"huey:telegram-parser:task:{task_id}"
        mapping = {
            'status': status,
            'completed_at': str(time.time())
        }
        
        if result:
            mapping['result'] = str(result)
        if error:
            mapping['error'] = str(error)
            
        redis_client.hset(task_key, mapping=mapping)
        redis_client.expire(task_key, 3600)
        logger.info(f"✅ Статус задачи {task_id} обновлен на '{status}'")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления статуса задачи {task_id}: {e}")


@huey.task()
def index_batch_task(settings: dict):
    """Huey задача для индексации сообщений с настройками"""
    task_id = None
    
    try:
        # Получаем task_id из контекста Huey перед выполнением
        try:
            if hasattr(huey, '_current_task') and huey._current_task:
                task_id = str(huey._current_task.id)
                logger.info(f"🔍 Получен task_id из контекста Huey: {task_id}")
            else:
                logger.warning("⚠️ Не удалось получить task_id из контекста Huey")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения task_id из контекста Huey: {e}")
        
        # Выполняем индексацию
        result = asyncio.run(_index_batch_with_settings(settings))
        
        # Обновляем статус после завершения
        if task_id:
            update_indexing_status(task_id, 'finished', result=str(result))
            logger.info(f"✅ Индексация завершена для задачи {task_id}")
        else:
            logger.warning("⚠️ task_id не найден, статус не обновлен")
        
        logger.info(f"✅ Индексация завершена успешно: {result}")
        
        return result
        
    except Exception as e:
        # При ошибке также обновляем статус
        if task_id:
            update_indexing_status(task_id, 'error', error=str(e))
            logger.error(f"❌ Ошибка индексации для задачи {task_id}: {e}")
        else:
            logger.error(f"❌ Ошибка индексации: {e}")
        
        raise


@huey.task()
def update_indexing_status(task_id: str, status: str, result: str = None, error: str = None):
    """Задача для обновления статуса индексации в Redis"""
    import redis
    from config_utils import get_config
    import time
    
    try:
        config = get_config()
        redis_client = redis.Redis(
            host=config['redis']['host'],
            port=int(config['redis']['port']),
            decode_responses=True
        )
        
        task_key = f"huey:telegram-parser:task:{task_id}"
        mapping = {
            'status': status,
            'completed_at': str(time.time())
        }
        
        if result:
            mapping['result'] = str(result)
        if error:
            mapping['error'] = str(error)
            
        redis_client.hset(task_key, mapping=mapping)
        redis_client.expire(task_key, 3600)
        logger.info(f"✅ Статус задачи {task_id} обновлен на '{status}'")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления статуса задачи {task_id}: {e}")


@huey.task()
def check_task_completion(task_id: str):
    """Задача для проверки завершения задачи и обновления статуса"""
    import redis
    from config_utils import get_config
    import time
    
    try:
        config = get_config()
        redis_client = redis.Redis(
            host=config['redis']['host'],
            port=int(config['redis']['port']),
            decode_responses=True
        )
        
        # Проверяем статус задачи в Huey
        task_key = f"huey:telegram-parser:task:{task_id}"
        task_data = redis_client.hgetall(task_key)
        
        if not task_data:
            logger.warning(f"⚠️ Задача {task_id} не найдена в Redis")
            return
        
        # Проверяем статус задачи через Redis напрямую
        try:
            # Проверяем разные возможные ключи для результата задачи
            possible_result_keys = [
                f"huey:telegram-parser:result:{task_id}",
                f"huey:result:{task_id}",
                f"huey:telegram-parser:{task_id}",
                f"huey:{task_id}"
            ]
            
            result_found = False
            for result_key in possible_result_keys:
                result_data = redis_client.get(result_key)
                if result_data:
                    # Задача завершена успешно
                    update_indexing_status(task_id, 'finished', result=result_data)
                    logger.info(f"✅ Задача {task_id} завершена успешно: {result_data}")
                    result_found = True
                    break
            
            if not result_found:
                # Проверяем разные возможные ключи для ошибки
                possible_error_keys = [
                    f"huey:telegram-parser:error:{task_id}",
                    f"huey:error:{task_id}"
                ]
                
                error_found = False
                for error_key in possible_error_keys:
                    error_data = redis_client.get(error_key)
                    if error_data:
                        update_indexing_status(task_id, 'error', error=error_data)
                        logger.error(f"❌ Задача {task_id} завершена с ошибкой: {error_data}")
                        error_found = True
                        break
                
                if not error_found:
                    # Проверяем, есть ли задача в очереди выполнения
                    # Если задача не найдена в результатах и ошибках, возможно она еще выполняется
                    # Но если прошло много времени, возможно она завершилась
                    current_time = time.time()
                    started_at = float(task_data.get('started_at', current_time))
                    elapsed_time = current_time - started_at
                    
                    if elapsed_time > 300:  # 5 минут
                        # Если прошло больше 5 минут, считаем задачу завершенной
                        update_indexing_status(task_id, 'finished', result="Задача выполнена (таймаут)")
                        logger.info(f"✅ Задача {task_id} завершена по таймауту")
                    else:
                        # Задача еще выполняется - планируем повторную проверку через 5 секунд
                        logger.info(f"🔄 Задача {task_id} еще выполняется ({elapsed_time:.1f}с), повторная проверка через 5 сек")
                        try:
                            check_task_completion.schedule(args=(task_id,), delay=5)
                        except Exception as e:
                            logger.warning(f"Не удалось запланировать повторную проверку: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка проверки статуса задачи {task_id}: {e}")
            # Fallback - планируем повторную проверку
            try:
                check_task_completion.schedule(args=(task_id,), delay=5)
            except Exception as e2:
                logger.warning(f"Не удалось запланировать повторную проверку: {e2}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки статуса задачи {task_id}: {e}")


@huey.task()
def reprocess_deduplication_task(threshold: float = 0.75, limit: int = 1000):
    """Задача переобработки дедупликации с улучшенными параметрами"""
    return asyncio.run(_reprocess_deduplication(threshold=threshold, limit=limit))

@huey.task()
def reclassify_messages_task(threshold: float = 0.8, limit: int = 1000):
    """Задача переклассификации сообщений с новым порогом"""
    return asyncio.run(_reclassify_messages(threshold=threshold, limit=limit))


async def _reprocess_deduplication(threshold: float = 0.75, limit: int = 1000):
    """Переобработать дедупликацию с новыми параметрами"""
    try:
        from pro_mode.deduplication_service import deduplication_service
        
        logger.info(f"Начинаем переобработку дедупликации с порогом {threshold} и лимитом {limit}")
        
        result = await deduplication_service.reprocess_all_messages(threshold, limit)
        
        logger.info(f"Переобработка завершена: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка переобработки дедупликации: {e}")
        raise

async def _reclassify_messages(threshold: float = 0.8, limit: int = 1000):
    """Переклассифицировать сообщения с новым порогом"""
    try:
        from pro_mode.classification_service import classification_service
        import asyncpg
        from config_utils import get_config
        
        logger.info(f"Начинаем переклассификацию с порогом {threshold} и лимитом {limit}")
        
        config = get_config()
        conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
        
        # Очищаем существующие классификации
        await conn.execute("DELETE FROM message_topics")
        logger.info("Существующие классификации очищены")
        
        # Получаем сообщения для переклассификации
        messages = await conn.fetch("""
            SELECT m.id, m.text_content 
            FROM messages m 
            WHERE m.text_content IS NOT NULL 
            AND LENGTH(m.text_content) > 10
            ORDER BY m.id DESC
            LIMIT $1
        """, limit)
        
        logger.info(f"Найдено {len(messages)} сообщений для переклассификации")
        
        processed = 0
        classified = 0
        
        for message in messages:
            try:
                message_id = message['id']
                text = message['text_content']
                
                # Классифицируем сообщение
                classifications = await classification_service.classify_message(message_id, text)
                
                if classifications:
                    classified += 1
                
                processed += 1
                
                if processed % 50 == 0:
                    logger.info(f"Обработано {processed}/{len(messages)} сообщений")
                    
            except Exception as e:
                logger.error(f"Ошибка классификации сообщения {message['id']}: {e}")
                continue
        
        await conn.close()
        
        result = {
            'processed': processed,
            'classified': classified,
            'threshold': threshold
        }
        
        logger.info(f"Переклассификация завершена: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка переклассификации: {e}")
        raise


@huey.task()
def index_messages_batch(limit: int = 1000, since: Optional[str] = None):
    """Поставить задачу индексации батча сообщений"""
    return asyncio.run(_index_batch(limit=limit, since=since))


@huey.task()
def index_new_messages_worker():
    """Периодическая индексация новых сообщений (каждые 10 минут)"""
    # Индексируем последние ~1000 по дате
    return asyncio.run(_index_batch(limit=1000))


# ============================================================================
# TOPIC MODELING TASKS
# ============================================================================

@huey.task()
def run_topic_modeling_pipeline(limit: Optional[int] = None, days_back: int = 30, run_classification: bool = True):
    """
    Запуск полного пайплайна тематического моделирования
    
    Args:
        limit: Лимит постов для обработки (None = без ограничений)
        days_back: Количество дней назад для загрузки постов
        run_classification: Запускать ли классификацию сообщений
    
    Returns:
        Словарь со статистикой выполнения
    """
    try:
        from pro_mode.topic_modeling_service import TopicModelingService
        
        logger.info("🚀 Запуск задачи тематического моделирования через Huey")
        logger.info(f"   Параметры: limit={limit}, days_back={days_back}, run_classification={run_classification}")

        task_id = None
        try:
            if hasattr(huey, '_current_task') and huey._current_task:
                task_id = str(huey._current_task.id)
        except Exception:
            task_id = None
        progress_tracker = TopicModelingProgressTracker(task_id)
        
        async def _run_pipeline():
            service = TopicModelingService(progress_tracker=progress_tracker)
            
            # Модифицируем метод загрузки для поддержки параметров
            original_fetch = service._fetch_posts_from_db
            async def fetch_with_params(limit_param=None, days_back_param=30, **kwargs):
                effective_limit = limit if limit is not None else (limit_param if limit_param is not None else kwargs.get("limit"))
                effective_days = days_back if days_back != 30 else kwargs.get("days_back", days_back_param)
                return await original_fetch(
                    limit=effective_limit,
                    days_back=effective_days
                )
            service._fetch_posts_from_db = fetch_with_params
            
            result = await service.run_full_pipeline(fetch_from_db=True, run_classification=run_classification)
            return result
        
        result = asyncio.run(_run_pipeline())
        
        logger.info("✅ Задача тематического моделирования завершена")
        logger.info(f"   Результат: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка в задаче тематического моделирования: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


