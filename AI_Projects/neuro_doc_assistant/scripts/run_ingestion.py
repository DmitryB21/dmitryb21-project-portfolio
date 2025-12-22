#!/usr/bin/env python
"""
Скрипт для запуска Ingestion Pipeline - загрузка и индексация документов в Qdrant
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from app.ingestion.loader import DocumentLoader
from app.ingestion.chunker import Chunker
from app.ingestion.embedding_service import EmbeddingService
from app.ingestion.indexer import QdrantIndexer

# Загружаем переменные окружения
load_dotenv()


def main():
    """
    Запуск полного Ingestion Pipeline:
    1. Загрузка документов из data/NeuroDoc_Data/
    2. Чанкинг документов
    3. Генерация embeddings
    4. Индексация в Qdrant (создание коллекции neuro_docs, если не существует)
    """
    print("=" * 80)
    print("Neuro_Doc_Assistant - Ingestion Pipeline")
    print("=" * 80)
    print()
    
    # Проверка наличия данных
    data_dir = project_root / "data" / "NeuroDoc_Data"
    if not data_dir.exists():
        print(f"❌ Ошибка: Директория с данными не найдена: {data_dir}")
        print("   Создайте директорию data/NeuroDoc_Data/ и поместите туда документы.")
        return 1
    
    hr_dir = data_dir / "hr"
    it_dir = data_dir / "it"
    
    if not hr_dir.exists() and not it_dir.exists():
        print(f"❌ Ошибка: Не найдены директории hr/ или it/ в {data_dir}")
        return 1
    
    # Инициализация Qdrant клиента
    print("[Шаг 1/5] Подключение к Qdrant...")
    qdrant_url = os.getenv("QDRANT_URL")
    if not qdrant_url:
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
    
    try:
        qdrant_client = QdrantClient(url=qdrant_url)
        # Проверяем подключение
        collections = qdrant_client.get_collections()
        print(f"✅ Подключение к Qdrant успешно: {qdrant_url}")
    except Exception as e:
        print(f"❌ Ошибка подключения к Qdrant: {e}")
        print()
        print("Убедитесь, что Qdrant запущен:")
        print("  Docker: docker run -p 6333:6333 qdrant/qdrant")
        print("  Или установите Qdrant локально")
        return 1
    
    # Инициализация компонентов
    print()
    print("[Шаг 2/5] Инициализация компонентов...")
    loader = DocumentLoader()
    chunker = Chunker()
    
    embedding_dim = int(os.getenv("EMBEDDING_DIM", "1536"))
    gigachat_auth_key = os.getenv("GIGACHAT_AUTH_KEY")
    gigachat_scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    
    # Определяем, использовать ли mock mode
    # Если auth_key не предоставлен или mock mode включен, используем mock mode
    use_mock_mode = not gigachat_auth_key or os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true"
    
    if use_mock_mode:
        print(f"   ⚠️  Используется mock mode для EmbeddingService (GIGACHAT_AUTH_KEY не предоставлен или mock mode включен)")
    else:
        print(f"   ✅ Используется OAuth 2.0 аутентификация для GigaChat API (scope: {gigachat_scope})")
    
    embedding_service = EmbeddingService(
        model_version=os.getenv("EMBEDDING_MODEL_VERSION", "GigaChat"),
        embedding_dim=embedding_dim,
        auth_key=gigachat_auth_key,
        scope=gigachat_scope,
        mock_mode=use_mock_mode
    )
    
    collection_name = os.getenv("QDRANT_COLLECTION", "neuro_docs")
    indexer = QdrantIndexer(
        qdrant_client=qdrant_client,
        collection_name=collection_name,
        embedding_dim=embedding_dim
    )
    print(f"✅ Компоненты инициализированы (collection: {collection_name}, embedding_dim: {embedding_dim})")
    
    # Загрузка документов
    print()
    print("[Шаг 3/5] Загрузка документов...")
    all_documents = []
    
    if hr_dir.exists():
        print(f"   Загрузка HR документов из {hr_dir}...")
        hr_documents = loader.load_documents(str(hr_dir))
        all_documents.extend(hr_documents)
        print(f"   ✅ Загружено HR документов: {len(hr_documents)}")
    
    if it_dir.exists():
        print(f"   Загрузка IT документов из {it_dir}...")
        it_documents = loader.load_documents(str(it_dir))
        all_documents.extend(it_documents)
        print(f"   ✅ Загружено IT документов: {len(it_documents)}")
    
    if not all_documents:
        print("❌ Ошибка: Не найдено документов для загрузки")
        return 1
    
    print(f"✅ Всего загружено документов: {len(all_documents)}")
    
    # Чанкинг
    print()
    print("[Шаг 4/5] Разбиение документов на чанки...")
    chunk_size = int(os.getenv("CHUNK_SIZE", "300"))
    overlap_percent = float(os.getenv("CHUNK_OVERLAP_PERCENT", "0.25"))
    
    all_chunks = []
    for doc in all_documents:
        chunks = chunker.chunk_documents(
            [doc],
            chunk_size=chunk_size,
            overlap_percent=overlap_percent
        )
        all_chunks.extend(chunks)
    
    print(f"✅ Создано чанков: {len(all_chunks)} (chunk_size={chunk_size}, overlap={overlap_percent*100}%)")
    
    # Генерация embeddings
    print()
    print("[Шаг 5/5] Генерация embeddings и индексация в Qdrant...")
    print("   Это может занять некоторое время...")
    
    chunk_texts = [chunk.text for chunk in all_chunks]
    
    # Генерируем embeddings батчами для оптимизации
    batch_size = 10
    all_embeddings = []
    
    for i in range(0, len(chunk_texts), batch_size):
        batch = chunk_texts[i:i + batch_size]
        batch_embeddings = embedding_service.generate_embeddings(batch)
        all_embeddings.extend(batch_embeddings)
        print(f"   Обработано {min(i + batch_size, len(chunk_texts))}/{len(chunk_texts)} чанков...")
    
    print(f"✅ Сгенерировано embeddings: {len(all_embeddings)}")
    
    # Индексация в Qdrant
    print()
    print(f"   Индексация в Qdrant (коллекция: {collection_name})...")
    print("   Коллекция будет создана автоматически, если не существует.")
    
    try:
        indexer.index_chunks(all_chunks, all_embeddings)
        print(f"✅ Индексация завершена успешно!")
    except Exception as e:
        print(f"❌ Ошибка при индексации: {e}")
        return 1
    
    # Проверка результата
    print()
    print("=" * 80)
    print("✅ INGESTION PIPELINE ЗАВЕРШЕН УСПЕШНО")
    print("=" * 80)
    print()
    print(f"📊 Статистика:")
    print(f"   - Загружено документов: {len(all_documents)}")
    print(f"   - Создано чанков: {len(all_chunks)}")
    print(f"   - Индексировано в Qdrant: {len(all_embeddings)}")
    print(f"   - Коллекция: {collection_name}")
    print()
    print("Теперь можно запускать FastAPI сервер и Streamlit UI!")
    print()
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

