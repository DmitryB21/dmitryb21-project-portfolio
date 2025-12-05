# tasks.py
import os
import asyncio
import logging
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from redis import Redis

from huey_config import huey
from config_utils import get_config 
from parser_app.channel_parser import ChannelParser
from parser_app.message_processor import MessageProcessor
from parser_app.data_writer import PostgresWriter
from parser_app.telegram_client_manager import TelegramClientManager
from parser_app.channel_provider import (
    load_channels_from_file, 
    extract_channel_identifier, 
    validate_channel_data
)

# Импорт задач Pro-режима для регистрации в Huey
from pro_mode.tasks_pro import index_messages_batch, index_new_messages_worker

# Настройка детального логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('telegram_parser.log', encoding='utf-8'),
        logging.FileHandler('parser_progress.log', encoding='utf-8')  # Отдельный файл для прогресса
    ]
)

logger = logging.getLogger(__name__)
progress_logger = logging.getLogger('progress')

# Настройка отдельного файла для прогресса
progress_handler = logging.FileHandler('parser_progress.log', encoding='utf-8')
progress_handler.setFormatter(logging.Formatter('%(asctime)s - PROGRESS - %(message)s'))
progress_logger.addHandler(progress_handler)
progress_logger.setLevel(logging.INFO)

BATCH_SIZE = 100

# Инициализация Redis из конфигурации
config = get_config()
redis_conn = Redis(
    host=config['redis']['host'],
    port=int(config['redis']['port']),
    db=int(config['redis'].get('db', 0)),
    decode_responses=True
)

def update_task_status(task_id: str, status: str, progress: dict = None, error: str = None):
    """Обновляет статус задачи в Redis"""
    key = f"task_status:{task_id}"
    
    # Подготовка данных для сохранения
    status_data = {
        'status': status,
        'updated_at': datetime.now().isoformat()
    }
    
    if progress:
        status_data['progress'] = json.dumps(progress)
    
    if error:
        status_data['error'] = error
    
    # Устанавливаем start_time только если его еще нет
    if not redis_conn.hexists(key, 'start_time'):
        status_data['start_time'] = datetime.now().isoformat()
    
    # Сохраняем данные в Redis - используем альтернативный метод для совместимости
    try:
        # Пробуем использовать mapping параметр (для новых версий Redis)
        redis_conn.hset(key, mapping=status_data)
    except Exception as e:
        # Если не сработало, используем старый формат (для старых версий Redis)
        for field, value in status_data.items():
            redis_conn.hset(key, field, value)
    
    # Устанавливаем TTL для записи (7 дней)
    redis_conn.expire(key, 60 * 60 * 24 * 7)
    
    # Логирование в специальный файл прогресса
    log_data = {
        'task_id': task_id,
        'status': status,
        'progress': progress,
        'error': error,
        'timestamp': datetime.now().isoformat()
    }
    progress_logger.info(json.dumps(log_data, ensure_ascii=False))
    

def get_task_status(task_id: str) -> Dict[str, Any]:
    """Получает статус задачи из Redis"""
    key = f"task_status:{task_id}"
    status_data_raw = redis_conn.hgetall(key)
    
    if not status_data_raw:
        return {
            'status': 'not_found',
            'progress': {},
            'error': 'Task not found',
            'updated_at': None,
            'start_time': None
        }
    
    # Обработка данных из Redis
    status_data = {
        'status': status_data_raw.get('status', 'unknown'),
        'progress': json.loads(status_data_raw.get('progress', '{}')),
        'error': status_data_raw.get('error'),
        'updated_at': status_data_raw.get('updated_at'),
        'start_time': status_data_raw.get('start_time')
    }
    
    return status_data

