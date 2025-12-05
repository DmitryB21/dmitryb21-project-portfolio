"""
Скрипт для создания нового пользователя через командную строку
Использование: python scripts/create_user.py --username <username> --password <password> [--email <email>] [--role <role>]
"""

import asyncio
import os
import sys
import argparse
from dotenv import load_dotenv
import logging

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth.user_service import user_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


async def create_user_cli(username: str, password: str, email: str = None, role: str = "analyst"):
    """
    Создает нового пользователя через командную строку
    
    Args:
        username: Имя пользователя
        password: Пароль
        email: Email (опционально)
        role: Роль пользователя ('admin' или 'analyst'), по умолчанию 'analyst'
    """
    try:
        # Валидация
        if not username or len(username) < 3:
            logger.error("❌ Username должен быть не менее 3 символов")
            return False
        
        if not password or len(password) < 6:
            logger.error("❌ Пароль должен быть не менее 6 символов")
            return False
        
        if role not in ["admin", "analyst"]:
            logger.error("❌ Роль должна быть 'admin' или 'analyst'")
            return False
        
        # Проверяем, не существует ли уже пользователь
        existing_user = await user_service.get_user_by_username(username)
        if existing_user:
            logger.error(f"❌ Пользователь с username '{username}' уже существует")
            return False
        
        # Создаем пользователя
        user = await user_service.create_user(
            username=username,
            password=password,
            email=email,
            role=role
        )
        
        if user:
            logger.info(f"✅ Пользователь успешно создан:")
            logger.info(f"   ID: {user['id']}")
            logger.info(f"   Username: {user['username']}")
            logger.info(f"   Email: {user.get('email', 'не указан')}")
            logger.info(f"   Role: {user['role']}")
            logger.info(f"   Active: {user['is_active']}")
            return True
        else:
            logger.error("❌ Не удалось создать пользователя")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка создания пользователя: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Создать нового пользователя в системе аутентификации',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python scripts/create_user.py --username analyst1 --password secure123
  python scripts/create_user.py --username admin2 --password admin456 --role admin
  python scripts/create_user.py --username user1 --password pass123 --email user@example.com --role analyst
        """
    )
    
    parser.add_argument(
        '--username', '-u',
        required=True,
        help='Имя пользователя (минимум 3 символа)'
    )
    
    parser.add_argument(
        '--password', '-p',
        required=True,
        help='Пароль (минимум 6 символов)'
    )
    
    parser.add_argument(
        '--email', '-e',
        default=None,
        help='Email пользователя (опционально)'
    )
    
    parser.add_argument(
        '--role', '-r',
        default='analyst',
        choices=['admin', 'analyst'],
        help='Роль пользователя: admin или analyst (по умолчанию: analyst)'
    )
    
    args = parser.parse_args()
    
    # Запускаем создание пользователя
    success = asyncio.run(create_user_cli(
        username=args.username,
        password=args.password,
        email=args.email,
        role=args.role
    ))
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

