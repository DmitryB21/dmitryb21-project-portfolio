"""
JWT-утилиты для создания и проверки токенов доступа
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Получаем секретный ключ из переменных окружения
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Создает JWT токен доступа
    
    Args:
        data: Данные для включения в токен (обычно user_id, username, role)
        expires_delta: Время жизни токена (по умолчанию из ACCESS_TOKEN_EXPIRE_MINUTES)
    
    Returns:
        Закодированный JWT токен
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"Ошибка создания JWT токена: {e}")
        raise


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Декодирует и проверяет JWT токен
    
    Args:
        token: JWT токен для декодирования
    
    Returns:
        Словарь с данными из токена или None при ошибке
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT токен истек")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Невалидный JWT токен: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка декодирования JWT токена: {e}")
        return None


def get_token_expiration_time() -> datetime:
    """Возвращает время истечения токена по умолчанию"""
    return datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