async def parse_single_channel_async(channel_info: dict, limit: int, days_back: int = 0, task_id: str = None, channel_index: int = 0, total_channels: int = 1):
    """Асинхронное парсинг одного канала с детальным логированием"""
    config = get_config()
    POSTGRES_DSN = config['postgresql']['dsn']
    
    # Создаем уникальное имя сессии для этой задачи
    session_name = f"telegram_parser_task_{task_id or datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Создаем клиент-менеджер для этой задачи
    client_manager = None
    
    try:
        # Сначала пробуем username (важно для JSON без числового ID)
        channel_username = (channel_info.get('username') or '').strip()
        if channel_username:
            channel_identifier = channel_username.lstrip('@')
            channel_display_name = f"{channel_info.get('title', channel_info.get('name',''))} (@{channel_identifier})".strip()
            channel_id = channel_info.get('id')  # может быть None
        else:
            # Если username нет, пытаемся извлечь числовой ID
            channel_id = extract_channel_identifier(channel_info)
            channel_identifier = channel_id
            channel_display_name = f"Channel_{channel_id}"
    except (ValueError, TypeError) as e:
        logger.error(f"❌ Некорректные данные канала {channel_info}: {e}")
        if task_id:
            update_task_status(task_id, 'failed', error=f"Некорректные данные канала: {e}")
        return

    # Инициализация прогресса
    if task_id:
        update_task_status(task_id, 'running', {
            'channel_index': channel_index,
            'total_channels': total_channels,
            'current_channel': channel_display_name,
            'stage': 'initializing',
            'messages_processed': 0,
            'total_messages': 0
        })

    logger.info(f"🚀 Начало задачи парсинга для канала: {channel_display_name} (ID: {channel_id})")
    logger.info(f"   📊 Лимит сообщений: {limit or 'не установлен'}")
    logger.info(f"   📍 Канал {channel_index + 1} из {total_channels}")
    logger.info(f"   🔑 Сессия: {session_name}")

    writer = PostgresWriter(dsn=POSTGRES_DSN)
    
    try:
        # Этап 1: Инициализация клиента Telegram
        logger.info("🔍 Инициализируем клиент Telegram...")
        if task_id:
            update_task_status(task_id, 'running', {
                'channel_index': channel_index,
                'total_channels': total_channels,
                'current_channel': channel_display_name,
                'stage': 'initializing_client',
                'messages_processed': 0,
                'total_messages': 0
            })
        
        # Получаем API ID и API HASH из конфигурации
        API_ID = int(config['telegram']['api_id'])
        API_HASH = config['telegram']['api_hash']
        
        # Создаем клиент-менеджер
        client_manager = TelegramClientManager(
            api_id=API_ID,
            api_hash=API_HASH,
            session_name=session_name
        )
        
        # Получаем клиент (автоматически создается и запускается)
        telegram_client = await client_manager.get_client()
        
        # Проверка подключения
        if not await client_manager.test_connection():
            error_msg = "Не удалось подключиться к Telegram"
            logger.error(f"❌ {error_msg}")
            if task_id:
                update_task_status(task_id, 'failed', error=error_msg)
            return
        
        # Этап 2: Получение информации о клиенте
        client_info = await client_manager.get_client_info()
        
        logger.info(f"✅ Подключение установлено")
        logger.info(f"   👤 Пользователь: {client_info.get('first_name', '')} (@{client_info.get('username', 'нет')})")
        logger.info(f"   📱 Телефон: {client_info.get('phone_number', 'скрыт')}")
        logger.info(f"   📊 Диалогов: {client_info.get('dialogs_count', 'N/A')}")

        # Создаем парсер с нашим клиентом-менеджером
        parser = ChannelParser(client_manager)

        # Этап 3: Парсинг канала
        logger.info("📡 Начинаем парсинг канала...")
        if task_id:
            update_task_status(task_id, 'running', {
                'channel_index': channel_index,
                'total_channels': total_channels,
                'current_channel': channel_display_name,
                'stage': 'parsing_channel',
                'messages_processed': 0,
                'total_messages': 0,
                'client_info': client_info
            })

        start_time = time.time()
        
        # Если доступен username, используем его для идентификации канала
        # иначе используем числовой ID
        channel_identifier_to_use = channel_username if channel_username else channel_id
        
        # Вызываем parse_channel_complete с правильными параметрами
        result = await parser.parse_channel_complete(
            channel_identifier_to_use,  # Используем username или ID
            limit=limit,
            days_back=days_back
        )
        
        if not result['success']:
            logger.error(f"❌ Ошибка парсинга канала {channel_display_name}: {result['error']}")
            if task_id:
                update_task_status(task_id, 'failed', error=result['error'])
            return

        # Этап 4: Обработка результатов
        channel_metadata = result['channel_metadata']
        messages = result['messages']
        message_count = result['message_count']
        
        # Обновляем display name с реальным именем канала, если оно доступно
        if channel_metadata.get('title'):
            channel_display_name = channel_metadata['title']
        
        logger.info(f"📊 Получены данные канала: {channel_display_name}")
        logger.info(f"   🆔 ID канала: {channel_metadata['id']}")
        logger.info(f"   👤 Username: @{channel_metadata['username'] or 'нет'}")
        logger.info(f"   📝 Описание: {(channel_metadata.get('description', '') or '')[:100]}{'...' if channel_metadata.get('description', '') and len(channel_metadata.get('description', '')) > 100 else ''}")
        logger.info(f"   👥 Участников: {channel_metadata.get('members_count', 'неизвестно')}")
        logger.info(f"   📋 Тип: {channel_metadata.get('type', 'неизвестно')}")
        logger.info(f"   ✅ Верифицирован: {'да' if channel_metadata.get('is_verified', False) else 'нет'}")

        # Этап 5: Сохранение метаданных канала
        logger.info("💾 Сохраняем метаданные канала...")
        if task_id:
            update_task_status(task_id, 'running', {
                'channel_index': channel_index,
                'total_channels': total_channels,
                'current_channel': channel_display_name,
                'stage': 'saving_metadata',
                'messages_processed': 0,
                'total_messages': message_count,
                'channel_info': {
                    'title': channel_metadata.get('title', ''),
                    'username': channel_metadata.get('username', ''),
                    'members_count': channel_metadata.get('members_count', 0)
                }
            })
            
        # Дополняем метаданные канала информацией из channel_info
        full_metadata = {**channel_metadata}
        if 'description' not in full_metadata or not full_metadata['description']:
            full_metadata['description'] = channel_info.get('description', '')
        if 'members_count' not in full_metadata:
            full_metadata['members_count'] = channel_info.get('members_count', 0)
        if 'type' not in full_metadata:
            full_metadata['type'] = channel_info.get('type', 'channel')
        if 'is_verified' not in full_metadata:
            full_metadata['is_verified'] = channel_info.get('is_verified', False)
            
        await writer.save_channel_metadata(full_metadata)
        logger.info(f"✅ Метаданные канала {channel_display_name} сохранены")

        # Этап 6: Обработка сообщений
        if messages:
            logger.info(f"📨 Обрабатываем {message_count} сообщений...")
            
            batch = []
            processed_count = 0
            
            for i, message in enumerate(messages, 1):
                try:
                    processed_message = MessageProcessor.process_message(message)
                    processed_message['channel_id'] = channel_metadata['id']
                    processed_message['channel_title'] = channel_metadata.get('title', '')
                    processed_message['channel_username'] = channel_metadata.get('username', '')
                    processed_message['channel_description'] = channel_metadata.get('description', '')
                    processed_message['raw_message'] = message.to_json() if hasattr(message, 'to_json') else str(message)
                    
                    batch.append(processed_message)
                    processed_count += 1

                    # Сохранение батча
                    if len(batch) >= BATCH_SIZE:
                        await writer.write_batch(batch)
                        logger.info(f"💾 Сохранен батч из {len(batch)} сообщений ({processed_count}/{message_count}) для {channel_display_name}")
                        
                        if task_id:
                            update_task_status(task_id, 'running', {
                                'channel_index': channel_index,
                                'total_channels': total_channels,
                                'current_channel': channel_display_name,
                                'stage': 'processing_messages',
                                'messages_processed': processed_count,
                                'total_messages': message_count,
                                'progress_percent': round((processed_count / message_count) * 100, 1) if message_count > 0 else 0,
                                'batch_size': len(batch)
                            })
                        
                        batch = []

                    # Прогресс каждые 50 сообщений
                    if i % 50 == 0:
                        logger.info(f"   ⏳ Обработано {i}/{message_count} сообщений...")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка обработки сообщения #{i} в канале {channel_display_name}: {e}")
                    continue

            # Сохранение оставшихся сообщений
            if batch:
                await writer.write_batch(batch)
                logger.info(f"💾 Сохранен финальный батч из {len(batch)} сообщений для {channel_display_name}")

            # Финальная статистика
            processing_time = time.time() - start_time
            logger.info(f"🎉 Парсинг канала {channel_display_name} завершен!")
            logger.info(f"   📊 Статистика:")
            logger.info(f"   ✅ Обработано сообщений: {processed_count}")
            logger.info(f"   📈 Всего сообщений в канале: {message_count}")
            logger.info(f"   🎯 Процент обработки: {round((processed_count/message_count)*100, 1) if message_count > 0 else 0}%")
            logger.info(f"   ⏱️ Время обработки: {round(processing_time, 1)} сек")
            logger.info(f"   🚀 Скорость: {round(processed_count/processing_time, 1) if processing_time > 0 else 0} сообщений/сек")
        else:
            logger.info(f"📭 В канале {channel_display_name} нет доступных сообщений")

        # Успешное завершение
        if task_id:
            update_task_status(task_id, 'completed', {
                'channel_index': channel_index,
                'total_channels': total_channels,
                'current_channel': channel_display_name,
                'stage': 'completed',
                'messages_processed': processed_count if messages else 0,
                'total_messages': message_count,
                'processing_time': round(processing_time, 1) if 'processing_time' in locals() else 0,
                'final_stats': {
                    'processed_messages': processed_count if messages else 0,
                    'total_messages': message_count,
                    'success_rate': round((processed_count/message_count)*100, 1) if message_count > 0 else 100,
                    'processing_time': round(processing_time, 1) if 'processing_time' in locals() else 0
                }
            })

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в парсинге канала {channel_display_name}: {e}")
        import traceback
        logger.error(f"📍 Трассировка: {traceback.format_exc()}")
        
        if task_id:
            update_task_status(task_id, 'failed', error=str(e))
        raise
        
    finally:
        # Освобождение ресурсов
        logger.info("🧹 Освобождаем ресурсы...")
        try:
            await writer.close()
            # Останавливаем клиент Telegram
            if client_manager:
                await client_manager.stop()
                logger.info(f"🔌 Клиент Telegram остановлен (сессия: {session_name})")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при освобождении ресурсов: {e}")
        
        logger.info(f"🔧 Ресурсы для задачи {channel_display_name} освобождены.")

