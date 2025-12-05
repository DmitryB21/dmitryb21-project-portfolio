# parser_app/channel_searcher.py
from typing import List, Dict, Any
from pyrogram.raw import functions
from pyrogram.raw.types import Channel
from parser_app.telegram_client_manager import TelegramClientManager
import logging


logger = logging.getLogger(__name__)

class ChannelSearcher:
    """
    Предоставляет функционал для поиска публичных Telegram-каналов
    по ключевым словам.
    """
    def __init__(self, client_manager: TelegramClientManager):
        self.client_manager = client_manager

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
      if not query:
        return []

      client = await self.client_manager.get_client()
      found = []

      try:
        result = await client.invoke(
            functions.contacts.Search(q=query, limit=limit)
        )
        for chat in result.chats:
            # Только каналы (broadcast) без megagroup
            if isinstance(chat, Channel) and getattr(chat, "broadcast", False) and not getattr(chat, "megagroup", False):
                found.append({
                    "id": chat.id,
                    "access_hash": chat.access_hash,
                    "title": chat.title,
                    "username": getattr(chat, "username", None)
                })
      except Exception as e:
        logger.error(f"Ошибка при поиске каналов: {e}")
      return found