# parser_app/telegram_client_manager.py

import logging
from typing import Optional
from pyrogram import Client
import os

logger = logging.getLogger(__name__)

class TelegramClientManager:
   
    def __init__(self, api_id: int, api_hash: str, session_name: str = "telegram_parser"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None
        self._is_running = False
        
        # Проверяем существование основной сессии
        self.main_session_exists = os.path.exists("telegram_parser.session")
        
        if not self.main_session_exists:
            raise Exception("❌ Основная сессия не найдена! Сначала запустите setup_main_session.py")

    async def _create_client_smart(self):
        """Создает клиент БЕЗ повторной авторизации"""
        
        if self.session_name == "telegram_parser":
            # Используем основную сессию напрямую
            logger.info("📱 Использую основную сессию")
            self.client = Client(
                name=self.session_name,
                api_id=self.api_id,
                api_hash=self.api_hash,
                workdir="."
            )
        else:
            # Создаем новую сессию на основе основной (БЕЗ ПОВТОРНОЙ АВТОРИЗАЦИИ!)
            logger.info(f"🔄 Создаю производную сессию: {self.session_name}")
            
            # МЕТОД 1: Session String (рекомендуемый)
            await self._create_from_session_string()
            
            # МЕТОД 2: Копирование файла (альтернативный)
            # await self._create_from_file_copy()

    async def _create_from_session_string(self):
        """Создание новой сессии через session_string (БЕЗОПАСНО)"""
        try:
            # Экспортируем session string из основной сессии
            main_client = Client("telegram_parser", api_id=self.api_id, api_hash=self.api_hash)
            await main_client.start()
            
            # Получаем строку сессии
            session_string = await main_client.export_session_string()
            logger.info("📤 Session string получен из основной сессии")
            
            await main_client.stop()
            
            # Создаем новый клиент из строки сессии
            self.client = Client(
                name=self.session_name,
                api_id=self.api_id,
                api_hash=self.api_hash,
                session_string=session_string,  # Ключевой параметр!
                workdir="."
            )
            
            logger.info(f"✅ Новая сессия создана из строки: {self.session_name}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания из session_string: {e}")
            # Fallback к копированию файла
            await self._create_from_file_copy()

    async def _create_from_file_copy(self):
        """Создание через копирование файла (БЕЗОПАСНЫЙ fallback)"""
        try:
            # Копируем файл сессии, если новой сессии нет
            session_file = f"{self.session_name}.session"
            main_session_file = "telegram_parser.session"
            
            if not os.path.exists(session_file) and os.path.exists(main_session_file):
                import shutil
                shutil.copy2(main_session_file, session_file)
                logger.info(f"📋 Скопирован файл сессии: {session_file}")
                
                # Копируем также journal файл, если есть
                journal_file = f"{main_session_file}-journal"
                if os.path.exists(journal_file):
                    shutil.copy2(journal_file, f"{session_file}-journal")
            
            # Создаем клиент
            self.client = Client(
                name=self.session_name,
                api_id=self.api_id,
                api_hash=self.api_hash,
                workdir="."
            )
            
            logger.info(f"✅ Сессия создана из копии файла: {self.session_name}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка копирования файла сессии: {e}")
            raise

    async def get_client(self):
        """Получение клиента с автоматическим созданием"""
        if self.client is None or not self._is_running:
            await self._create_client_smart()
            
            # Запускаем клиент (БЕЗ АВТОРИЗАЦИИ - уже авторизован!)
            await self.client.start()
            
            me = await self.client.get_me()
            logger.info(f"✅ Клиент запущен: {me.first_name} (сессия: {self.session_name})")
            self._is_running = True
            
        return self.client

    async def stop(self):
        """Остановка с очисткой временных сессий"""
        if self.client and self._is_running:
            await self.client.stop()
            self._is_running = False
            
            # Удаляем временные файлы (НЕ основную сессию!)
            if self.session_name != "telegram_parser" and self.session_name.startswith("telegram_parser_"):
                session_file = f"{self.session_name}.session"
                if os.path.exists(session_file):
                    os.remove(session_file)
                    logger.info(f"🗑️ Удален временный файл: {session_file}")
    
    async def get_client_info(self) -> dict:
        """
        Получает подробную информацию о клиенте для диагностики.
        """
        if not self.client or not self._is_running:
            return {
                'status': 'not_connected',
                'error': 'Клиент не подключен'
            }
        
        try:
            me = await self.client.get_me()
            
            # Получаем количество диалогов для диагностики
            dialogs_count = await self.client.get_dialogs_count()
            
            return {
                'status': 'connected',
                'user_id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'phone_number': me.phone_number,
                'is_verified': me.is_verified,
                'is_bot': me.is_bot,
                'is_premium': getattr(me, 'is_premium', False),
                'dialogs_count': dialogs_count,
                'session_name': self.session_name
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def test_connection(self) -> bool:
        """
        Тестирует подключение к Telegram.
        """
        try:
            client = await self.get_client()
            me = await client.get_me()
            logger.info(f"🔍 Тест подключения успешен. Пользователь: {me.first_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Тест подключения не пройден: {e}")
            return False