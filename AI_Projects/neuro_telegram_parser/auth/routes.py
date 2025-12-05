"""
Flask роуты для аутентификации
"""

from flask import Blueprint, request, jsonify, session, redirect
import asyncio
from auth.user_service import user_service
from auth.jwt import create_access_token
from auth.dependencies import require_auth, get_current_user
import logging

logger = logging.getLogger(__name__)

# Создаем Blueprint для аутентификации
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Эндпоинт для входа пользователя
    
    Request body:
        {
            "username": "admin",
            "password": "password123"
        }
    
    Returns:
        {
            "access_token": "eyJ...",
            "token_type": "bearer",
            "role": "admin",
            "username": "admin"
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "error": "Неверный запрос",
                "message": "Требуется JSON с username и password"
            }), 400
        
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            return jsonify({
                "error": "Неверный запрос",
                "message": "Требуются поля username и password"
            }), 400
        
        # Аутентифицируем пользователя
        user = asyncio.run(user_service.authenticate_user(username, password))
        
        if not user:
            return jsonify({
                "error": "Неверные учетные данные",
                "message": "Неверный username или password"
            }), 401
        
        # Создаем JWT токен
        token_data = {
            "sub": str(user["id"]),  # subject - ID пользователя (должен быть строкой)
            "username": user["username"],
            "role": user["role"]
        }
        
        access_token = create_access_token(data=token_data)
        
        # Сохраняем информацию о пользователе в Flask session
        session['user_id'] = user["id"]
        session['username'] = user["username"]
        session['role'] = user["role"]
        session['authenticated'] = True
        
        logger.info(f"Успешный вход пользователя: {username} (role={user['role']})")
        
        return jsonify({
            "access_token": access_token,
            "token_type": "bearer",
            "role": user["role"],
            "username": user["username"]
        }), 200
        
    except Exception as e:
        logger.error(f"Ошибка входа: {e}")
        return jsonify({
            "error": "Внутренняя ошибка сервера",
            "message": str(e)
        }), 500


@auth_bp.route('/logout', methods=['POST', 'GET'])
def logout():
    """Выход из системы"""
    session.clear()
    return jsonify({
        "message": "Вы успешно вышли из системы"
    }), 200


@auth_bp.route('/me', methods=['GET'])
def get_current_user_info():
    """
    Получить информацию о текущем пользователе
    
    Headers:
        Authorization: Bearer <token> (опционально, если есть session)
    
    Returns:
        {
            "id": 1,
            "username": "admin",
            "email": "admin@example.com",
            "role": "admin",
            "is_active": true
        }
    """
    try:
        # Сначала проверяем session
        if session.get('authenticated'):
            # Получаем полную информацию о пользователе из БД
            user_id = session.get('user_id')
            if user_id:
                user = asyncio.run(user_service.get_user_by_id(user_id))
                if user:
                    return jsonify({
                        "id": user["id"],
                        "username": user["username"],
                        "email": user.get("email"),
                        "role": user["role"],
                        "is_active": user["is_active"]
                    }), 200
        
        # Если нет session, проверяем JWT токен
        from auth.dependencies import get_current_user_sync
        user = get_current_user_sync()
        if user:
            return jsonify({
                "id": user["id"],
                "username": user["username"],
                "email": user.get("email"),
                "role": user["role"],
                "is_active": user["is_active"]
            }), 200
        
        return jsonify({
            "error": "Требуется аутентификация",
            "message": "Необходимо войти в систему"
        }), 401
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о пользователе: {e}")
        return jsonify({
            "error": "Внутренняя ошибка сервера",
            "message": str(e)
        }), 500


