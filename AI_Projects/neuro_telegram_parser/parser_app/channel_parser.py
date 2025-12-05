import asyncio
import logging
from typing import AsyncGenerator, Dict, List, Optional, Union

from pyrogram import errors
from pyrogram.enums import ChatType
from pyrogram.types import Chat, Message
from pyrogram.raw import functions

from parser_app.telegram_client_manager import TelegramClientManager

logger = logging.getLogger(__name__)


class ChannelParser:
    def __init__(self, client_manager: TelegramClientManager):
        self.client_manager = client_manager
        self.dialogs_cache: Dict[int, Chat] = {}
        self.dialogs_loaded = False

    async def load_user_dialogs(self) -> Dict[int, Chat]:
        if self.dialogs_loaded:
            return self.dialogs_cache

        client = await self.client_manager.get_client()
        try:
            async for dialog in client.get_dialogs():
                chat = dialog.chat
                self.dialogs_cache[chat.id] = chat
            self.dialogs_loaded = True
            logger.info(f"✅ Загружено {len(self.dialogs_cache)} диалогов")
        except Exception as e:
            logger.error(f"Ошибка загрузки диалогов: {e}")
        return self.dialogs_cache

    def format_ids(self, channel_id: int) -> List[int]:
        """
        Возвращает несколько вариантов ID для поиска: 
        исходный, без -100 префикса, а также -100<core>.
        """
        ids = {channel_id}
        sid = str(channel_id)
        if channel_id < 0 and sid.startswith("-100"):
            core = int(sid[4:])
            ids.update({core, -core})
        elif channel_id < 0:
            abs_id = abs(channel_id)
            ids.update({abs_id, int(f"-100{abs_id}")})
        else:
            # Положительный raw ID
            ids.update({int(f"-100{channel_id}"), -channel_id})
        return list(ids)

    async def try_join_channel(self, client, chat_id: int) -> bool:
        """
        Пробует присоединиться к каналу по разным форматам ID.
        """
        for fmt in self.format_ids(chat_id):
            try:
                await client.join_chat(fmt)
                logger.info(f"✅ Успешный join_chat({fmt})")
                return True
            except Exception as e:
                logger.debug(f"join_chat({fmt}) не удался: {e}")
        return False

    async def get_channel_info(
        self, channel_identifier: Union[int, str]
    ) -> Optional[Chat]:
        client = await self.client_manager.get_client()

        # 1. По username
        if isinstance(channel_identifier, str):
            uname = channel_identifier.lstrip("@")
            try:
                chat = await client.get_chat(uname)
                logger.info(f"✅ Найден по username: {chat.title} (@{chat.username})")
                return chat
            except Exception:
                pass

        # 2. По ID через диалоги и get_chat
        cid = None
        try:
            if isinstance(channel_identifier, (int, str)) and str(channel_identifier).isdigit():
                cid = int(channel_identifier)
        except (ValueError, TypeError):
            pass
            
        if cid is not None:
            # Поиск в диалогах
            dialogs = await self.load_user_dialogs()
            for fmt in self.format_ids(cid):
                if fmt in dialogs:
                    chat = dialogs[fmt]
                    logger.info(f"✅ Найден в диалогах: {chat.title} (ID: {fmt})")
                    return chat

            # Прямые get_chat
            for fmt in self.format_ids(cid):
                try:
                    chat = await client.get_chat(fmt)
                    logger.info(f"✅ Найден через get_chat: {chat.title} (ID: {fmt})")
                    return chat
                except (errors.FloodWait) as e:
                    logger.warning(f"FloodWait({fmt}), жду {e.value}s")
                    await asyncio.sleep(e.value)
                except (errors.ChannelPrivate, errors.PeerIdInvalid, errors.ChannelInvalid, errors.Forbidden):
                    continue
                except Exception as e:
                    logger.debug(f"get_chat({fmt}) ошибка: {e}")

            # Попытка join если get_chat не помог
            if await self.try_join_channel(client, cid):
                try:
                    chat = await client.get_chat(cid)
                    logger.info(f"✅ Найден после join: {chat.title} (ID: {cid})")
                    return chat
                except Exception:
                    pass

        # 3. По username из channel_info
        # (реализуется во внешней логике, если доступен username)

        logger.error(f"❌ Канал {channel_identifier} не найден")
        return None

    async def parse_channel_complete(
        self, channel_identifier: Union[int, str], limit: int = None, days_back: int = 0
    ) -> Dict:
        logger.info(f"🚀 Старт parse_channel_complete({channel_identifier})")
        logger.info(f"   📅 Период парсинга: {days_back if days_back > 0 else 'за все время'}")
        chat = await self.get_channel_info(channel_identifier)
        if not chat:
            return {"success": False, "error": f"{channel_identifier} not found"}

        # Дальше логика парсинга сообщений:
        messages = []
        counter = 0
        async for msg in self._iter_messages(chat, limit, days_back):
            messages.append(msg)
            counter += 1
        return {
            "success": True,
            "channel_metadata": {"id": chat.id, "title": chat.title, "username": chat.username},
            "message_count": counter,
            "messages": messages,
        }

    async def _iter_messages(self, chat: Chat, limit: int = None, days_back: int = 0) -> AsyncGenerator[Message, None]:
        client = await self.client_manager.get_client()
        
        # Если указан период парсинга, вычисляем дату начала и конца
        start_date = None
        end_date = None
        if days_back > 0:
            from datetime import datetime, timedelta
            # Pyrogram возвращает даты в местном времени (UTC+3), поэтому используем local time
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            logger.info(f"   📅 Парсинг сообщений с {start_date.strftime('%Y-%m-%d %H:%M:%S')} Local по {end_date.strftime('%Y-%m-%d %H:%M:%S')} Local")
        
        # Сначала собираем сообщения, затем фильтруем
        messages = []
        message_count = 0
        
        # Парсим сообщения без фильтрации (сначала получаем самые свежие)
        async for message in client.get_chat_history(chat.id, limit=limit * 3 if limit else None):  # Берем в 3 раза больше для фильтрации
            messages.append(message)
            message_count += 1
            
            # Останавливаемся если достигли лимита * 3 (для последующей фильтрации)
            if limit and message_count >= limit * 3:
                break
        
        logger.info(f"   📊 Получено {len(messages)} сообщений для фильтрации")
        
        # Теперь фильтруем по дате и применяем лимит
        filtered_count = 0
        for message in messages:
            # Если указан период, фильтруем по дате
            if start_date is not None and end_date is not None:
                if message.date:
                    # Конвертируем дату сообщения в UTC для сравнения
                    # message.date уже в UTC, но может иметь timezone info
                    if message.date.tzinfo is not None:
                        message_utc = message.date.replace(tzinfo=None)
                    else:
                        message_utc = message.date
                    
                    # Проверяем, что сообщение в нужном диапазоне
                    if message_utc < start_date or message_utc > end_date:
                        continue  # Пропускаем сообщения вне диапазона
            
            yield message
            filtered_count += 1
            
            # Останавливаемся если достигли лимита
            if limit and filtered_count >= limit:
                break
        
        logger.info(f"   📊 После фильтрации: {filtered_count} сообщений")