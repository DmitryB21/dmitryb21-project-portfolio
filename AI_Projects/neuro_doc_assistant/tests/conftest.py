"""
@file: conftest.py
@description: Общие фикстуры для всех тестов проекта
@dependencies: pytest
@created: 2024-12-19
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from app.agent.agent import AgentController
from app.retrieval.retriever import Retriever
from app.retrieval.metadata_filter import MetadataFilter
from app.generation.prompt_builder import PromptBuilder
from app.generation.gigachat_client import LLMClient
from app.evaluation.metrics import MetricsCollector
from app.evaluation.ragas_evaluator import RAGASEvaluator
from app.ingestion.embedding_service import EmbeddingService
from app.ingestion.loader import DocumentLoader
from app.ingestion.chunker import Chunker
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


@pytest.fixture(scope="session")
def agent_client(prepared_vector_store):
    """
    Фикстура для создания клиента агента через AgentController.
    
    Использует реальный AgentController со всеми модулями:
    - Retriever (с prepared_vector_store)
    - MetadataFilter
    - PromptBuilder
    - LLMClient (в мок-режиме для тестов)
    - MetricsCollector
    - RAGASEvaluator (в мок-режиме для тестов)
    
    Контракт API:
    - agent_client.ask(query: str, ground_truth_relevant: List[str] = None) -> AgentResponse
      где AgentResponse содержит:
      - answer: str
      - sources: list[Source]
      - metrics: dict[str, float]
    """
    # Создаём компоненты для AgentController
    qdrant_client = prepared_vector_store
    embedding_service = EmbeddingService(model_version="test_model", embedding_dim=1536)
    # Мокаем generate_embeddings для тестов
    embedding_service.generate_embeddings = lambda texts: [[0.1] * 1536 for _ in texts]
    
    retriever = Retriever(
        qdrant_client=qdrant_client,
        embedding_service=embedding_service,
        collection_name="neuro_docs"
    )
    metadata_filter = MetadataFilter()
    prompt_builder = PromptBuilder()
    llm_client = LLMClient(mock_mode=True)
    metrics_collector = MetricsCollector()
    ragas_evaluator = RAGASEvaluator(mock_mode=True)
    
    # Создаём AgentController
    agent_controller = AgentController(
        retriever=retriever,
        metadata_filter=metadata_filter,
        prompt_builder=prompt_builder,
        llm_client=llm_client,
        metrics_collector=metrics_collector,
        ragas_evaluator=ragas_evaluator
    )
    
    return agent_controller
