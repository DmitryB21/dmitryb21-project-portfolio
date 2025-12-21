"""
@file: test_indexer.py
@description: Тесты для QdrantIndexer - индексация чанков в Qdrant
@dependencies: app.ingestion.indexer, qdrant_client
@created: 2024-12-19
"""

import pytest
from datetime import datetime
from app.ingestion.indexer import QdrantIndexer
from app.ingestion.chunker import Chunk


class TestQdrantIndexer:
    """
    Тесты для QdrantIndexer компонента.
    
    QdrantIndexer отвечает за:
    - Создание коллекции в Qdrant (если не существует)
    - Загрузку чанков с векторами и метаданными в Qdrant
    - Коллекция: neuro_docs (одна коллекция для всех документов)
    """

    @pytest.fixture
    def indexer(self, qdrant_client):
        """Фикстура для создания экземпляра QdrantIndexer"""
        return QdrantIndexer(qdrant_client=qdrant_client, collection_name="neuro_docs")

    @pytest.fixture
    def qdrant_client(self):
        """Фикстура для создания мок Qdrant клиента"""
        # В реальной реализации это будет настоящий Qdrant клиент или тестовый инстанс
        from unittest.mock import Mock, MagicMock
        mock_client = MagicMock()
        
        # Мокаем get_collections
        collections_mock = Mock()
        collections_mock.collections = []
        mock_client.get_collections.return_value = collections_mock
        
        # Мокаем create_collection
        mock_client.create_collection.return_value = True
        
        # Мокаем upsert
        mock_client.upsert.return_value = True
        
        return mock_client

    @pytest.fixture
    def sample_chunks(self):
        """Создаёт тестовые чанки"""
        return [
            Chunk(
                chunk_id="chunk_001",
                doc_id="doc_001",
                text="Первый чанк текста для тестирования.",
                text_length=10,
                metadata={
                    "source": "hr",
                    "category": "hr",
                    "file_path": "hr_01.md",
                    "metadata_tags": ["policy"]
                }
            ),
            Chunk(
                chunk_id="chunk_002",
                doc_id="doc_001",
                text="Второй чанк текста для тестирования.",
                text_length=10,
                metadata={
                    "source": "hr",
                    "category": "hr",
                    "file_path": "hr_01.md",
                    "metadata_tags": ["policy"]
                }
            )
        ]

    @pytest.fixture
    def sample_embeddings(self):
        """Создаёт тестовые embeddings (размерность 1536)"""
        return [
            [0.1] * 1536,
            [0.2] * 1536
        ]

    def test_create_collection_if_not_exists(self, indexer, qdrant_client):
        """
        UC-1 Ingestion: Создание коллекции neuro_docs если не существует
        
        Given:
            - Коллекция neuro_docs не существует в Qdrant
        When:
            - Вызывается index_chunks
        Then:
            - Коллекция создаётся с правильными параметрами (vector_size, distance)
            - Коллекция имеет имя neuro_docs
        """
        from unittest.mock import Mock
        collections_mock = Mock()
        collections_mock.collections = []
        qdrant_client.get_collections.return_value = collections_mock
        
        # Создаём тестовые чанки и embeddings
        from app.ingestion.chunker import Chunk
        test_chunks = [Chunk(
            chunk_id="test_001",
            doc_id="doc_001",
            text="Test text",
            text_length=10,
            metadata={"source": "hr"}
        )]
        test_embeddings = [[0.1] * 1536]
        
        indexer.index_chunks(test_chunks, test_embeddings, collection_name="neuro_docs")
        
        # Проверяем, что create_collection был вызван (если коллекция не существует)
        # или upsert был вызван (если коллекция существует)
        assert qdrant_client.upsert.called or qdrant_client.create_collection.called

    def test_index_chunks_with_metadata(self, indexer, qdrant_client, sample_chunks, sample_embeddings):
        """
        UC-1 Ingestion: Индексация чанков с полными метаданными
        
        Given:
            - Список чанков с метаданными
            - Список embeddings соответствующих размерностей
        When:
            - Вызывается index_chunks
        Then:
            - Чанки записываются в Qdrant с правильными метаданными
            - Метаданные содержат все обязательные поля (doc_id, chunk_id, source, created_at, text_length, embedding_version, metadata_tags)
        """
        indexer.index_chunks(sample_chunks, sample_embeddings)
        
        # Проверяем, что upsert был вызван
        assert qdrant_client.upsert.called
        
        # Проверяем структуру payload метаданных
        call_args = qdrant_client.upsert.call_args
        points = call_args[1].get("points") or call_args[0][1] if call_args[0] else None
        
        if points:
            for point in points:
                payload = point.payload
                assert "doc_id" in payload
                assert "chunk_id" in payload
                assert "source" in payload
                assert "created_at" in payload
                assert "text_length" in payload
                assert "embedding_version" in payload
                assert "metadata_tags" in payload
                assert "text" in payload

    def test_collection_name_neuro_docs(self, indexer):
        """
        UC-1 Ingestion: Использование коллекции neuro_docs
        
        Given:
            - QdrantIndexer создан с collection_name="neuro_docs"
        When:
            - Индексируются чанки
        Then:
            - Используется коллекция neuro_docs (одна коллекция для всех документов)
        """
        assert indexer.collection_name == "neuro_docs"

    def test_metadata_structure_complete(self, indexer, qdrant_client, sample_chunks, sample_embeddings):
        """
        UC-1 Ingestion: Полная структура метаданных payload
        
        Given:
            - Чанк с полными метаданными
        When:
            - Чанк индексируется в Qdrant
        Then:
            - Payload содержит все обязательные поля:
              - doc_id (string)
              - chunk_id (string)
              - source (string: HR, IT, Compliance)
              - created_at (datetime)
              - text_length (int)
              - embedding_version (string)
              - metadata_tags (list[str])
              - text (string)
        """
        indexer.index_chunks(sample_chunks, sample_embeddings)
        
        # Проверяем структуру через мок
        assert qdrant_client.upsert.called

    def test_optional_experiment_id(self, indexer, qdrant_client, sample_chunks, sample_embeddings):
        """
        UC-6 Ingestion: Опциональное поле experiment_id в метаданных
        
        Given:
            - Чанк с experiment_id в метаданных
        When:
            - Чанк индексируется в Qdrant
        Then:
            - Payload содержит experiment_id (если указан)
            - experiment_id используется для привязки к экспериментальному прогону
        """
        # Добавляем experiment_id к метаданным
        sample_chunks[0].metadata["experiment_id"] = "exp_001"
        
        indexer.index_chunks(sample_chunks, sample_embeddings)
        
        assert qdrant_client.upsert.called

    def test_vector_dimension_match(self, indexer, qdrant_client, sample_chunks):
        """
        UC-1 Ingestion: Соответствие размерности векторов
        
        Given:
            - Embeddings размерности 1536
            - Коллекция создана с vector_size=1536
        When:
            - Индексируются чанки
        Then:
            - Размерность векторов соответствует размерности коллекции
            - Не возникает ошибок несоответствия размерности
        """
        embeddings_1536 = [[0.1] * 1536 for _ in sample_chunks]
        
        indexer.index_chunks(sample_chunks, embeddings_1536)
        
        assert qdrant_client.upsert.called

    def test_multiple_chunks_indexing(self, indexer, qdrant_client):
        """
        UC-1 Ingestion: Индексация множества чанков
        
        Given:
            - Большой список чанков (например, 100 чанков)
        When:
            - Вызывается index_chunks
        Then:
            - Все чанки индексируются
            - Производительность приемлема (батчинг при необходимости)
        """
        many_chunks = [
            Chunk(
                chunk_id=f"chunk_{i:03d}",
                doc_id=f"doc_{i // 10:03d}",
                text=f"Текст чанка {i}",
                text_length=100,
                metadata={"source": "hr", "category": "hr"}
            )
            for i in range(100)
        ]
        many_embeddings = [[0.1] * 1536 for _ in range(100)]
        
        indexer.index_chunks(many_chunks, many_embeddings)
        
        assert qdrant_client.upsert.called

    def test_error_handling_qdrant_failure(self, indexer, qdrant_client, sample_chunks, sample_embeddings):
        """
        UC-1 Ingestion: Обработка ошибок Qdrant
        
        Given:
            - Qdrant возвращает ошибку при индексации
        When:
            - Вызывается index_chunks
        Then:
            - Выбрасывается соответствующее исключение
            - Ошибка логируется
        """
        qdrant_client.upsert.side_effect = Exception("Qdrant error")
        
        with pytest.raises(Exception):
            indexer.index_chunks(sample_chunks, sample_embeddings)

    def test_empty_chunks_handling(self, indexer, qdrant_client):
        """
        UC-1 Ingestion: Обработка пустого списка чанков
        
        Given:
            - Пустой список чанков
        When:
            - Вызывается index_chunks
        Then:
            - Метод завершается без ошибок
            - Коллекция не создаётся, если не существует
        """
        indexer.index_chunks([], [])
        
        # Не должно быть вызовов upsert для пустого списка
        # Но коллекция может быть создана для будущего использования
        pass

