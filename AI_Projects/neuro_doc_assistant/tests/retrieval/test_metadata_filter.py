"""
@file: test_metadata_filter.py
@description: Тесты для MetadataFilter - фильтрация retrieved чанков по метаданным
@dependencies: app.retrieval.metadata_filter
@created: 2024-12-19
"""

import pytest
from app.retrieval.metadata_filter import MetadataFilter
from app.retrieval.retriever import RetrievedChunk


class TestMetadataFilter:
    """
    Тесты для MetadataFilter компонента.
    
    MetadataFilter отвечает за:
    - Фильтрацию retrieved чанков по метаданным (source, category, file_path)
    - Поддержку UC-3 (фильтрация по метаданным)
    """
    
    @pytest.fixture
    def metadata_filter(self):
        """Фикстура для создания экземпляра MetadataFilter"""
        return MetadataFilter()
    
    @pytest.fixture
    def sample_chunks(self):
        """Создаёт тестовые RetrievedChunk объекты"""
        return [
            RetrievedChunk(
                id="chunk_001",
                text="HR политика удалённой работы",
                score=0.95,
                metadata={
                    "doc_id": "doc_001",
                    "chunk_id": "chunk_001",
                    "source": "hr",
                    "category": "hr",
                    "file_path": "hr_01_политика_удалённой_работы.md",
                    "metadata_tags": ["policy"]
                }
            ),
            RetrievedChunk(
                id="chunk_002",
                text="IT инструкция по SLA сервиса платежей",
                score=0.88,
                metadata={
                    "doc_id": "doc_002",
                    "chunk_id": "chunk_002",
                    "source": "it",
                    "category": "it",
                    "file_path": "it_10_порядок_обращения_в_техподдержку.md",
                    "metadata_tags": ["sla"]
                }
            ),
            RetrievedChunk(
                id="chunk_003",
                text="Compliance документ по безопасности",
                score=0.82,
                metadata={
                    "doc_id": "doc_003",
                    "chunk_id": "chunk_003",
                    "source": "compliance",
                    "category": "compliance",
                    "file_path": "compliance_gckrf.md",
                    "metadata_tags": ["security"]
                }
            )
        ]
    
    def test_filter_by_source_hr(self, metadata_filter, sample_chunks):
        """
        UC-3 Retrieval: Фильтрация по source="hr"
        
        Given:
            - Список retrieved чанков с разными source (hr, it, compliance)
        When:
            - Вызывается filter с source="hr"
        Then:
            - Возвращаются только чанки с source="hr"
            - Порядок и scores сохраняются
        """
        filtered = metadata_filter.filter(sample_chunks, source="hr")
        
        assert len(filtered) == 1
        assert filtered[0].metadata["source"] == "hr"
        assert filtered[0].id == "chunk_001"
    
    def test_filter_by_source_it(self, metadata_filter, sample_chunks):
        """
        UC-3 Retrieval: Фильтрация по source="it"
        
        Given:
            - Список retrieved чанков
        When:
            - Вызывается filter с source="it"
        Then:
            - Возвращаются только чанки с source="it"
        """
        filtered = metadata_filter.filter(sample_chunks, source="it")
        
        assert len(filtered) == 1
        assert filtered[0].metadata["source"] == "it"
        assert filtered[0].id == "chunk_002"
    
    def test_filter_by_category(self, metadata_filter, sample_chunks):
        """
        UC-3 Retrieval: Фильтрация по category
        
        Given:
            - Список retrieved чанков с разными category
        When:
            - Вызывается filter с category="it"
        Then:
            - Возвращаются только чанки с category="it"
        """
        filtered = metadata_filter.filter(sample_chunks, category="it")
        
        assert len(filtered) == 1
        assert filtered[0].metadata["category"] == "it"
    
    def test_filter_by_file_path(self, metadata_filter, sample_chunks):
        """
        UC-3 Retrieval: Фильтрация по file_path
        
        Given:
            - Список retrieved чанков
        When:
            - Вызывается filter с file_path (частичное совпадение)
        Then:
            - Возвращаются только чанки, соответствующие file_path
        """
        filtered = metadata_filter.filter(sample_chunks, file_path="hr_01")
        
        assert len(filtered) == 1
        assert "hr_01" in filtered[0].metadata["file_path"]
    
    def test_filter_by_multiple_criteria(self, metadata_filter, sample_chunks):
        """
        UC-3 Retrieval: Фильтрация по нескольким критериям
        
        Given:
            - Список retrieved чанков
        When:
            - Вызывается filter с source="it" и category="it"
        Then:
            - Возвращаются только чанки, соответствующие всем критериям
        """
        filtered = metadata_filter.filter(sample_chunks, source="it", category="it")
        
        assert len(filtered) == 1
        assert filtered[0].metadata["source"] == "it"
        assert filtered[0].metadata["category"] == "it"
    
    def test_filter_preserves_order(self, metadata_filter, sample_chunks):
        """
        UC-3 Retrieval: Сохранение порядка после фильтрации
        
        Given:
            - Список retrieved чанков, отсортированных по score
        When:
            - Вызывается filter
        Then:
            - Порядок чанков сохраняется (отсортирован по score)
        """
        filtered = metadata_filter.filter(sample_chunks, source="it")
        
        if len(filtered) > 1:
            scores = [chunk.score for chunk in filtered]
            assert scores == sorted(scores, reverse=True)
    
    def test_filter_empty_result(self, metadata_filter, sample_chunks):
        """
        UC-3 Retrieval: Фильтрация с пустым результатом
        
        Given:
            - Список retrieved чанков
        When:
            - Вызывается filter с критериями, которым не соответствует ни один чанк
        Then:
            - Возвращается пустой список
        """
        filtered = metadata_filter.filter(sample_chunks, source="nonexistent")
        
        assert len(filtered) == 0
        assert isinstance(filtered, list)
    
    def test_filter_by_metadata_tags(self, metadata_filter, sample_chunks):
        """
        UC-3 Retrieval: Фильтрация по metadata_tags
        
        Given:
            - Список retrieved чанков с metadata_tags
        When:
            - Вызывается filter с metadata_tag="sla"
        Then:
            - Возвращаются только чанки, содержащие указанный тег
        """
        filtered = metadata_filter.filter(sample_chunks, metadata_tag="sla")
        
        assert len(filtered) == 1
        assert "sla" in filtered[0].metadata.get("metadata_tags", [])
    
    def test_filter_no_criteria(self, metadata_filter, sample_chunks):
        """
        UC-3 Retrieval: Фильтрация без критериев
        
        Given:
            - Список retrieved чанков
        When:
            - Вызывается filter без критериев
        Then:
            - Возвращаются все чанки без изменений
        """
        filtered = metadata_filter.filter(sample_chunks)
        
        assert len(filtered) == len(sample_chunks)
        assert filtered == sample_chunks
    
    def test_filter_combines_with_retriever(self, metadata_filter, sample_chunks):
        """
        UC-3 Retrieval: Интеграция MetadataFilter с Retriever
        
        Given:
            - Результаты от Retriever.retrieve()
        When:
            - Применяется MetadataFilter
        Then:
            - Фильтрация работает корректно с результатами Retriever
            - Структура RetrievedChunk сохраняется
        """
        # Симулируем результаты от Retriever
        retriever_results = sample_chunks
        
        # Применяем фильтр
        filtered = metadata_filter.filter(retriever_results, source="it")
        
        # Проверяем, что структура сохранилась
        assert len(filtered) > 0
        for chunk in filtered:
            assert isinstance(chunk, RetrievedChunk)
            assert hasattr(chunk, 'text')
            assert hasattr(chunk, 'score')
            assert hasattr(chunk, 'metadata')

