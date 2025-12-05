# parser_app/data_writer.py

import asyncio
import asyncpg
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DataWriter(ABC):
    @abstractmethod
    async def write_batch(self, data: List) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

class PostgresWriter(DataWriter):
    """
    PostgreSQL writer с улучшенной поддержкой метаданных каналов и обработкой ошибок.
    """
    
    def __init__(self, dsn: str, pool_size: int = 10):
        self.dsn = dsn
        self.pool_size = pool_size
        self.pool: Optional[asyncpg.Pool] = None

    async def get_pool(self) -> asyncpg.Pool:
        """Получает пул соединений с базой данных."""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    dsn=self.dsn,
                    min_size=1,
                    max_size=self.pool_size,
                    command_timeout=60  # Увеличиваем timeout
                )
                logger.info("Соединение с PostgreSQL установлено.")
            except Exception as e:
                logger.error(f"Ошибка подключения к PostgreSQL: {e}")
                raise
        return self.pool

    async def save_channel_metadata(self, channel_metadata: Dict[str, Any]) -> None:
        """
        Сохраняет или обновляет метаданные канала в таблице channels.
        
        Args:
            channel_metadata: Словарь с метаданными канала
        """
        if not channel_metadata:
            logger.warning("Переданы пустые метаданные канала")
            return
            
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            try:
                # Подготавливаем данные для вставки/обновления
                channel_data = (
                    channel_metadata.get('id'),
                    channel_metadata.get('title', ''),
                    channel_metadata.get('description', ''),
                    channel_metadata.get('username'),
                    datetime.utcnow()  # last_parsed_at
                )
                
                # Используем ON CONFLICT для обновления существующих записей
                query = """
                    INSERT INTO channels (id, name, description, username, last_parsed_at)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        username = EXCLUDED.username,
                        last_parsed_at = EXCLUDED.last_parsed_at
                """
                
                await conn.execute(query, *channel_data)
                
                logger.info(f"Метаданные канала {channel_metadata.get('title')} (ID: {channel_metadata.get('id')}) сохранены в БД")
                
            except Exception as e:
                logger.error(f"Ошибка при сохранении метаданных канала: {e}")
                raise

    def _parse_datetime(self, date_str: str) -> datetime:
        """
        Преобразует строку даты в объект datetime.
        
        Args:
            date_str: Строка с датой в формате ISO
            
        Returns:
            datetime: Объект datetime
        """
        if not date_str:
            return datetime.utcnow()
            
        try:
            # Пробуем разобрать ISO формат
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            try:
                # Альтернативный формат с миллисекундами
                import dateutil.parser
                return dateutil.parser.parse(date_str)
            except:
                logger.warning(f"Не удалось разобрать дату: {date_str}, используем текущую дату")
                return datetime.utcnow()

    async def write_batch(self, data: List[Dict[str, Any]]) -> None:
        """
        Записывает пакет сообщений в базу данных с улучшенной обработкой ошибок.
        
        Args:
            data: Список словарей с данными сообщений
        """
        if not data:
            logger.debug("Передан пустой пакет данных")
            return

        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Подготавливаем данные для batch insert сообщений
                    messages_to_insert = []
                    for item in data:
                        try:
                            # Извлекаем и валидируем данные сообщения
                            # Адаптируем для работы с новым форматом MessageProcessor
                            message_id = item.get('message_id') or item.get('MessageID')
                            channel_id = item.get('channel_id') or item.get('ID')
                            
                            if not message_id or not channel_id:
                                logger.warning(f"Пропускаем сообщение без ID: {item}")
                                continue
                            
                            # Получаем дату и преобразуем её в объект datetime
                            date_str = item.get('date') or item.get('Date')
                            published_at = self._parse_datetime(date_str) if isinstance(date_str, str) else date_str
                            
                            # Подготавливаем данные для записи
                            message_data = (
                                int(message_id),
                                int(channel_id),
                                item.get('text') or item.get('Original', ''),  # text_content
                                published_at,  # published_at как объект datetime
                                item.get('content_type') or item.get('ContentType', 'text'),  # content_type  
                                item.get('views') or item.get('Views', 0) or 0,  # views_count
                                item.get('forwards') or item.get('Forwards', 0) or 0,  # forwards_count
                                item.get('reactions') or json.dumps(item.get('Reactions', {}), ensure_ascii=False) if item.get('Reactions') else '{}',  # reactions
                                item.get('comments_count') or item.get('CommentsCount', 0) or 0,  # comments_count
                                json.dumps(item, ensure_ascii=False)  # raw_message - сохраняем всё сообщение как JSON
                            )
                            messages_to_insert.append(message_data)
                            
                        except Exception as e:
                            logger.warning(f"Ошибка при подготовке сообщения для записи: {e}. Данные: {item}")
                            continue

                    if not messages_to_insert:
                        logger.warning("Нет валидных сообщений для записи в пакете")
                        return

                    # Batch insert сообщений с ON CONFLICT DO NOTHING
                    query = """
                        INSERT INTO messages (
                            message_id, channel_id, text_content, published_at, 
                            content_type, views_count, forwards_count, reactions, 
                            comments_count, raw_message
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (channel_id, message_id) DO NOTHING
                    """
                    
                    result = await conn.executemany(query, messages_to_insert)
                    
                    logger.info(f"Записано {len(messages_to_insert)} сообщений в БД")
                    
                except asyncpg.DataError as e:
                    logger.error(f"Ошибка данных при записи batch: {e}")
                    raise
                except asyncpg.IntegrityConstraintViolationError as e:
                    logger.warning(f"Нарушение целостности при записи batch: {e}")
                    # Не прерываем выполнение, так как это может быть дубликат
                except Exception as e:
                    logger.error(f"Неожиданная ошибка при записи batch данных: {e}")
                    raise

    async def close(self) -> None:
        """Закрывает пул соединений."""
        if self.pool:
            await self.pool.close()
            logger.info("Соединение с PostgreSQL закрыто.")

