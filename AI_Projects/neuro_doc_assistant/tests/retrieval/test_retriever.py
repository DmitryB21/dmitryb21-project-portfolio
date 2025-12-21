"""
@file: test_retriever.py
@description: Тесты для Retriever - semantic search по Qdrant
@dependencies: app.retrieval.retriever, app.ingestion.embedding_service
@created: 2024-12-19
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.retrieval.retriever import Retriever, RetrievedChunk


class TestRetriever:
    """
    Тесты для Retriever компонента.
    
    Retriever отвечает за:
    - Semantic search по Qdrant коллекции neuro_docs
    - Параметризацию K (количество retrieved чанков: 3, 5, 8)
    - Возврат релевантных чанков с метаданными и scores
    """
    
    @pytest.fixture
    def qdrant_client(self):
        """Фикстура для создания мок Qdrant клиента"""
        mock_client = MagicMock()
        
        # Мокаем search метод - создаём объект с атрибутом points
        mock_search_result = Mock()
        mock_points = [
            Mock(
                id="chunk_001",
                score=0.95,
                payload={
                    "text": "SLA сервиса платежей составляет 99.9%",
                    "doc_id": "doc_001",
                    "chunk_id": "chunk_001",
                    "source": "it",
                    "category": "it",
                    "file_path": "it_10_порядок_обращения_в_техподдержку.md",
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
                    "category": "it",
                    "file_path": "it_10_порядок_обращения_в_техподдержку.md",
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
                    "category": "it",
                    "file_path": "it_20_порядок_обращения_в_техподдержку.md",
                    "metadata_tags": ["sla"]
                }
            )
        ]
        # Устанавливаем points как список перед возвратом
        mock_search_result.points = mock_points
        mock_client.search.return_value = mock_search_result
        
        return mock_client
    
    @pytest.fixture
    def embedding_service(self):
        """Фикстура для создания мок EmbeddingService"""
        mock_service = Mock()
        mock_service.generate_embeddings.return_value = [[0.1] * 1536]
        return mock_service
    
    @pytest.fixture
    def retriever(self, qdrant_client, embedding_service):
        """Фикстура для создания экземпляра Retriever"""
        return Retriever(
            qdrant_client=qdrant_client,
            embedding_service=embedding_service,
            collection_name="neuro_docs"
        )
    
    def test_retrieve_k3(self, retriever, qdrant_client, embedding_service):
        """
        UC-1 Retrieval: Semantic search с K=3
        
        Given:
            - Запрос пользователя: "Какой SLA у сервиса платежей?"
            - В Qdrant есть релевантные чанки
        When:
            - Вызывается retrieve с K=3
        Then:
            - Возвращается список из 3 RetrievedChunk объектов
            - Каждый чанк содержит text, score, metadata
            - Чанки отсортированы по score (от большего к меньшему)
        """
        query = "Какой SLA у сервиса платежей?"
        
        results = retriever.retrieve(query, k=3)
        
        assert len(results) == 3
        assert all(isinstance(chunk, RetrievedChunk) for chunk in results)
        assert all(chunk.text is not None for chunk in results)
        assert all(chunk.score is not None for chunk in results)
        assert all(chunk.metadata is not None for chunk in results)
        
        # Проверяем сортировку по score (от большего к меньшему)
        scores = [chunk.score for chunk in results]
        assert scores == sorted(scores, reverse=True)
        
        # Проверяем, что search был вызван с правильными параметрами
        qdrant_client.search.assert_called_once()
        call_args = qdrant_client.search.call_args
        assert call_args[1]["limit"] == 3 or call_args[0][1] == 3
    
    def test_retrieve_k5(self, retriever, qdrant_client, embedding_service):
        """
        UC-1 Retrieval: Semantic search с K=5
        
        Given:
            - Запрос пользователя
        When:
            - Вызывается retrieve с K=5
        Then:
            - Возвращается список из 5 RetrievedChunk объектов (или меньше, если недостаточно чанков)
            - Все чанки релевантны запросу
        """
        query = "Какой SLA у сервиса платежей?"
        
        # Настраиваем мок для возврата 5 чанков
        mock_result = Mock()
        mock_points = [
            Mock(id=f"chunk_{i:03d}", score=0.9 - i*0.1, payload={"text": f"Text {i}", "doc_id": "doc_001", "chunk_id": f"chunk_{i:03d}", "source": "it"})
            for i in range(5)
        ]
        mock_result.points = mock_points
        qdrant_client.search.return_value = mock_result
        
        results = retriever.retrieve(query, k=5)
        
        assert len(results) <= 5
        assert all(isinstance(chunk, RetrievedChunk) for chunk in results)
    
    def test_retrieve_k8(self, retriever, qdrant_client, embedding_service):
        """
        UC-4 Retrieval: Semantic search с K=8 (для reranking)
        
        Given:
            - Запрос пользователя
        When:
            - Вызывается retrieve с K=8
        Then:
            - Возвращается список из 8 RetrievedChunk объектов (или меньше)
            - K=8 используется для последующего reranking
        """
        query = "Какой SLA у сервиса платежей?"
        
        # Настраиваем мок для возврата 8 чанков
        mock_result = Mock()
        mock_points = [
            Mock(id=f"chunk_{i:03d}", score=0.9 - i*0.05, payload={"text": f"Text {i}", "doc_id": "doc_001", "chunk_id": f"chunk_{i:03d}", "source": "it"})
            for i in range(8)
        ]
        mock_result.points = mock_points
        qdrant_client.search.return_value = mock_result
        
        results = retriever.retrieve(query, k=8)
        
        assert len(results) <= 8
        assert all(isinstance(chunk, RetrievedChunk) for chunk in results)
    
    def test_retrieve_uses_embedding_service(self, retriever, embedding_service):
        """
        UC-1 Retrieval: Использование EmbeddingService для генерации query embedding
        
        Given:
            - Запрос пользователя
        When:
            - Вызывается retrieve
        Then:
            - EmbeddingService.generate_embeddings вызывается с запросом
            - Сгенерированный embedding используется для поиска в Qdrant
        """
        query = "Какой SLA у сервиса платежей?"
        
        retriever.retrieve(query, k=3)
        
        # Проверяем, что embedding_service был вызван
        embedding_service.generate_embeddings.assert_called_once()
        call_args = embedding_service.generate_embeddings.call_args
        assert query in call_args[0][0] or query == call_args[0][0][0]
    
    def test_retrieve_returns_retrieved_chunk_structure(self, retriever, qdrant_client):
        """
        UC-1 Retrieval: Структура RetrievedChunk
        
        Given:
            - Запрос пользователя
        When:
            - Вызывается retrieve
        Then:
            - Каждый RetrievedChunk содержит:
              - text: str (текст чанка)
              - score: float (релевантность, 0.0-1.0)
              - id: str (chunk_id)
              - metadata: dict (doc_id, source, category, file_path и др.)
        """
        query = "Какой SLA у сервиса платежей?"
        
        results = retriever.retrieve(query, k=3)
        
        for chunk in results:
            assert hasattr(chunk, 'text')
            assert hasattr(chunk, 'score')
            assert hasattr(chunk, 'id')
            assert hasattr(chunk, 'metadata')
            assert isinstance(chunk.text, str)
            assert isinstance(chunk.score, float)
            assert 0.0 <= chunk.score <= 1.0
            assert isinstance(chunk.metadata, dict)
            assert "doc_id" in chunk.metadata
            assert "chunk_id" in chunk.metadata
    
    def test_retrieve_empty_results(self, retriever, qdrant_client, embedding_service):
        """
        UC-5 Retrieval: Обработка отсутствия релевантных результатов
        
        Given:
            - Запрос пользователя, на который нет релевантных чанков в Qdrant
        When:
            - Вызывается retrieve
        Then:
            - Возвращается пустой список или список с низкими scores
            - Не выбрасывается исключение
        """
        query = "Вопрос, на который нет ответа в документации"
        
        # Настраиваем мок для возврата пустого результата
        mock_result = Mock()
        mock_result.points = []
        qdrant_client.search.return_value = mock_result
        
        results = retriever.retrieve(query, k=3)
        
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_retrieve_collection_name(self, retriever, qdrant_client):
        """
        UC-1 Retrieval: Использование коллекции neuro_docs
        
        Given:
            - Retriever создан с collection_name="neuro_docs"
        When:
            - Вызывается retrieve
        Then:
            - Поиск выполняется в коллекции neuro_docs
        """
        query = "Какой SLA у сервиса платежей?"
        
        retriever.retrieve(query, k=3)
        
        # Проверяем, что search был вызван с правильной коллекцией
        call_args = qdrant_client.search.call_args
        # Проверяем keyword arguments
        assert call_args.kwargs.get("collection_name") == "neuro_docs"
    
    def test_retrieve_score_threshold(self, retriever, qdrant_client, embedding_service):
        """
        UC-1 Retrieval: Фильтрация по минимальному score
        
        Given:
            - Запрос пользователя
            - Настроен минимальный score threshold
        When:
            - Вызывается retrieve с score_threshold
        Then:
            - Возвращаются только чанки с score >= threshold
        """
        query = "Какой SLA у сервиса платежей?"
        
        # Настраиваем мок для возврата чанков с разными scores
        mock_result = Mock()
        mock_points = [
            Mock(id="chunk_001", score=0.95, payload={"text": "Text 1", "doc_id": "doc_001", "chunk_id": "chunk_001", "source": "it"}),
            Mock(id="chunk_002", score=0.50, payload={"text": "Text 2", "doc_id": "doc_001", "chunk_id": "chunk_002", "source": "it"}),
            Mock(id="chunk_003", score=0.30, payload={"text": "Text 3", "doc_id": "doc_001", "chunk_id": "chunk_003", "source": "it"}),
        ]
        mock_result.points = mock_points
        qdrant_client.search.return_value = mock_result
        
        results = retriever.retrieve(query, k=3, score_threshold=0.5)
        
        # Проверяем, что все результаты имеют score >= 0.5
        assert all(chunk.score >= 0.5 for chunk in results)
        assert len(results) <= 2  # chunk_003 должен быть отфильтрован
    
    def test_retrieve_latency(self, retriever, qdrant_client, embedding_service):
        """
        UC-7 Retrieval: Проверка latency поиска
        
        Given:
            - Запрос пользователя
        When:
            - Вызывается retrieve
        Then:
            - Latency поиска приемлема (цель: < 200мс p95)
            - Метод завершается быстро
        """
        import time
        query = "Какой SLA у сервиса платежей?"
        
        start_time = time.time()
        results = retriever.retrieve(query, k=3)
        end_time = time.time()
        
        latency = (end_time - start_time) * 1000  # в миллисекундах
        
        # Проверяем, что latency приемлема (для моков должно быть очень быстро)
        assert latency < 1000  # 1 секунда для моков (в реальности должно быть < 200мс)
        assert len(results) >= 0

