"""
Зависимости Flask для защиты роутов
Обеспечивает проверку JWT токенов и ролей пользователей
"""

from flask import request, jsonify
from functools import wraps
from typing import Optional, Callable
import asyncio
from auth.jwt import decode_access_token
from auth.user_service import user_service
import logging

logger = logging.getLogger(__name__)


def get_current_user_sync() -> Optional[dict]:
    """
    Синхронная функция для получения текущего пользователя из JWT токена
    Используется в Flask декораторах
    
    Returns:
        Словарь с данными пользователя или None
    """
    try:
        # Получаем токен из заголовка Authorization
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return None
        
        # Проверяем формат "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        token = parts[1]
        
        # Декодируем токен
        payload = decode_access_token(token)
        if not payload:
            return None
        
        # Получаем user_id из токена
        user_id_str = payload.get("sub")  # стандартное поле JWT для subject (user_id)
        if not user_id_str:
            return None
        
        # Преобразуем строку в int
        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            logger.warning(f"Невалидный user_id в токене: {user_id_str}")
            return None
        
        # Получаем пользователя из БД (синхронно через asyncio.run)
        user = asyncio.run(user_service.get_user_by_id(user_id))
        
        if not user or not user.get("is_active"):
            return None
        
        return user
        
    except Exception as e:
        logger.error(f"Ошибка получения текущего пользователя: {e}")
        return None


def require_auth(f: Callable) -> Callable:
    """
    Декоратор для защиты роута - требует аутентификации
    
    Usage:
        @app.route('/api/protected')
        @require_auth
        def protected_route():
            user = get_current_user_sync()
            return jsonify({"user": user})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user_sync()
        
        if not user:
            return jsonify({
                "error": "Требуется аутентификация",
                "message": "Необходимо предоставить валидный JWT токен"
            }), 401
        
        # Добавляем user в kwargs для использования в функции
        kwargs['current_user'] = user
        return f(*args, **kwargs)
    
    return decorated_function


def require_role(required_role: str) -> Callable:
    """
    Возвращает декоратор для проверки роли пользователя
    
    Args:
        required_role: Требуемая роль ('admin' или 'analyst')
    
    Usage:
        @app.route('/api/admin/clusters')
        @require_role('admin')
        def admin_route(current_user):
            return jsonify({"message": "Admin only"})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user_sync()
            
            if not user:
                return jsonify({
                    "error": "Требуется аутентификация",
                    "message": "Необходимо предоставить валидный JWT токен"
                }), 401
            
            user_role = user.get("role")
            if user_role != required_role:
                return jsonify({
                    "error": "Доступ запрещен",
                    "message": f"Требуется роль '{required_role}', у вас роль '{user_role}'"
                }), 403
            
            # Добавляем user в kwargs
            kwargs['current_user'] = user
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def get_current_user() -> Optional[dict]:
    """
    Удобная функция для получения текущего пользователя
    Можно использовать внутри защищенных роутов
    
    Returns:
        Словарь с данными пользователя или None
    """
    return get_current_user_sync()