@huey.task()
def run_single_channel_parse(channel_info: dict, limit: int, days_back: int = 0, task_id: str = None):
    """Задача Huey для парсинга одного канала"""
    return asyncio.run(parse_single_channel_async(channel_info, limit, days_back, task_id))

@huey.task()
def orchestrate_parsing_from_file(source_file_path: str, limit_per_channel: int = None, channel_limit: int = None, days_back: int = 0, task_id: str = None):
    """Оркестрация парсинга из CSV файла с детальным прогрессом"""
    
    logger.info(f"🚀 Запуск оркестрации парсинга из файла: {source_file_path}")
    logger.info(f"   📊 Лимит сообщений на канал: {limit_per_channel or 'не установлен'}")
    logger.info(f"   📈 Лимит каналов: {channel_limit or 'не установлен'}")
    logger.info(f"   📅 Период парсинга: {days_back if days_back > 0 else 'за все время'}")
    
    if task_id:
        update_task_status(task_id, 'running', {
            'stage': 'loading_channels',
            'source_file': source_file_path,
            'limit_per_channel': limit_per_channel,
            'channel_limit': channel_limit
        })

    # Загрузка каналов из файла
    channels_to_parse = load_channels_from_file(source_file_path)
    if not channels_to_parse:
        error_msg = f"Не удалось загрузить каналы из файла {source_file_path}. Проверьте формат файла и попробуйте снова."
        logger.error(f"❌ {error_msg}")
        if task_id:
            update_task_status(task_id, 'failed', error=error_msg)
        return

    # Валидация каналов
    valid_channels = [ch for ch in channels_to_parse if validate_channel_data(ch)]
    invalid_count = len(channels_to_parse) - len(valid_channels)
    
    if invalid_count > 0:
        logger.warning(f"⚠️ Пропущено {invalid_count} некорректных каналов")

    if not valid_channels:
        error_msg = "Не найдено ни одного валидного канала. Проверьте содержимое файла."
        logger.error(f"❌ {error_msg}")
        if task_id:
            update_task_status(task_id, 'failed', error=error_msg)
        return

    # Применение лимита каналов
    if channel_limit and channel_limit > 0 and channel_limit < len(valid_channels):
        logger.info(f"📊 Применяем лимит каналов: {channel_limit} из {len(valid_channels)}")
        valid_channels = valid_channels[:channel_limit]

    logger.info(f"📋 Будет обработано {len(valid_channels)} каналов.")

    if task_id:
        update_task_status(task_id, 'running', {
            'stage': 'scheduling_tasks',
            'total_channels': len(valid_channels),
            'valid_channels': len(valid_channels),
            'invalid_channels': invalid_count,
            'channels_scheduled': 0
        })

    # Планирование задач
    scheduled_count = 0
    for i, channel_info in enumerate(valid_channels):
        try:
            # Создание уникального ID подзадачи
            subtask_id = f"{task_id}_channel_{i}" if task_id else None
            
            # Планирование задачи для каждого канала (поддержка username или id)
            run_single_channel_parse(channel_info, limit_per_channel, days_back, subtask_id)
            scheduled_count += 1
            
            channel_label = channel_info.get('username') or channel_info.get('title') or channel_info.get('name') or channel_info.get('id') or 'Unknown'
            logger.info(f"📋 Задача поставлена для канала: {channel_label} ({i+1}/{len(valid_channels)})")
            
            if task_id:
                update_task_status(task_id, 'running', {
                    'stage': 'scheduling_tasks',
                    'total_channels': len(valid_channels),
                    'channels_scheduled': scheduled_count,
                    'current_channel_index': i + 1,
                    'current_channel': str(channel_label)
                })
                
        except Exception as e:
            logger.error(f"❌ Ошибка планирования задачи для канала {channel_info}: {e}")
            continue

    # Финальный статус
    logger.info(f"🎉 Оркестрация из файла завершена!")
    logger.info(f"   ✅ Задач поставлено: {scheduled_count}")
    logger.info(f"   ❌ Ошибок: {len(valid_channels) - scheduled_count}")
    
    if task_id:
        update_task_status(task_id, 'completed', {
            'stage': 'completed',
            'total_channels': len(valid_channels),
            'channels_scheduled': scheduled_count,
            'channels_failed': len(valid_channels) - scheduled_count,
            'source_file': source_file_path
        })