@auth_bp.route('/verify', methods=['POST'])
def verify_token():
    """
    Проверить валидность токена (опциональный эндпоинт)
    
    Request body:
        {
            "token": "eyJ..."
        }
    
    Returns:
        {
            "valid": true,
            "user": {...}
        }
    """
    try:
        data = request.get_json()
        
        if not data or "token" not in data:
            return jsonify({
                "error": "Неверный запрос",
                "message": "Требуется поле token"
            }), 400
        
        token = data["token"]
        
        # Используем существующую логику проверки
        from auth.dependencies import get_current_user_sync
        
        # Временно устанавливаем токен в заголовок для проверки
        original_auth = request.headers.get("Authorization")
        request.headers["Authorization"] = f"Bearer {token}"
        
        try:
            user = get_current_user_sync()
            
            if user:
                return jsonify({
                    "valid": True,
                    "user": {
                        "id": user["id"],
                        "username": user["username"],
                        "role": user["role"]
                    }
                }), 200
            else:
                return jsonify({
                    "valid": False,
                    "message": "Токен невалиден или истек"
                }), 401
        finally:
            # Восстанавливаем оригинальный заголовок
            if original_auth:
                request.headers["Authorization"] = original_auth
            elif "Authorization" in request.headers:
                del request.headers["Authorization"]
        
    except Exception as e:
        logger.error(f"Ошибка проверки токена: {e}")
        return jsonify({
            "error": "Внутренняя ошибка сервера",
            "message": str(e)
        }), 500


