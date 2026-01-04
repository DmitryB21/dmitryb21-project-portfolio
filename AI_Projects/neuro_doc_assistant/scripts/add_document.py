#!/usr/bin/env python
"""
Скрипт для добавления одного нового документа в систему.

Использование:
    python scripts/add_document.py <path_to_file> [--category CATEGORY] [--update]
    
Примеры:
    python scripts/add_document.py data/new_doc.md --category hr
    python scripts/add_document.py data/updated_doc.md --category it --update
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

from app.storage.s3_storage import S3DocumentStorage
from app.storage.document_repository import DocumentRepository, DocumentMetadata
from app.ingestion.loader import DocumentLoader
from app.ingestion.chunker import Chunker
from app.ingestion.embedding_service import EmbeddingService
from app.ingestion.indexer import QdrantIndexer
from qdrant_client import QdrantClient


def get_mime_type(file_path: Path) -> str:
    """Определяет MIME тип по расширению файла"""
    mime_types = {
        '.md': 'text/markdown',
        '.txt': 'text/plain',
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    return mime_types.get(file_path.suffix.lower(), 'application/octet-stream')


def determine_category(file_path: Path, provided_category: Optional[str] = None) -> str:
    """Определяет категорию документа"""
    if provided_category:
        return provided_category.lower()
    
    path_str = str(file_path).lower()
    if '/hr/' in path_str or '\\hr\\' in path_str:
        return "hr"
    elif '/it/' in path_str or '\\it\\' in path_str:
        return "it"
    elif '/compliance/' in path_str or '\\compliance\\' in path_str:
        return "compliance"
    elif '/onboarding/' in path_str or '\\onboarding\\' in path_str:
        return "onboarding"
    
    return "unknown"


def delete_old_chunks(qdrant_client: QdrantClient, collection_name: str, doc_id: str) -> int:
    """Удаляет старые чанки документа из Qdrant"""
    try:
        # Получаем все точки с данным doc_id
        points, _ = qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter={
                "must": [{"key": "doc_id", "match": {"value": doc_id}}]
            },
            limit=10000
        )
        
        if not points:
            return 0
        
        # Удаляем точки
        point_ids = [point.id for point in points]
        qdrant_client.delete(
            collection_name=collection_name,
            points_selector=point_ids
        )
        
        return len(point_ids)
    except Exception as e:
        print(f"   ⚠️  Предупреждение: не удалось удалить старые чанки: {e}")
        return 0


def add_document(
    file_path: Path,
    category: Optional[str] = None,
    update: bool = False
) -> int:
    """
    Добавляет документ в систему.
    
    Args:
        file_path: Путь к файлу
        category: Категория документа (hr, it, compliance, onboarding)
        update: Если True, обновляет существующий документ
    
    Returns:
        0 при успехе, 1 при ошибке
    """
    print("=" * 80)
    print("Добавление документа в систему")
    print("=" * 80)
    print()
    
    if not file_path.exists():
        print(f"❌ Ошибка: Файл не найден: {file_path}")
        return 1
    
    # Определяем категорию
    category = determine_category(file_path, category)
    if category == "unknown":
        print("⚠️  Предупреждение: категория не определена, используется 'unknown'")
        print("   Используйте --category для указания категории")
    
    # Инициализация компонентов
    print("🔧 Инициализация компонентов...")
    
    try:
        s3_storage = S3DocumentStorage()
        print("   ✅ S3 хранилище")
    except Exception as e:
        print(f"   ❌ Ошибка S3: {e}")
        return 1
    
    try:
        doc_repository = DocumentRepository()
        print("   ✅ PostgreSQL")
    except Exception as e:
        print(f"   ⚠️  Предупреждение: PostgreSQL недоступен: {e}")
        doc_repository = None
    
    try:
        qdrant_client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333"))
        )
        print("   ✅ Qdrant")
    except Exception as e:
        print(f"   ❌ Ошибка Qdrant: {e}")
        return 1
    
    loader = DocumentLoader(storage_backend="auto")
    chunker = Chunker()
    
    # Embedding service
    initial_embedding_dim = int(os.getenv("EMBEDDING_DIM", "1024"))
    gigachat_auth_key = os.getenv("GIGACHAT_AUTH_KEY")
    gigachat_scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    use_mock_mode = not gigachat_auth_key or os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true"
    
    embedding_service = EmbeddingService(
        model_version=os.getenv("EMBEDDING_MODEL_VERSION", "GigaChat"),
        embedding_dim=initial_embedding_dim,
        auth_key=gigachat_auth_key,
        scope=gigachat_scope,
        mock_mode=use_mock_mode
    )
    
    collection_name = os.getenv("QDRANT_COLLECTION", "neuro_docs")
    indexer = QdrantIndexer(
        qdrant_client=qdrant_client,
        collection_name=collection_name,
        embedding_dim=initial_embedding_dim
    )
    
    print()
    
    # Этап 1: Загрузка в S3
    print("[1/7] Загрузка в S3...")
    s3_key = f"{category}/{file_path.name}"
    
    # Проверяем существование документа
    existing_doc = None
    if doc_repository:
        existing_doc = doc_repository.get_document_by_s3_key(s3_key)
    
    if existing_doc and not update:
        print(f"   ⚠️  Документ уже существует: {s3_key}")
        print("   Используйте --update для обновления документа")
        return 1
    
    if existing_doc and update:
        print(f"   🔄 Обновление существующего документа: {s3_key}")
        # Удаляем старые чанки из Qdrant
        deleted_count = delete_old_chunks(qdrant_client, collection_name, existing_doc.id)
        if deleted_count > 0:
            print(f"   ✅ Удалено старых чанков из Qdrant: {deleted_count}")
    else:
        print(f"   📤 Загрузка нового документа: {s3_key}")
    
    try:
        s3_uri = s3_storage.upload_document(file_path, s3_key)
        print(f"   ✅ Загружено в S3: {s3_uri}")
    except Exception as e:
        print(f"   ❌ Ошибка загрузки в S3: {e}")
        return 1
    
    # Этап 2: Сохранение метаданных в PostgreSQL
    if doc_repository:
        print()
        print("[2/7] Сохранение метаданных в PostgreSQL...")
        try:
            file_size = file_path.stat().st_size
            mime_type = get_mime_type(file_path)
            
            doc_metadata = DocumentMetadata(
                file_path=str(file_path),
                s3_key=s3_key,
                category=category,
                filename=file_path.name,
                file_size=file_size,
                mime_type=mime_type,
                version=(existing_doc.version + 1) if existing_doc and update else 1
            )
            
            doc_id = doc_repository.save_document(doc_metadata)
            print(f"   ✅ Метаданные сохранены (ID: {doc_id})")
        except Exception as e:
            print(f"   ⚠️  Предупреждение: не удалось сохранить метаданные: {e}")
    
    # Этап 3: Загрузка и парсинг
    print()
    print("[3/7] Загрузка и парсинг документа...")
    try:
        documents = loader.load_documents(s3_key, category=category)
        if not documents:
            print("   ❌ Не удалось загрузить документ")
            return 1
        doc = documents[0]
        print(f"   ✅ Документ загружен: {len(doc.text)} символов")
    except Exception as e:
        print(f"   ❌ Ошибка загрузки: {e}")
        return 1
    
    # Этап 4: Чанкинг
    print()
    print("[4/7] Разбиение на чанки...")
    chunk_size = int(os.getenv("CHUNK_SIZE", "300"))
    overlap_percent = float(os.getenv("CHUNK_OVERLAP_PERCENT", "0.25"))
    
    chunks = chunker.chunk_documents(
        [doc],
        chunk_size=chunk_size,
        overlap_percent=overlap_percent
    )
    print(f"   ✅ Создано чанков: {len(chunks)}")
    
    # Этап 5: Генерация embeddings
    print()
    print("[5/7] Генерация embeddings...")
    actual_mode = "Mock Embeddings" if embedding_service.mock_mode else "GigaChat Embeddings API"
    print(f"   Режим: {actual_mode}")
    
    chunk_texts = [chunk.text for chunk in chunks]
    
    try:
        embeddings = embedding_service.generate_embeddings(chunk_texts)
        final_embedding_dim = embedding_service.embedding_dim
        print(f"   ✅ Сгенерировано embeddings: {len(embeddings)} (размерность: {final_embedding_dim})")
    except Exception as e:
        print(f"   ❌ Ошибка генерации embeddings: {e}")
        return 1
    
    # Этап 6: Индексация в Qdrant
    print()
    print("[6/7] Индексация в Qdrant...")
    try:
        indexer.index_chunks(chunks, embeddings)
        print(f"   ✅ Индексировано в Qdrant: {len(chunks)} чанков")
    except Exception as e:
        print(f"   ❌ Ошибка индексации: {e}")
        return 1
    
    # Этап 7: Обновление метаданных
    if doc_repository:
        print()
        print("[7/7] Обновление метаданных...")
        try:
            doc_repository.mark_as_indexed(s3_key, actual_mode, final_embedding_dim)
            print(f"   ✅ Метаданные обновлены (indexed_at установлен)")
        except Exception as e:
            print(f"   ⚠️  Предупреждение: не удалось обновить метаданные: {e}")
    
    print()
    print("=" * 80)
    print("✅ ДОКУМЕНТ УСПЕШНО ДОБАВЛЕН")
    print("=" * 80)
    print()
    print(f"📊 Статистика:")
    print(f"   - Файл: {file_path.name}")
    print(f"   - S3 ключ: {s3_key}")
    print(f"   - Категория: {category}")
    print(f"   - Чанков: {len(chunks)}")
    print(f"   - Embeddings: {len(embeddings)} (размерность: {final_embedding_dim})")
    print(f"   - Режим embeddings: {actual_mode}")
    print()
    
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Добавление документа в систему Neuro_Doc_Assistant"
    )
    parser.add_argument(
        "file_path",
        type=Path,
        help="Путь к файлу для добавления"
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=["hr", "it", "compliance", "onboarding"],
        help="Категория документа"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Обновить существующий документ (удалить старые чанки)"
    )
    
    args = parser.parse_args()
    
    exit_code = add_document(
        file_path=args.file_path,
        category=args.category,
        update=args.update
    )
    
    sys.exit(exit_code)

