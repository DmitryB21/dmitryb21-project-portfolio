"""
Скрипт инициализации первого администратора
Создает дефолтного админа, если таблица users пуста
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth.user_service import user_service
import logging

logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")


async def init_default_admin():
    """
    Инициализирует дефолтного администратора, если таблица users пуста
    Идемпотентно - не создаст дубликат при повторных запусках
    """
    try:
        # Проверяем, есть ли уже пользователи
        users_count = await user_service.get_users_count()
        
        if users_count > 0:
            logger.info(f"В системе уже есть {users_count} пользователь(ей). Пропускаем создание дефолтного админа.")
            return
        
        # Проверяем, не существует ли уже пользователь с таким username
        existing_user = await user_service.get_user_by_username(DEFAULT_ADMIN_USERNAME)
        
        if existing_user:
            logger.info(f"Пользователь '{DEFAULT_ADMIN_USERNAME}' уже существует. Пропускаем создание.")
            return
        
        # Создаем дефолтного администратора
        # Проверяем длину пароля в байтах
        pwd_bytes = DEFAULT_ADMIN_PASSWORD.encode('utf-8')
        logger.info(f"Длина пароля в байтах: {len(pwd_bytes)}")
        
        admin = await user_service.create_user(
            username=DEFAULT_ADMIN_USERNAME,
            password=DEFAULT_ADMIN_PASSWORD,
            email=DEFAULT_ADMIN_EMAIL,
            role="admin"
        )
        
        if admin:
            logger.info(f"✅ Создан дефолтный администратор:")
            logger.info(f"   Username: {DEFAULT_ADMIN_USERNAME}")
            logger.info(f"   Password: {DEFAULT_ADMIN_PASSWORD}")
            logger.info(f"   Email: {DEFAULT_ADMIN_EMAIL}")
            logger.info(f"   Role: admin")
            logger.warning(f"⚠️  ВАЖНО: Измените пароль после первого входа!")
        else:
            logger.error("❌ Не удалось создать дефолтного администратора")
            
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации администратора: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(init_default_admin())