@huey.task()
def orchestrate_adhoc_parsing(channels: list, limit_per_channel: int = None, days_back: int = 0, task_id: str = None):
    """Оркестрация ad-hoc парсинга с детальным прогрессом"""
    
    logger.info(f"🚀 Запуск ad-hoc оркестрации для {len(channels)} каналов.")
    logger.info(f"   📅 Период парсинга: {days_back if days_back > 0 else 'за все время'}")
    
    if task_id:
        update_task_status(task_id, 'running', {
            'stage': 'validating_channels',
            'total_channels': len(channels),
            'limit_per_channel': limit_per_channel,
            'days_back': days_back
        })

    scheduled_count = 0
    error_count = 0
    
    for i, channel_data in enumerate(channels):
        try:
            if not validate_channel_data_enhanced(channel_data):
                logger.warning(f"⚠️ Пропускаем некорректный канал: {channel_data}")
                error_count += 1
                continue

            # Создание уникального ID подзадачи
            subtask_id = f"{task_id}_adhoc_{i}" if task_id else None
            
            run_single_channel_parse(channel_data, limit_per_channel, days_back, subtask_id)
            
            channel_name = channel_data.get('title', channel_data.get('id', 'Unknown'))
            scheduled_count += 1
            logger.info(f"📋 Ad-hoc задача поставлена для канала: {channel_name}")
            
            if task_id:
                update_task_status(task_id, 'running', {
                    'stage': 'scheduling_tasks',
                    'total_channels': len(channels),
                    'channels_scheduled': scheduled_count,
                    'channels_failed': error_count,
                    'current_channel_index': i + 1,
                    'current_channel': channel_name
                })
                
        except Exception as e:
            logger.error(f"❌ Ошибка ad-hoc планирования для канала {channel_data}: {e}")
            error_count += 1
            continue

    logger.info(f"🎉 Ad-hoc оркестрация завершена.")
    logger.info(f"   ✅ Задач поставлено: {scheduled_count}")
    logger.info(f"   ❌ Ошибок: {error_count}")
    
    if task_id:
        update_task_status(task_id, 'completed', {
            'stage': 'completed',
            'total_channels': len(channels),
            'channels_scheduled': scheduled_count,
            'channels_failed': error_count
        })

