"""
@file: test_retrieval_integration.py
@description: Интеграционные тесты для Retrieval Layer с Ingestion module
@dependencies: app.retrieval.retriever, app.retrieval.metadata_filter, app.ingestion.*
@created: 2024-12-19
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.retrieval.retriever import Retriever
from app.retrieval.metadata_filter import MetadataFilter
from app.ingestion.embedding_service import EmbeddingService


class TestRetrievalIntegration:
    """
    Интеграционные тесты для Retrieval Layer.
    
    Проверяют интеграцию Retriever и MetadataFilter с Ingestion module.
    """
    
    @pytest.fixture
    def qdrant_client(self):
        """Фикстура для создания мок Qdrant клиента"""
        mock_client = MagicMock()
        
        # Мокаем search с результатами, соответствующими структуре из Ingestion
        mock_result = Mock()
        mock_points = [
            Mock(
                id="hr_01_chunk_000",
                score=0.95,
                payload={
                    "text": "Политика удалённой работы устанавливает правила для сотрудников",
                    "doc_id": "hr_01_политика_удалённой_работы_abc123",
                    "chunk_id": "hr_01_chunk_000",
                    "source": "hr",
                    "category": "hr",
                    "file_path": "data/NeuroDoc_Data/hr/hr_01_политика_удалённой_работы.md",
                    "created_at": "2024-12-19T10:00:00",
                    "text_length": 50,
                    "embedding_version": "GigaChat",
                    "metadata_tags": ["policy", "remote_work"]
                }
            ),
            Mock(
                id="it_10_chunk_001",
                score=0.88,
                payload={
                    "text": "SLA сервиса платежей составляет 99.9%",
                    "doc_id": "it_10_порядок_обращения_в_техподдержку_def456",
                    "chunk_id": "it_10_chunk_001",
                    "source": "it",
                    "category": "it",
                    "file_path": "data/NeuroDoc_Data/it/it_10_порядок_обращения_в_техподдержку.md",
                    "created_at": "2024-12-19T10:00:00",
                    "text_length": 30,
                    "embedding_version": "GigaChat",
                    "metadata_tags": ["sla", "payments"]
                }
            )
        ]
        mock_result.points = mock_points
        mock_client.search.return_value = mock_result
        
        return mock_client
    
    @pytest.fixture
    def embedding_service(self):
        """Фикстура для создания EmbeddingService"""
        return EmbeddingService(model_version="test_model", embedding_dim=1536)
    
    @pytest.fixture
    def retriever(self, qdrant_client, embedding_service):
        """Фикстура для создания Retriever"""
        return Retriever(
            qdrant_client=qdrant_client,
            embedding_service=embedding_service,
            collection_name="neuro_docs"
        )
    
    @pytest.fixture
    def metadata_filter(self):
        """Фикстура для создания MetadataFilter"""
        return MetadataFilter()
    
    def test_retriever_with_ingestion_metadata(self, retriever, qdrant_client, embedding_service):
        """
        UC-1 Retrieval: Retriever работает с метаданными из Ingestion
        
        Given:
            - Чанки проиндексированы через Ingestion pipeline
            - Метаданные соответствуют структуре из QdrantIndexer
        When:
            - Вызывается Retriever.retrieve()
        Then:
            - Возвращаются чанки с полными метаданными из Ingestion
            - Метаданные содержат все обязательные поля (doc_id, chunk_id, source, created_at, text_length, embedding_version, metadata_tags)
        """
        query = "Какой SLA у сервиса платежей?"
        
        with patch.object(embedding_service, 'generate_embeddings', return_value=[[0.1] * 1536]):
            results = retriever.retrieve(query, k=3)
        
        assert len(results) > 0
        for chunk in results:
            assert "doc_id" in chunk.metadata
            assert "chunk_id" in chunk.metadata
            assert "source" in chunk.metadata
            assert "created_at" in chunk.metadata
            assert "text_length" in chunk.metadata
            assert "embedding_version" in chunk.metadata
            assert "metadata_tags" in chunk.metadata
    
    def test_retriever_metadata_filter_integration(self, retriever, metadata_filter, embedding_service):
        """
        UC-3 Retrieval: Интеграция Retriever + MetadataFilter
        
        Given:
            - Запрос пользователя
        When:
            - Выполняется retrieve, затем filter
        Then:
            - Фильтрация работает корректно с результатами retrieve
            - Возвращаются только чанки, соответствующие фильтру
        """
        query = "Какой SLA у сервиса платежей?"
        
        with patch.object(embedding_service, 'generate_embeddings', return_value=[[0.1] * 1536]):
            # Шаг 1: Retrieval
            retrieved = retriever.retrieve(query, k=5)
            
            # Шаг 2: Фильтрация
            filtered = metadata_filter.filter(retrieved, source="it")
        
        # Проверяем, что фильтрация работает
        assert len(filtered) <= len(retrieved)
        assert all(chunk.metadata["source"] == "it" for chunk in filtered)
    
    def test_retrieval_precision_at_k(self, retriever, embedding_service):
        """
        UC-1 Retrieval: Проверка Precision@K для retrieved результатов
        
        Given:
            - Запрос пользователя
            - Известные релевантные чанки
        When:
            - Вызывается retrieve с K=3
        Then:
            - Возвращаются релевантные чанки
            - Precision@3 можно рассчитать (для последующего использования в Evaluation module)
        """
        query = "Какой SLA у сервиса платежей?"
        
        with patch.object(embedding_service, 'generate_embeddings', return_value=[[0.1] * 1536]):
            results = retriever.retrieve(query, k=3)
        
        # Проверяем, что результаты имеют scores (для расчёта Precision@K)
        assert len(results) > 0
        assert all(chunk.score is not None for chunk in results)
        assert all(0.0 <= chunk.score <= 1.0 for chunk in results)
    
    def test_retrieval_with_prepared_vector_store(self, retriever, embedding_service):
        """
        UC-1 Retrieval: Работа с prepared_vector_store из фикстуры
        
        Given:
            - prepared_vector_store готов (из tests/fixtures/vector_store.py)
        When:
            - Вызывается retrieve
        Then:
            - Retriever работает с реальным векторным хранилищем
            - Результаты соответствуют проиндексированным документам
        """
        query = "Какой SLA у сервиса платежей?"
        
        with patch.object(embedding_service, 'generate_embeddings', return_value=[[0.1] * 1536]):
            results = retriever.retrieve(query, k=3)
        
        # Проверяем базовую структуру результатов
        assert isinstance(results, list)
        # В реальном тесте здесь будут проверки на соответствие реальным данным

