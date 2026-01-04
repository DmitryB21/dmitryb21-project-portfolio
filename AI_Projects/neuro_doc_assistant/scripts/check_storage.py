#!/usr/bin/env python
"""Проверка подключения к хранилищам"""
import sys
from pathlib import Path
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

# Проверка S3
print("=" * 60)
print("Проверка S3 хранилища (MinIO)")
print("=" * 60)
try:
    from app.storage.s3_storage import S3DocumentStorage
    storage = S3DocumentStorage()
    print(f"✅ S3 подключен: {storage.config.endpoint_url}")
    print(f"   Bucket: {storage.config.bucket_name}")
    docs = storage.list_documents()
    print(f"   Документов в хранилище: {len(docs)}")
except Exception as e:
    print(f"❌ Ошибка S3: {e}")

# Проверка PostgreSQL
print()
print("=" * 60)
print("Проверка PostgreSQL")
print("=" * 60)
try:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL не установлен")
    else:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Проверка существования таблицы
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'documents'
                )
            """))
            table_exists = result.scalar()
            
            if table_exists:
                result = conn.execute(text("SELECT COUNT(*) FROM documents"))
                count = result.scalar()
                print(f"✅ PostgreSQL подключен: {db_url.split('@')[1] if '@' in db_url else db_url}")
                print(f"   Таблица documents существует")
                print(f"   Документов в БД: {count}")
            else:
                print(f"✅ PostgreSQL подключен")
                print(f"   ⚠️  Таблица documents не существует (нужно запустить init_db.sql)")
except Exception as e:
    print(f"❌ Ошибка PostgreSQL: {e}")

print()
print("=" * 60)