def validate_channel_data_enhanced(channel_info: Dict[str, Any]) -> bool:
    """Расширенная валидация данных канала для ad-hoc парсинга"""
    try:
        # Проверка наличия ID
        if 'id' not in channel_info:
            logger.error(f"❌ Отсутствует ID канала: {channel_info}")
            return False
            
        channel_id = channel_info['id']
        
        # Проверка типа ID - должен быть числом или строкой с числом
        if not isinstance(channel_id, (int, float, str)):
            logger.error(f"❌ Некорректный тип ID: {type(channel_id)} для {channel_info}")
            return False
            
        try:
            channel_id_int = int(channel_id)
        except (ValueError, TypeError):
            logger.error(f"❌ ID не является числом: {channel_info}")
            return False
            
        # Удаляем проверку на отрицательный ID, так как публичные каналы 
        # могут иметь положительные ID в Telegram
        
        # Проверка наличия названия или username
        title = channel_info.get('title', '').strip()
        username = channel_info.get('username', '')
        
        if not title and not username:
            logger.warning(f"⚠️ Отсутствует название и username канала: {channel_info}")
            # Создаем временное название
            channel_info['title'] = f"Channel_{abs(channel_id_int)}"
            
        logger.debug(f"✅ Канал валиден - ID:{channel_id_int}, title:'{title}', username:'{username}'")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка валидации канала {channel_info}: {e}")
        return False