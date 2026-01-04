#!/usr/bin/env python
"""
Скрипт для миграции документов из локальной файловой системы в S3-хранилище
и сохранения метаданных в PostgreSQL.

Использование:
    python scripts/migrate_to_s3.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

from app.storage.s3_storage import S3DocumentStorage, S3Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime


def migrate_documents():
    """
    Мигрирует все документы из data/NeuroDoc_Data/ в S3 и сохраняет метаданные в PostgreSQL.
    """
    print("=" * 80)
    print("Миграция документов в S3-хранилище")
    print("=" * 80)
    print()
    
    # Проверка конфигурации
    s3_endpoint = os.getenv("S3_ENDPOINT")
    s3_access_key = os.getenv("S3_ACCESS_KEY")
    s3_secret_key = os.getenv("S3_SECRET_KEY")
    s3_bucket = os.getenv("S3_BUCKET")
    database_url = os.getenv("DATABASE_URL")
    
    if not all([s3_endpoint, s3_access_key, s3_secret_key, s3_bucket]):
        print("❌ Ошибка: Не настроены переменные окружения для S3")
        print("   Требуются: S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET")
        return 1
    
    if not database_url:
        # Попробуем собрать DATABASE_URL из отдельных переменных
        postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        postgres_port = os.getenv("POSTGRES_PORT", "5432")
        postgres_db = os.getenv("POSTGRES_DB", "neuro_doc_assistant")
        postgres_user = os.getenv("POSTGRES_USER", "neuro_doc_user")
        postgres_password = os.getenv("POSTGRES_PASSWORD", "neuro_doc_password")
        database_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
    
    # Исправляем 127.0.0.1 на localhost для лучшей совместимости
    if "127.0.0.1" in database_url:
        database_url = database_url.replace("127.0.0.1", "localhost")
    
    # Инициализация хранилищ
    print("🔧 Инициализация хранилищ...")
    try:
        s3_config = S3Config(
            endpoint_url=s3_endpoint,
            access_key=s3_access_key,
            secret_key=s3_secret_key,
            bucket_name=s3_bucket
        )
        s3_storage = S3DocumentStorage(config=s3_config)
        print(f"✅ S3 хранилище инициализировано: {s3_endpoint}")
    except Exception as e:
        print(f"❌ Ошибка инициализации S3: {e}")
        return 1
    
    session = None
    try:
        # Используем localhost вместо 127.0.0.1 для лучшей совместимости
        if "127.0.0.1" in database_url:
            database_url = database_url.replace("127.0.0.1", "localhost")
        
        engine = create_engine(database_url)
        # Тестируем подключение
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        Session = sessionmaker(bind=engine)
        session = Session()
        print(f"✅ PostgreSQL подключен")
    except Exception as e:
        print(f"⚠️  Предупреждение: не удалось подключиться к PostgreSQL: {e}")
        print(f"   Миграция будет продолжена только для S3 (метаданные не будут сохранены)")
        print(f"   DATABASE_URL: {database_url.split('@')[1] if '@' in database_url else database_url}")
        session = None
    
    # Поиск документов
    data_dir = project_root / "data" / "NeuroDoc_Data"
    if not data_dir.exists():
        print(f"❌ Директория с данными не найдена: {data_dir}")
        return 1
    
    print()
    print("📁 Поиск документов...")
    documents_to_migrate = []
    
    for category_dir in data_dir.iterdir():
        if not category_dir.is_dir():
            continue
        
        category = category_dir.name
        print(f"   Категория: {category}")
        
        # Поддерживаемые форматы
        for ext in ['.md', '.txt', '.pdf', '.docx']:
            for doc_file in category_dir.glob(f"*{ext}"):
                documents_to_migrate.append((category, doc_file))
    
    if not documents_to_migrate:
        print("❌ Документы не найдены")
        return 1
    
    print(f"✅ Найдено документов для миграции: {len(documents_to_migrate)}")
    print()
    
    # Миграция
    print("📤 Начало миграции...")
    migrated = 0
    errors = 0
    
    for category, doc_file in documents_to_migrate:
        try:
            # Формируем S3 ключ
            s3_key = f"{category}/{doc_file.name}"
            
            # Проверяем, не загружен ли уже
            if s3_storage.document_exists(s3_key):
                print(f"   ⏭️  Пропущен (уже существует): {s3_key}")
                continue
            
            # Загружаем в S3
            s3_uri = s3_storage.upload_document(doc_file, s3_key)
            print(f"   ✅ Загружен: {s3_key}")
            
            # Сохраняем метаданные в PostgreSQL (если подключение доступно)
            if session:
                try:
                    file_size = doc_file.stat().st_size
                    mime_type = _get_mime_type(doc_file.suffix)
                    
                    session.execute(
                        text("""
                            INSERT INTO documents (file_path, s3_key, category, filename, file_size, mime_type, created_at)
                            VALUES (:file_path, :s3_key, :category, :filename, :file_size, :mime_type, :created_at)
                            ON CONFLICT (s3_key) DO NOTHING
                        """),
                        {
                            "file_path": str(doc_file),
                            "s3_key": s3_key,
                            "category": category,
                            "filename": doc_file.name,
                            "file_size": file_size,
                            "mime_type": mime_type,
                            "created_at": datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
                        }
                    )
                    session.commit()
                except Exception as db_error:
                    print(f"   ⚠️  Предупреждение: не удалось сохранить метаданные в БД: {db_error}")
                    session.rollback()
            
            migrated += 1
            
        except Exception as e:
            print(f"   ❌ Ошибка при миграции {doc_file.name}: {e}")
            errors += 1
            session.rollback()
    
    if session:
        session.close()
    
    print()
    print("=" * 80)
    print("📊 Результаты миграции:")
    print(f"   ✅ Успешно мигрировано: {migrated}")
    print(f"   ❌ Ошибок: {errors}")
    print("=" * 80)
    
    return 0 if errors == 0 else 1


def _get_mime_type(extension: str) -> str:
    """Определяет MIME тип по расширению файла"""
    mime_types = {
        '.md': 'text/markdown',
        '.txt': 'text/plain',
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    return mime_types.get(extension.lower(), 'application/octet-stream')


if __name__ == "__main__":
    exit_code = migrate_documents()
    sys.exit(exit_code)