@auth_bp.route('/users', methods=['POST'])
@require_auth
def create_user(current_user):
    """
    Создать нового пользователя (только для администраторов)
    
    Headers:
        Authorization: Bearer <token>
    
    Request body:
        {
            "username": "newuser",
            "password": "secure_password",
            "email": "user@example.com",  # опционально
            "role": "analyst"  # опционально, по умолчанию "analyst"
        }
    
    Returns:
        {
            "status": "ok",
            "user": {
                "id": 2,
                "username": "newuser",
                "email": "user@example.com",
                "role": "analyst",
                "is_active": true
            }
        }
    """
    try:
        # Проверяем, что текущий пользователь - администратор
        if current_user.get("role") != "admin":
            return jsonify({
                "error": "Доступ запрещен",
                "message": "Только администраторы могут создавать пользователей"
            }), 403
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                "error": "Неверный запрос",
                "message": "Требуется JSON с username и password"
            }), 400
        
        username = data.get("username")
        password = data.get("password")
        email = data.get("email")
        role = data.get("role", "analyst")  # По умолчанию "analyst"
        
        if not username or not password:
            return jsonify({
                "error": "Неверный запрос",
                "message": "Требуются поля username и password"
            }), 400
        
        # Валидация роли
        if role not in ["admin", "analyst"]:
            return jsonify({
                "error": "Неверный запрос",
                "message": "Роль должна быть 'admin' или 'analyst'"
            }), 400
        
        # Валидация username
        if len(username) < 3 or len(username) > 50:
            return jsonify({
                "error": "Неверный запрос",
                "message": "Username должен быть от 3 до 50 символов"
            }), 400
        
        # Валидация password
        if len(password) < 6:
            return jsonify({
                "error": "Неверный запрос",
                "message": "Пароль должен быть не менее 6 символов"
            }), 400
        
        # Создаем пользователя
        user = asyncio.run(user_service.create_user(
            username=username,
            password=password,
            email=email,
            role=role
        ))
        
        if not user:
            return jsonify({
                "error": "Ошибка создания пользователя",
                "message": "Пользователь с таким username уже существует"
            }), 409
        
        logger.info(f"Администратор {current_user['username']} создал пользователя: {username} (role={role})")
        
        return jsonify({
            "status": "ok",
            "message": f"Пользователь '{username}' успешно создан",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user.get("email"),
                "role": user["role"],
                "is_active": user["is_active"]
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Ошибка создания пользователя: {e}")
        return jsonify({
            "error": "Внутренняя ошибка сервера",
            "message": str(e)
        }), 500


@auth_bp.route('/users', methods=['GET'])
@require_auth
def list_users(current_user):
    """
    Получить список всех пользователей (только для администраторов)
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        {
            "status": "ok",
            "users": [
                {
                    "id": 1,
                    "username": "admin",
                    "email": "admin@example.com",
                    "role": "admin",
                    "is_active": true,
                    "created_at": "2024-01-01T00:00:00"
                },
                ...
            ]
        }
    """
    try:
        # Проверяем, что текущий пользователь - администратор
        if current_user.get("role") != "admin":
            return jsonify({
                "error": "Доступ запрещен",
                "message": "Только администраторы могут просматривать список пользователей"
            }), 403
        
        # Получаем список пользователей
        users = asyncio.run(user_service.get_all_users())
        
        return jsonify({
            "status": "ok",
            "users": users
        }), 200
        
    except Exception as e:
        logger.error(f"Ошибка получения списка пользователей: {e}")
        return jsonify({
            "error": "Внутренняя ошибка сервера",
            "message": str(e)
        }), 500


@auth_bp.route('/users/<int:user_id>', methods=['PUT', 'PATCH'])
@require_auth
def update_user(current_user, user_id):
    """
    Обновить данные пользователя (только для администраторов)
    
    Headers:
        Authorization: Bearer <token>
    
    Request body (все поля опциональны):
        {
            "username": "newusername",
            "email": "newemail@example.com",
            "role": "analyst",
            "is_active": true,
            "password": "newpassword"
        }
    
    Returns:
        {
            "status": "ok",
            "message": "Пользователь обновлен",
            "user": {...}
        }
    """
    try:
        # Проверяем, что текущий пользователь - администратор
        if current_user.get("role") != "admin":
            return jsonify({
                "error": "Доступ запрещен",
                "message": "Только администраторы могут обновлять пользователей"
            }), 403
        
        data = request.get_json() or {}
        
        # Валидация
        if "role" in data and data["role"] not in ["admin", "analyst"]:
            return jsonify({
                "error": "Неверный запрос",
                "message": "Роль должна быть 'admin' или 'analyst'"
            }), 400
        
        if "username" in data and (len(data["username"]) < 3 or len(data["username"]) > 50):
            return jsonify({
                "error": "Неверный запрос",
                "message": "Username должен быть от 3 до 50 символов"
            }), 400
        
        if "password" in data and len(data["password"]) < 6:
            return jsonify({
                "error": "Неверный запрос",
                "message": "Пароль должен быть не менее 6 символов"
            }), 400
        
        # Обновляем пользователя
        user = asyncio.run(user_service.update_user(
            user_id=user_id,
            username=data.get("username"),
            email=data.get("email"),
            role=data.get("role"),
            is_active=data.get("is_active"),
            password=data.get("password")
        ))
        
        if not user:
            return jsonify({
                "error": "Ошибка обновления",
                "message": "Пользователь не найден или username уже занят"
            }), 404
        
        logger.info(f"Администратор {current_user['username']} обновил пользователя: {user_id}")
        
        return jsonify({
            "status": "ok",
            "message": "Пользователь успешно обновлен",
            "user": user
        }), 200
        
    except Exception as e:
        logger.error(f"Ошибка обновления пользователя: {e}")
        return jsonify({
            "error": "Внутренняя ошибка сервера",
            "message": str(e)
        }), 500


@auth_bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_auth
def delete_user(current_user, user_id):
    """
    Удалить пользователя (только для администраторов)
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        {
            "status": "ok",
            "message": "Пользователь удален"
        }
    """
    try:
        # Проверяем, что текущий пользователь - администратор
        if current_user.get("role") != "admin":
            return jsonify({
                "error": "Доступ запрещен",
                "message": "Только администраторы могут удалять пользователей"
            }), 403
        
        # Нельзя удалить самого себя
        if current_user.get("id") == user_id:
            return jsonify({
                "error": "Ошибка удаления",
                "message": "Нельзя удалить самого себя"
            }), 400
        
        # Удаляем пользователя
        success = asyncio.run(user_service.delete_user(user_id))
        
        if not success:
            return jsonify({
                "error": "Ошибка удаления",
                "message": "Пользователь не найден"
            }), 404
        
        logger.info(f"Администратор {current_user['username']} удалил пользователя: {user_id}")
        
        return jsonify({
            "status": "ok",
            "message": "Пользователь успешно удален"
        }), 200
        
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя: {e}")
        return jsonify({
            "error": "Внутренняя ошибка сервера",
            "message": str(e)
        }), 500