class CSVWriter(DataWriter):
    """
    CSV writer для экспорта данных в файлы (резервная опция).
    """
    
    def __init__(self, base_filename: str = "telegram_data"):
        self.base_filename = base_filename
        self.channels_file = None
        self.messages_file = None
        self.channels_written = set()

    async def write_batch(self, data: List[Dict[str, Any]]) -> None:
        """Записывает данные в CSV файлы."""
        import csv
        import os
        
        # Создаем файлы если они не существуют
        channels_path = f"{self.base_filename}_channels.csv"
        messages_path = f"{self.base_filename}_messages.csv"
        
        # Записываем каналы
        channels_to_write = []
        for item in data:
            channel_id = item.get('channel_id') or item.get('ID')
            if channel_id and channel_id not in self.channels_written:
                channel_data = {
                    'id': channel_id,
                    'name': item.get('channel_title', ''),
                    'description': item.get('channel_description', ''),
                    'username': item.get('channel_username', ''),
                    'last_parsed_at': datetime.utcnow().isoformat()
                }
                channels_to_write.append(channel_data)
                self.channels_written.add(channel_id)
        
        if channels_to_write:
            file_exists = os.path.exists(channels_path)
            with open(channels_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['id', 'name', 'description', 'username', 'last_parsed_at'])
                if not file_exists:
                    writer.writeheader()
                writer.writerows(channels_to_write)
        
        # Записываем сообщения
        if data:
            file_exists = os.path.exists(messages_path)
            with open(messages_path, 'a', newline='', encoding='utf-8') as f:
                fieldnames = ['message_id', 'channel_id', 'text_content', 'published_at', 'content_type', 
                            'views_count', 'forwards_count', 'reactions', 'comments_count']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                
                for item in data:
                    try:
                        # Адаптация для работы с новым форматом MessageProcessor
                        row = {
                            'message_id': item.get('message_id') or item.get('MessageID'),
                            'channel_id': item.get('channel_id') or item.get('ID'),
                            'text_content': item.get('text') or item.get('Original', ''),
                            'published_at': item.get('date') or item.get('Date'),
                            'content_type': item.get('content_type') or item.get('ContentType', 'text'),
                            'views_count': item.get('views') or item.get('Views', 0),
                            'forwards_count': item.get('forwards') or item.get('Forwards', 0),
                            'reactions': item.get('reactions') or json.dumps(item.get('Reactions', {})),
                            'comments_count': item.get('comments_count') or item.get('CommentsCount', 0)
                        }
                        writer.writerow(row)
                    except Exception as e:
                        logger.warning(f"Ошибка при записи сообщения в CSV: {e}")
                        continue

    async def close(self) -> None:
        """Завершает работу CSV writer."""
        logger.info("CSV Writer закрыт.")