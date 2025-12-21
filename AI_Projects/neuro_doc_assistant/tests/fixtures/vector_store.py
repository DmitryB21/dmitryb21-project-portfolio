"""
@file: vector_store.py
@description: Фикстуры для подготовки векторного хранилища для тестов UC-1
@dependencies: app.ingestion.*, qdrant_client
@created: 2024-12-19
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from app.ingestion.loader import DocumentLoader
from app.ingestion.chunker import Chunker
from app.ingestion.embedding_service import EmbeddingService
from app.ingestion.indexer import QdrantIndexer


@pytest.fixture(scope="session")
def qdrant_test_client():
    """
    Фикстура для создания тестового Qdrant клиента.
    
    В реальной реализации это может быть:
    - Тестовый инстанс Qdrant (docker контейнер)
    - Мок клиента для unit-тестов
    - Отдельная тестовая коллекция в production Qdrant
    """
    # Для unit-тестов используем мок
    # Для integration тестов нужен реальный Qdrant инстанс
    from unittest.mock import MagicMock
    
    mock_client = MagicMock()
    
    # Настраиваем мок для get_collections
    mock_collections = MagicMock()
    mock_collections.collections = []
    mock_client.get_collections.return_value = mock_collections
    
    # Настраиваем мок для create_collection
    mock_client.create_collection.return_value = True
    
    # Настраиваем мок для upsert
    mock_client.upsert.return_value = True
    
    # Настраиваем мок для search - будет обновляться в prepared_vector_store
    # с реальными данными после индексации
    mock_search_result = MagicMock()
    mock_search_result.points = []
    mock_client.search.return_value = mock_search_result
    
    return mock_client


@pytest.fixture(scope="session")
def prepared_vector_store(qdrant_test_client):
    """
    Фикстура для подготовки векторного хранилища для тестов UC-1.
    
    Эта фикстура использует реальный Ingestion pipeline для подготовки данных:
    1. Загружает документы из data/NeuroDoc_Data/hr/ и data/NeuroDoc_Data/it/
    2. Разбивает на чанки
    3. Генерирует embeddings
    4. Индексирует в Qdrant
    
    После выполнения фикстуры векторное хранилище готово для использования
    в тестах UC-1 (test_uc1_basic_search.py).
    
    Scope: session - выполняется один раз для всех тестов в сессии
    """
    # Проверяем наличие директорий с данными
    hr_path = Path("data/NeuroDoc_Data/hr")
    it_path = Path("data/NeuroDoc_Data/it")
    
    if not hr_path.exists() or not it_path.exists():
        pytest.skip("Data directories not found")
    
    # Создаём компоненты pipeline
    loader = DocumentLoader()
    chunker = Chunker()
    embedding_service = EmbeddingService(model_version="test_model", embedding_dim=1536)
    indexer = QdrantIndexer(qdrant_client=qdrant_test_client, collection_name="neuro_docs")
    
    # Загружаем документы
    hr_documents = loader.load_documents(str(hr_path))
    it_documents = loader.load_documents(str(it_path))
    all_documents = hr_documents + it_documents
    
    assert len(all_documents) > 0, "No documents loaded"
    
    # Разбиваем на чанки
    all_chunks = []
    for doc in all_documents:
        chunks = chunker.chunk_documents([doc], chunk_size=300, overlap_percent=0.25)
        all_chunks.extend(chunks)
    
    assert len(all_chunks) > 0, "No chunks created"
    
    # Генерируем embeddings
    # В реальной реализации здесь будут настоящие API вызовы к GigaChat Embeddings
    # Для тестов можно использовать моки или реальные вызовы (зависит от конфигурации)
    chunk_texts = [chunk.text for chunk in all_chunks]
    
    # Мокаем embeddings для тестов (в production будут реальные)
    mock_embeddings = [[0.1] * 1536 for _ in all_chunks]
    
    with patch.object(embedding_service, 'generate_embeddings', return_value=mock_embeddings):
        embeddings = embedding_service.generate_embeddings(chunk_texts)
    
    assert len(embeddings) == len(all_chunks), "Embeddings count mismatch"
    
    # Индексируем в Qdrant
    indexer.index_chunks(all_chunks, embeddings)
    
    # Настраиваем мок search для возврата реальных чанков при поиске
    # Создаём моковые точки из реальных чанков для поиска
    def mock_search(collection_name, query_vector, limit=3, **kwargs):
        """Моковая функция search, которая возвращает чанки на основе query"""
        from unittest.mock import MagicMock
        
        # Для простоты возвращаем первые limit чанков
        # В реальной реализации здесь был бы semantic search
        mock_points = []
        for i, chunk in enumerate(all_chunks[:limit]):
            mock_point = MagicMock()
            mock_point.id = chunk.chunk_id
            mock_point.score = 0.95 - i * 0.1  # Симулируем score
            mock_point.payload = {
                "text": chunk.text,
                "doc_id": chunk.doc_id,
                "chunk_id": chunk.chunk_id,
                "source": chunk.metadata.get("source", "unknown"),
                "category": chunk.metadata.get("category", "unknown"),
                "file_path": chunk.metadata.get("file_path", ""),
                "metadata_tags": chunk.metadata.get("metadata_tags", []),
                "created_at": "2024-12-19T00:00:00",
                "text_length": chunk.text_length,
                "embedding_version": "test_model"
            }
            mock_points.append(mock_point)
        
        mock_result = MagicMock()
        mock_result.points = mock_points
        return mock_result
    
    qdrant_test_client.search = mock_search
    
    # Возвращаем клиент Qdrant для использования в тестах
    return qdrant_test_client


@pytest.fixture(scope="function")
def mock_vector_store():
    """
    Мок векторного хранилища для unit-тестов.
    
    Используется когда не нужен полный ingestion pipeline,
    а достаточно мокированных данных для тестирования других компонентов.
    """
    mock_client = Mock()
    mock_client.search.return_value = Mock(
        points=[
            Mock(
                id="chunk_001",
                score=0.95,
                payload={
                    "text": "SLA сервиса платежей составляет 99.9%",
                    "doc_id": "doc_001",
                    "chunk_id": "chunk_001",
                    "source": "it",
                    "metadata_tags": ["sla", "payments"]
                }
            ),
            Mock(
                id="chunk_002",
                score=0.88,
                payload={
                    "text": "Время отклика сервиса платежей не более 200мс",
                    "doc_id": "doc_001",
                    "chunk_id": "chunk_002",
                    "source": "it",
                    "metadata_tags": ["sla", "payments"]
                }
            ),
            Mock(
                id="chunk_003",
                score=0.82,
                payload={
                    "text": "Документация по SLA сервисов находится в разделе IT",
                    "doc_id": "doc_002",
                    "chunk_id": "chunk_003",
                    "source": "it",
                    "metadata_tags": ["sla"]
                }
            )
        ]
    )
    return mock_client

