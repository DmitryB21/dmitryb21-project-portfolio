"""
Сервис управления пользователями
Обеспечивает создание, получение и проверку пользователей
"""

import asyncpg
from typing import Optional, Dict, Any
from config_utils import get_config
import logging
import bcrypt

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для работы с пользователями"""
    
    def __init__(self):
        self.config = get_config()
        self.dsn = self.config['postgresql']['dsn']
    
    def _get_password_hash(self, password: str) -> str:
        """Хэширует пароль (bcrypt ограничивает 72 байтами)"""
        # Обрезаем пароль до 72 байт, если он длиннее (ограничение bcrypt)
        password_bytes = password.encode('utf-8')
        password_len = len(password_bytes)
        
        if password_len > 72:
            logger.warning(f"Пароль длиной {password_len} байт обрезается до 72 байт")
            password_bytes = password_bytes[:72]
        
        # Используем bcrypt напрямую
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Проверяет пароль"""
        try:
            password_bytes = plain_password.encode('utf-8')
            # Обрезаем до 72 байт при проверке тоже
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception as e:
            logger.error(f"Ошибка проверки пароля: {e}")
            return False
    
    async def create_user(
        self, 
        username: str, 
        password: str, 
        email: Optional[str] = None,
        role: str = "analyst"
    ) -> Optional[Dict[str, Any]]:
        """
        Создает нового пользователя
        
        Args:
            username: Имя пользователя
            password: Пароль (будет хэширован)
            email: Email (опционально)
            role: Роль пользователя ('admin' или 'analyst')
        
        Returns:
            Словарь с данными пользователя (без пароля) или None при ошибке
        """
        try:
            conn = await asyncpg.connect(dsn=self.dsn)
            
            # Проверяем, не существует ли уже пользователь с таким username
            existing = await conn.fetchval(
                "SELECT id FROM users WHERE username = $1",
                username
            )
            
            if existing:
                logger.warning(f"Пользователь с username '{username}' уже существует")
                await conn.close()
                return None
            
            # Хэшируем пароль
            hashed_password = self._get_password_hash(password)
            
            # Создаем пользователя
            user_id = await conn.fetchval(
                """
                INSERT INTO users (username, email, hashed_password, role, is_active)
                VALUES ($1, $2, $3, $4, TRUE)
                RETURNING id
                """,
                username, email, hashed_password, role
            )
            
            await conn.close()
            
            logger.info(f"Создан пользователь: {username} (id={user_id}, role={role})")
            
            return {
                "id": user_id,
                "username": username,
                "email": email,
                "role": role,
                "is_active": True
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания пользователя {username}: {e}")
            return None
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Получает пользователя по username
        
        Args:
            username: Имя пользователя
        
        Returns:
            Словарь с данными пользователя (включая hashed_password) или None
        """
        try:
            conn = await asyncpg.connect(dsn=self.dsn)
            
            row = await conn.fetchrow(
                """
                SELECT id, username, email, hashed_password, role, is_active, created_at
                FROM users
                WHERE username = $1
                """,
                username
            )
            
            await conn.close()
            
            if not row:
                return None
            
            return {
                "id": row['id'],
                "username": row['username'],
                "email": row['email'],
                "hashed_password": row['hashed_password'],
                "role": row['role'],
                "is_active": row['is_active'],
                "created_at": row['created_at']
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователя {username}: {e}")
            return None
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает пользователя по ID
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Словарь с данными пользователя (без пароля) или None
        """
        try:
            conn = await asyncpg.connect(dsn=self.dsn)
            
            row = await conn.fetchrow(
                """
                SELECT id, username, email, role, is_active, created_at
                FROM users
                WHERE id = $1
                """,
                user_id
            )
            
            await conn.close()
            
            if not row:
                return None
            
            return {
                "id": row['id'],
                "username": row['username'],
                "email": row['email'],
                "role": row['role'],
                "is_active": row['is_active'],
                "created_at": row['created_at']
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователя по ID {user_id}: {e}")
            return None
    
    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Аутентифицирует пользователя по username и password
        
        Args:
            username: Имя пользователя
            password: Пароль
        
        Returns:
            Словарь с данными пользователя (без пароля) или None при ошибке
        """
        user = await self.get_user_by_username(username)
        
        if not user:
            logger.warning(f"Попытка входа с несуществующим username: {username}")
            return None
        
        if not user['is_active']:
            logger.warning(f"Попытка входа неактивного пользователя: {username}")
            return None
        
        if not self.verify_password(password, user['hashed_password']):
            logger.warning(f"Неверный пароль для пользователя: {username}")
            return None
        
        # Возвращаем пользователя без пароля
        return {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "role": user['role'],
            "is_active": user['is_active']
        }
    
    async def user_exists(self, username: str) -> bool:
        """Проверяет, существует ли пользователь"""
        user = await self.get_user_by_username(username)
        return user is not None
    
    async def get_users_count(self) -> int:
        """Возвращает количество пользователей в системе"""
        try:
            conn = await asyncpg.connect(dsn=self.dsn)
            count = await conn.fetchval("SELECT COUNT(*) FROM users")
            await conn.close()
            return count or 0
        except Exception as e:
            logger.error(f"Ошибка получения количества пользователей: {e}")
            return 0
    
    async def get_all_users(self) -> list:
        """
        Получает список всех пользователей (без паролей)
        
        Returns:
            Список словарей с данными пользователей
        """
        try:
            conn = await asyncpg.connect(dsn=self.dsn)
            
            rows = await conn.fetch(
                """
                SELECT id, username, email, role, is_active, created_at
                FROM users
                ORDER BY created_at DESC
                """
            )
            
            await conn.close()
            
            users = []
            for row in rows:
                users.append({
                    "id": row['id'],
                    "username": row['username'],
                    "email": row['email'],
                    "role": row['role'],
                    "is_active": row['is_active'],
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None
                })
            
            return users
            
        except Exception as e:
            logger.error(f"Ошибка получения списка пользователей: {e}")
            return []
    
    async def update_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        email: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        password: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Обновляет данные пользователя
        
        Args:
            user_id: ID пользователя
            username: Новое имя пользователя (опционально)
            email: Новый email (опционально)
            role: Новая роль (опционально)
            is_active: Новый статус активности (опционально)
            password: Новый пароль (опционально, будет хэширован)
        
        Returns:
            Словарь с обновленными данными пользователя или None при ошибке
        """
        try:
            conn = await asyncpg.connect(dsn=self.dsn)
            
            # Проверяем, существует ли пользователь
            existing = await conn.fetchrow(
                "SELECT id, username FROM users WHERE id = $1",
                user_id
            )
            
            if not existing:
                logger.warning(f"Пользователь с ID {user_id} не найден")
                await conn.close()
                return None
            
            # Если обновляется username, проверяем уникальность
            if username and username != existing['username']:
                username_exists = await conn.fetchval(
                    "SELECT id FROM users WHERE username = $1 AND id != $2",
                    username, user_id
                )
                if username_exists:
                    logger.warning(f"Username '{username}' уже занят")
                    await conn.close()
                    return None
            
            # Формируем запрос на обновление
            updates = []
            params = []
            param_index = 1
            
            if username is not None:
                updates.append(f"username = ${param_index}")
                params.append(username)
                param_index += 1
            
            if email is not None:
                updates.append(f"email = ${param_index}")
                params.append(email)
                param_index += 1
            
            if role is not None:
                if role not in ["admin", "analyst"]:
                    logger.error(f"Неверная роль: {role}")
                    await conn.close()
                    return None
                updates.append(f"role = ${param_index}")
                params.append(role)
                param_index += 1
            
            if is_active is not None:
                updates.append(f"is_active = ${param_index}")
                params.append(is_active)
                param_index += 1
            
            if password is not None:
                hashed_password = self._get_password_hash(password)
                updates.append(f"hashed_password = ${param_index}")
                params.append(hashed_password)
                param_index += 1
            
            if not updates:
                # Нет изменений
                await conn.close()
                # Возвращаем текущие данные пользователя
                return await self.get_user_by_id(user_id)
            
            # Выполняем обновление
            params.append(user_id)
            query = f"""
                UPDATE users
                SET {', '.join(updates)}
                WHERE id = ${param_index}
                RETURNING id, username, email, role, is_active, created_at
            """
            
            row = await conn.fetchrow(query, *params)
            await conn.close()
            
            if not row:
                return None
            
            logger.info(f"Пользователь {user_id} обновлен")
            
            return {
                "id": row['id'],
                "username": row['username'],
                "email": row['email'],
                "role": row['role'],
                "is_active": row['is_active'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None
            }
            
        except Exception as e:
            logger.error(f"Ошибка обновления пользователя {user_id}: {e}")
            return None
    
    async def delete_user(self, user_id: int) -> bool:
        """
        Удаляет пользователя
        
        Args:
            user_id: ID пользователя
        
        Returns:
            True если пользователь удален, False при ошибке
        """
        try:
            conn = await asyncpg.connect(dsn=self.dsn)
            
            # Проверяем, существует ли пользователь
            exists = await conn.fetchval(
                "SELECT id FROM users WHERE id = $1",
                user_id
            )
            
            if not exists:
                logger.warning(f"Пользователь с ID {user_id} не найден")
                await conn.close()
                return False
            
            # Удаляем пользователя
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)
            await conn.close()
            
            logger.info(f"Пользователь {user_id} удален")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
            return False


# Глобальный экземпляр сервиса
user_service = UserService()

