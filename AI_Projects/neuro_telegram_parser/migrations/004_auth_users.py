"""
Миграция 004: Создание таблицы users для системы аутентификации
Добавляет таблицу пользователей с поддержкой ролей и хэшированных паролей
"""

import psycopg2
import os
import sys

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_utils import get_config

def create_users_table():
    """Создание таблицы users для аутентификации"""
    config = get_config()
    
    if 'postgresql' not in config or 'dsn' not in config['postgresql']:
        print("Ошибка: В файле config.ini отсутствует секция [postgresql] или параметр dsn.")
        sys.exit(1)
    
    POSTGRES_DSN = config['postgresql']['dsn']
    
    try:
        display_dsn = POSTGRES_DSN.split('@')[1] if '@' in POSTGRES_DSN else POSTGRES_DSN
        print(f"Подключение к PostgreSQL: {display_dsn}")
        conn = psycopg2.connect(dsn=POSTGRES_DSN)
        cur = conn.cursor()
        print("Успешное подключение к PostgreSQL.")

        # Таблица пользователей
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE,
            hashed_password TEXT NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'analyst',  -- 'admin', 'analyst'
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)
        print("Таблица 'users' создана или уже существует.")

        # Создание индексов для производительности
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email) WHERE email IS NOT NULL;",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);",
            "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users (is_active);"
        ]

        for index_sql in indexes:
            cur.execute(index_sql)
        
        print("Индексы для таблицы users созданы или уже существуют.")
        
        conn.commit()

    except Exception as e:
        print(f"Ошибка при создании таблицы users: {e}")
        raise
    finally:
        if 'conn' in locals() and conn is not None:
            conn.close()
            print("Соединение с PostgreSQL закрыто.")

if __name__ == "__main__":
    create_users_table()

