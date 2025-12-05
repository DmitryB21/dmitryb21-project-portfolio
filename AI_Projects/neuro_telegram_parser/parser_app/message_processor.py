# parser_app/message_processor.py

import json
from typing import Dict, Any
from pyrogram.types import Message

class MessageProcessor:
    """
    Обрабатывает сырой объект Message от Pyrogram и трансформирует его
    в структурированный словарь в соответствии с целевой схемой.
    """
    @staticmethod
    def _determine_content_type(message: Message) -> str:
        """Определяет тип содержимого сообщения"""
        if message.photo:
            return "photo"
        if message.video:
            return "video"
        if message.document:
            return "document"
        if message.text:
            return "text"

    @staticmethod
    def _fix_date(date_obj):
        """Форматирует дату в ISO формат с UTC"""
        if not date_obj:
            return None
            
        # Просто возвращаем дату в ISO формате с UTC
        return date_obj.isoformat() + "Z"

    @staticmethod
    def process_message(message: Message) -> Dict[str, Any]:
        """
        Основной метод трансформации сообщения в структурированный формат.
        
        Args:
            message: Объект сообщения Pyrogram
            
        Returns:
            Dict: Структурированные данные сообщения
        """
        reactions_data = []
        reactions_count = 0
        total_reactions = 0

        if hasattr(message, 'reactions') and message.reactions and hasattr(message.reactions, 'reactions'):
            reactions_count = len(message.reactions.reactions)
            for reaction in message.reactions.reactions:
                total_reactions += reaction.count
                reactions_data.append({"emoji": reaction.emoji, "count": reaction.count})

        # Обработка комментариев
        comments_count = 0
        if hasattr(message, 'replies') and message.replies:
            comments_count = message.replies.replies

        # Обработка текста сообщения
        text_content = ""
        if message.text:
            text_content = message.text
        elif message.caption:
            text_content = message.caption

        # Обработка медиа-данных
        media_info = {}
        content_type = MessageProcessor._determine_content_type(message)
        
        if content_type == "photo" and message.photo:
            media_info = {
                "file_id": message.photo.file_id if hasattr(message.photo, 'file_id') else None,
                "width": message.photo.width if hasattr(message.photo, 'width') else None,
                "height": message.photo.height if hasattr(message.photo, 'height') else None,
                "file_size": message.photo.file_size if hasattr(message.photo, 'file_size') else None
            }
        elif content_type == "video" and message.video:
            media_info = {
                "file_id": message.video.file_id if hasattr(message.video, 'file_id') else None,
                "width": message.video.width if hasattr(message.video, 'width') else None,
                "height": message.video.height if hasattr(message.video, 'height') else None,
                "duration": message.video.duration if hasattr(message.video, 'duration') else None,
                "file_size": message.video.file_size if hasattr(message.video, 'file_size') else None
            }
        elif content_type == "document" and message.document:
            media_info = {
                "file_id": message.document.file_id if hasattr(message.document, 'file_id') else None,
                "file_name": message.document.file_name if hasattr(message.document, 'file_name') else None,
                "mime_type": message.document.mime_type if hasattr(message.document, 'mime_type') else None,
                "file_size": message.document.file_size if hasattr(message.document, 'file_size') else None
            }

        # Формирование итогового словаря
        return {
            "channel_title": message.chat.title if message.chat else None,
            "channel_id": message.chat.id if message.chat else None,
            "message_id": message.id,
            "text": text_content,
            "date": MessageProcessor._fix_date(message.date) if message.date else None,
            "content_type": content_type,
            "views": message.views or 0,
            "forwards": message.forwards or 0,
            "reactions": json.dumps(reactions_data, ensure_ascii=False),
            "reactions_count": reactions_count,
            "total_reactions": total_reactions,
            "comments": json.dumps([], ensure_ascii=False),  # Заглушка из-за высокой стоимости запроса
            "comments_count": comments_count,
            "media_info": json.dumps(media_info, ensure_ascii=False),
            "has_link": 1 if text_content and ("http://" in text_content or "https://" in text_content) else 0,
            "has_mention": 1 if text_content and "@" in text_content else 0,
            "has_hashtag": 1 if text_content and "#" in text_content else 0,
            "message_length": len(text_content) if text_content else 0
        }
    
    @staticmethod
    def process(message: Message) -> Dict[str, Any]:
        """
        Алиас для process_message для обратной совместимости.
        """
        return MessageProcessor.process_message(message)