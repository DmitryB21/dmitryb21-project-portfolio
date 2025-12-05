#!/usr/bin/env python3
"""
Миграция: Добавление поля collection_name в таблицу embeddings
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import os

# Добавляем путь к проекту для импорта config_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_utils import get_config

def add_collection_name_to_embeddings():
    """Добавить поле collection_name в таблицу embeddings"""
    config = get_config()
    if 'postgresql' not in config or 'dsn' not in config['postgresql']:
        print("Ошибка: В файле config.ini отсутствует секция [postgresql] или параметр dsn.")
        sys.exit(1)
    dsn = config['postgresql']['dsn']
    
    try:
        conn = psycopg2.connect(dsn)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Проверяем, существует ли поле collection_name
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'embeddings' AND column_name = 'collection_name'
        """)
        
        if cur.fetchone():
            print("Поле 'collection_name' уже существует в таблице 'embeddings'.")
            # Проверяем, существует ли новый constraint
            cur.execute("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'embeddings' 
                AND constraint_name = 'embeddings_message_id_model_collection_key'
            """)
            if not cur.fetchone():
                print("Обновляем constraint для включения 'collection_name'...")
                # Удаляем старый constraint, если он существует
                cur.execute("""
                    ALTER TABLE embeddings 
                    DROP CONSTRAINT IF EXISTS embeddings_message_id_model_key;
                """)
                # Создаем новый constraint с collection_name
                cur.execute("""
                    ALTER TABLE embeddings 
                    ADD CONSTRAINT embeddings_message_id_model_collection_key 
                    UNIQUE (message_id, model, collection_name);
                """)
                print("✅ Уникальный constraint обновлен для включения 'collection_name'.")
            else:
                print("Constraint с 'collection_name' уже существует.")
        else:
            # Добавляем поле collection_name
            cur.execute("""
                ALTER TABLE embeddings 
                ADD COLUMN collection_name VARCHAR(100);
            """)
            print("✅ Поле 'collection_name' добавлено в таблицу 'embeddings'.")
            
            # Обновляем уникальный constraint, чтобы включить collection_name
            # Сначала удаляем старый constraint, если он существует
            cur.execute("""
                ALTER TABLE embeddings 
                DROP CONSTRAINT IF EXISTS embeddings_message_id_model_key;
            """)
            
            # Удаляем старый индекс, если он существует
            cur.execute("""
                DROP INDEX IF EXISTS embeddings_message_id_model_key;
            """)
            
            # Создаем новый уникальный constraint с collection_name
            cur.execute("""
                ALTER TABLE embeddings 
                ADD CONSTRAINT embeddings_message_id_model_collection_key 
                UNIQUE (message_id, model, collection_name);
            """)
            print("✅ Уникальный constraint обновлен для включения 'collection_name'.")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при добавлении поля collection_name: {e}")
        raise

if __name__ == "__main__":
    add_collection_name_to_embeddings()

