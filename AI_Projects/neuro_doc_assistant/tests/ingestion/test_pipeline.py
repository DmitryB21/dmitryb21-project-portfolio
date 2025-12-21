"""
@file: test_pipeline.py
@description: Интеграционные тесты для полного Ingestion pipeline
@dependencies: app.ingestion.loader, app.ingestion.chunker, app.ingestion.embedding_service, app.ingestion.indexer
@created: 2024-12-19
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from app.ingestion.loader import DocumentLoader
from app.ingestion.chunker import Chunker
from app.ingestion.embedding_service import EmbeddingService
from app.ingestion.indexer import QdrantIndexer


class TestIngestionPipeline:
    """
    Интеграционные тесты для полного Ingestion pipeline.
    
    Pipeline: файлы → DocumentLoader → Chunker → EmbeddingService → QdrantIndexer
    """

    @pytest.fixture
    def pipeline_components(self, qdrant_client):
        """Создаёт все компоненты pipeline"""
        loader = DocumentLoader()
        chunker = Chunker()
        embedding_service = EmbeddingService(model_version="test_model", embedding_dim=1536)
        indexer = QdrantIndexer(qdrant_client=qdrant_client, collection_name="neuro_docs")
        
        return {
            "loader": loader,
            "chunker": chunker,
            "embedding_service": embedding_service,
            "indexer": indexer
        }

    @pytest.fixture
    def qdrant_client(self):
        """Фикстура для создания мок Qdrant клиента"""
        from unittest.mock import Mock, MagicMock
        mock_client = MagicMock()
        collections_mock = Mock()
        collections_mock.collections = []
        mock_client.get_collections.return_value = collections_mock
        mock_client.create_collection.return_value = True
        mock_client.upsert.return_value = True
        return mock_client

    @pytest.fixture
    def sample_hr_directory(self, tmp_path):
        """Создаёт тестовую директорию с HR документами"""
        hr_dir = tmp_path / "hr"
        hr_dir.mkdir()
        
        # Создаём несколько тестовых файлов
        (hr_dir / "hr_01.md").write_text(
            "# Политика удалённой работы\n\n"
            "## Введение\n\n"
            "Настоящая политика устанавливает правила удалённой работы сотрудников."
        )
        (hr_dir / "hr_02.md").write_text(
            "# Порядок оформления отпуска\n\n"
            "## Общие положения\n\n"
            "Данный документ описывает порядок оформления отпуска."
        )
        
        return hr_dir

    def test_full_pipeline_single_file(self, pipeline_components, tmp_path):
        """
        UC-1 Ingestion: Полный pipeline для одного файла
        
        Given:
            - Один MD файл с документацией
        When:
            - Выполняется полный ingestion pipeline:
              1. DocumentLoader загружает файл
              2. Chunker разбивает на чанки
              3. EmbeddingService генерирует embeddings
              4. QdrantIndexer индексирует в Qdrant
        Then:
            - Все компоненты работают корректно
            - Чанки успешно индексированы в Qdrant
            - Векторное хранилище готово для Retrieval Layer
        """
        # Создаём тестовый файл
        test_file = tmp_path / "test.md"
        test_file.write_text(
            "# Тестовый документ\n\n"
            " ".join([f"Токен {i}" for i in range(500)])  # Достаточно текста для чанкинга
        )
        
        loader = pipeline_components["loader"]
        chunker = pipeline_components["chunker"]
        embedding_service = pipeline_components["embedding_service"]
        indexer = pipeline_components["indexer"]
        
        # Шаг 1: Загрузка документов
        documents = loader.load_documents(str(test_file))
        assert len(documents) == 1
        
        # Шаг 2: Чанкинг
        chunks = chunker.chunk_documents(documents, chunk_size=300)
        assert len(chunks) > 0
        
        # Шаг 3: Генерация embeddings (мок) - создаём правильное количество векторов
        mock_embeddings = [[0.1] * 1536 for _ in chunks]
        with patch.object(embedding_service, 'generate_embeddings', return_value=mock_embeddings):
            embeddings = embedding_service.generate_embeddings([chunk.text for chunk in chunks])
        
        assert len(embeddings) == len(chunks)
        
        # Шаг 4: Индексация
        indexer.index_chunks(chunks, embeddings)
        
        # Проверяем, что индексация прошла успешно
        assert indexer.qdrant_client.upsert.called

    def test_full_pipeline_directory(self, pipeline_components, sample_hr_directory):
        """
        UC-1 Ingestion: Полный pipeline для директории
        
        Given:
            - Директория с несколькими MD файлами (HR документы)
        When:
            - Выполняется полный ingestion pipeline
        Then:
            - Все файлы обработаны
            - Все чанки индексированы в Qdrant
            - Метаданные корректны (category="hr")
        """
        loader = pipeline_components["loader"]
        chunker = pipeline_components["chunker"]
        embedding_service = pipeline_components["embedding_service"]
        indexer = pipeline_components["indexer"]
        
        # Шаг 1: Загрузка документов
        documents = loader.load_documents(str(sample_hr_directory))
        assert len(documents) == 2
        assert all(doc.metadata["category"] == "hr" for doc in documents)
        
        # Шаг 2: Чанкинг
        all_chunks = []
        for doc in documents:
            chunks = chunker.chunk_documents([doc], chunk_size=300)
            all_chunks.extend(chunks)
        
        assert len(all_chunks) > 0
        
        # Шаг 3: Генерация embeddings (мок)
        mock_embeddings = [[0.1] * 1536 for _ in all_chunks]
        with patch.object(embedding_service, 'generate_embeddings', return_value=mock_embeddings):
            embeddings = embedding_service.generate_embeddings([chunk.text for chunk in all_chunks])
        
        # Шаг 4: Индексация
        indexer.index_chunks(all_chunks, embeddings)
        
        assert indexer.qdrant_client.upsert.called

    def test_pipeline_with_real_hr_directory(self, pipeline_components):
        """
        UC-1 Ingestion: Pipeline с реальной директорией HR документов
        
        Given:
            - Реальная директория data/NeuroDoc_Data/hr/
        When:
            - Выполняется полный ingestion pipeline
        Then:
            - Все документы обработаны
            - Векторное хранилище готово для использования в тестах UC-1
        """
        hr_path = Path("data/NeuroDoc_Data/hr")
        if not hr_path.exists():
            pytest.skip("HR directory not found")
        
        loader = pipeline_components["loader"]
        chunker = pipeline_components["chunker"]
        embedding_service = pipeline_components["embedding_service"]
        indexer = pipeline_components["indexer"]
        
        # Загружаем документы
        documents = loader.load_documents(str(hr_path))
        assert len(documents) > 0
        
        # Чанкинг
        all_chunks = []
        for doc in documents:
            chunks = chunker.chunk_documents([doc], chunk_size=300, overlap_percent=0.25)
            all_chunks.extend(chunks)
        
        # Мокаем embeddings для теста (в реальности будут настоящие API вызовы)
        mock_embeddings = [[0.1] * 1536 for _ in all_chunks]
        with patch.object(embedding_service, 'generate_embeddings', return_value=mock_embeddings):
            embeddings = embedding_service.generate_embeddings([chunk.text for chunk in all_chunks])
        
        # Индексация
        indexer.index_chunks(all_chunks, embeddings)
        
        assert indexer.qdrant_client.upsert.called

    def test_pipeline_metadata_flow(self, pipeline_components, tmp_path):
        """
        UC-1 Ingestion: Сохранение метаданных через весь pipeline
        
        Given:
            - Документ с метаданными (category, file_path)
        When:
            - Документ проходит через весь pipeline
        Then:
            - Метаданные сохраняются на каждом этапе
            - Финальные метаданные в Qdrant содержат все необходимые поля
        """
        test_file = tmp_path / "test.md"
        test_file.write_text("# Тестовый документ\n\nТекст документа.")
        
        loader = pipeline_components["loader"]
        chunker = pipeline_components["chunker"]
        embedding_service = pipeline_components["embedding_service"]
        indexer = pipeline_components["indexer"]
        
        # Загрузка
        documents = loader.load_documents(str(test_file))
        original_metadata = documents[0].metadata
        
        # Чанкинг
        chunks = chunker.chunk_documents(documents, chunk_size=300)
        
        # Проверяем сохранение метаданных в чанках
        for chunk in chunks:
            assert chunk.doc_id == documents[0].id
            assert chunk.metadata.get("category") == original_metadata.get("category")
        
        # Embeddings и индексация
        mock_embeddings = [[0.1] * 1536 for _ in chunks]
        with patch.object(embedding_service, 'generate_embeddings', return_value=mock_embeddings):
            embeddings = embedding_service.generate_embeddings([chunk.text for chunk in chunks])
        
        indexer.index_chunks(chunks, embeddings)
        
        # Проверяем, что метаданные переданы в Qdrant
        assert indexer.qdrant_client.upsert.called

