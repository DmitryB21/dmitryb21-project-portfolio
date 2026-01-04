#!/usr/bin/env python
"""
Синхронизация метаданных из S3 в PostgreSQL.
Использует прямое подключение через docker exec для обхода проблем с аутентификацией.
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

from app.storage.s3_storage import S3DocumentStorage


def sync_metadata():
    """Синхронизирует метаданные из S3 в PostgreSQL через docker exec"""
    print("=" * 80)
    print("Синхронизация метаданных в PostgreSQL")
    print("=" * 80)
    print()
    
    # Инициализация S3
    storage = S3DocumentStorage()
    all_docs = storage.list_documents()
    
    print(f"📁 Найдено документов в S3: {len(all_docs)}")
    print()
    
    # Группируем по категориям
    documents_by_category = {}
    for s3_key in all_docs:
        parts = s3_key.split('/')
        if len(parts) >= 2:
            category = parts[0]
            filename = parts[-1]
            if category not in documents_by_category:
                documents_by_category[category] = []
            documents_by_category[category].append((s3_key, filename))
    
    # Подготовка SQL команд
    sql_commands = []
    for category, docs in documents_by_category.items():
        for s3_key, filename in docs:
            # Экранируем специальные символы для SQL
            s3_key_escaped = s3_key.replace("'", "''")
            filename_escaped = filename.replace("'", "''")
            
            sql = f"""
            INSERT INTO documents (file_path, s3_key, category, filename, created_at)
            VALUES ('{s3_key_escaped}', '{s3_key_escaped}', '{category}', '{filename_escaped}', NOW())
            ON CONFLICT (s3_key) DO NOTHING;
            """
            sql_commands.append(sql)
    
    # Выполняем через docker exec
    print("💾 Сохранение метаданных в PostgreSQL...")
    
    # Объединяем все SQL команды
    full_sql = "\n".join(sql_commands)
    
    # Сохраняем во временный файл
    temp_sql_file = project_root / "temp_sync.sql"
    temp_sql_file.write_text(full_sql, encoding='utf-8')
    
    try:
        # Копируем файл в контейнер и выполняем
        subprocess.run(
            ["docker", "cp", str(temp_sql_file), "neuro_doc_postgres:/tmp/sync.sql"],
            check=True,
            capture_output=True
        )
        
        result = subprocess.run(
            [
                "docker", "exec", "neuro_doc_postgres",
                "psql", "-U", "neuro_doc_user", "-d", "neuro_doc_assistant",
                "-f", "/tmp/sync.sql"
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Метаданные успешно синхронизированы")
        else:
            print(f"⚠️  Предупреждение: {result.stderr}")
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при синхронизации: {e}")
        return 1
    finally:
        # Удаляем временный файл
        if temp_sql_file.exists():
            temp_sql_file.unlink()
    
    # Проверяем результат
    result = subprocess.run(
        [
            "docker", "exec", "neuro_doc_postgres",
            "psql", "-U", "neuro_doc_user", "-d", "neuro_doc_assistant",
            "-t", "-c", "SELECT COUNT(*) FROM documents;"
        ],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        count = result.stdout.strip()
        print(f"📊 Документов в PostgreSQL: {count}")
    
    print()
    print("=" * 80)
    return 0


if __name__ == "__main__":
    exit_code = sync_metadata()
    sys.exit(exit_code)

