# setup_main_session.py

import asyncio
import os
import sys
from dotenv import load_dotenv
from pyrogram import Client


# Добавляем путь к проекту
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Загружаем переменные окружения
load_dotenv()

# Импортируем функцию для получения конфигурации
from telegram_parser.config_utils import get_config


async def main():
    config = get_config()
    API_ID = int(config['telegram']['api_id'])
    API_HASH = config['telegram']['api_hash']
    
    PHONE_NUMBER = config['telegram'].get('phone_number', '')
    app = Client("telegram_parser", api_id=API_ID, api_hash=API_HASH,  phone_number=PHONE_NUMBER)
    
    # Это запросит номер телефона и код ОДИН РАЗ
    await app.start()
    
    me = await app.get_me()
    print(f"✅ Авторизован: {me.first_name}")
    
    await app.stop()
    print("📁 Основная сессия telegram_parser.session создана!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())