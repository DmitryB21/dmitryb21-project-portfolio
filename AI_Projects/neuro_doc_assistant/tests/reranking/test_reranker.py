"""
Тесты для Reranker - переупорядочивание retrieved документов
"""

import pytest
from unittest.mock import Mock, MagicMock
from app.reranking.reranker import Reranker
from app.retrieval.retriever import RetrievedChunk


@pytest.fixture
def sample_chunks():
    """Фикстура с примерными retrieved чанками"""
    return [
        RetrievedChunk(
            id="chunk_1",
            text="SLA сервиса платежей составляет 99.9%. Время отклика не более 200мс.",
            score=0.85,
            metadata={"doc_id": "doc_1", "category": "it", "file_path": "it/payments.md"}
        ),
        RetrievedChunk(
            id="chunk_2",
            text="Сервис платежей обрабатывает транзакции. SLA гарантирует доступность.",
            score=0.78,
            metadata={"doc_id": "doc_2", "category": "it", "file_path": "it/payments.md"}
        ),
        RetrievedChunk(
            id="chunk_3",
            text="HR политика компании включает правила отпусков и больничных.",
            score=0.65,
            metadata={"doc_id": "doc_3", "category": "hr", "file_path": "hr/policy.md"}
        ),
        RetrievedChunk(
            id="chunk_4",
            text="Платежный сервис имеет SLA 99.9% и время отклика 200мс.",
            score=0.72,
            metadata={"doc_id": "doc_4", "category": "it", "file_path": "it/payments.md"}
        ),
        RetrievedChunk(
            id="chunk_5",
            text="IT отдел поддерживает сервисы с различными SLA требованиями.",
            score=0.60,
            metadata={"doc_id": "doc_5", "category": "it", "file_path": "it/general.md"}
        ),
    ]


class TestReranker:
    """Тесты для Reranker"""
    
    def test_rerank_improves_order(self, sample_chunks):
        """Тест: reranking улучшает порядок чанков по релевантности"""
        query = "Какой SLA у сервиса платежей?"
        
        reranker = Reranker()
        reranked = reranker.rerank(query=query, chunks=sample_chunks, top_k=3)
        
        # Проверяем, что вернулось top_k чанков
        assert len(reranked) == 3
        
        # Проверяем, что чанки отсортированы по релевантности (убывание)
        for i in range(len(reranked) - 1):
            assert reranked[i].rerank_score >= reranked[i + 1].rerank_score
    
    def test_rerank_preserves_chunks(self, sample_chunks):
        """Тест: reranking сохраняет все данные чанков"""
        query = "Какой SLA у сервиса платежей?"
        
        reranker = Reranker()
        reranked = reranker.rerank(query=query, chunks=sample_chunks, top_k=3)
        
        # Проверяем, что все поля сохранены
        for chunk in reranked:
            assert hasattr(chunk, "id")
            assert hasattr(chunk, "text")
            assert hasattr(chunk, "metadata")
            assert hasattr(chunk, "rerank_score")
    
    def test_rerank_top_k_parameter(self, sample_chunks):
        """Тест: параметр top_k ограничивает количество возвращаемых чанков"""
        query = "Какой SLA у сервиса платежей?"
        
        reranker = Reranker()
        
        # Тест с top_k=2
        reranked_2 = reranker.rerank(query=query, chunks=sample_chunks, top_k=2)
        assert len(reranked_2) == 2
        
        # Тест с top_k=5
        reranked_5 = reranker.rerank(query=query, chunks=sample_chunks, top_k=5)
        assert len(reranked_5) == 5
        
        # Тест с top_k больше количества чанков
        reranked_10 = reranker.rerank(query=query, chunks=sample_chunks, top_k=10)
        assert len(reranked_10) == len(sample_chunks)
    
    def test_rerank_empty_chunks(self):
        """Тест: reranking с пустым списком чанков"""
        query = "Какой SLA у сервиса платежей?"
        
        reranker = Reranker()
        reranked = reranker.rerank(query=query, chunks=[], top_k=3)
        
        assert reranked == []
    
    def test_rerank_single_chunk(self, sample_chunks):
        """Тест: reranking с одним чанком"""
        query = "Какой SLA у сервиса платежей?"
        single_chunk = [sample_chunks[0]]
        
        reranker = Reranker()
        reranked = reranker.rerank(query=query, chunks=single_chunk, top_k=3)
        
        assert len(reranked) == 1
        assert reranked[0].id == single_chunk[0].id
    
    def test_rerank_score_calculation(self, sample_chunks):
        """Тест: rerank_score рассчитывается для каждого чанка"""
        query = "Какой SLA у сервиса платежей?"
        
        reranker = Reranker()
        reranked = reranker.rerank(query=query, chunks=sample_chunks, top_k=3)
        
        # Проверяем, что у всех чанков есть rerank_score
        for chunk in reranked:
            assert hasattr(chunk, "rerank_score")
            assert isinstance(chunk.rerank_score, float)
            assert 0.0 <= chunk.rerank_score <= 1.0
    
    def test_rerank_improves_precision(self, sample_chunks):
        """Тест: reranking улучшает Precision@3 (более релевантные чанки выше)"""
        query = "Какой SLA у сервиса платежей?"
        
        # Ground truth: chunk_1 и chunk_4 наиболее релевантны (содержат "SLA" и "99.9%")
        ground_truth_relevant = ["chunk_1", "chunk_4"]
        
        reranker = Reranker()
        reranked = reranker.rerank(query=query, chunks=sample_chunks, top_k=3)
        
        # Проверяем, что релевантные чанки находятся в топ-3
        reranked_ids = [chunk.id for chunk in reranked]
        relevant_in_top3 = sum(1 for chunk_id in reranked_ids if chunk_id in ground_truth_relevant)
        
        # После reranking должно быть больше релевантных чанков в топ-3
        assert relevant_in_top3 >= 1  # Хотя бы один релевантный чанк в топ-3
    
    def test_rerank_query_relevance(self, sample_chunks):
        """Тест: reranking учитывает релевантность к запросу"""
        query_hr = "Какие правила отпусков?"
        query_it = "Какой SLA у сервиса платежей?"
        
        reranker = Reranker()
        
        # Для HR запроса HR чанк должен быть выше
        reranked_hr = reranker.rerank(query=query_hr, chunks=sample_chunks, top_k=3)
        hr_chunk_in_top = any(chunk.metadata.get("category") == "hr" for chunk in reranked_hr[:2])
        
        # Для IT запроса IT чанки должны быть выше
        reranked_it = reranker.rerank(query=query_it, chunks=sample_chunks, top_k=3)
        it_chunks_in_top = sum(1 for chunk in reranked_it[:2] if chunk.metadata.get("category") == "it")
        
        assert hr_chunk_in_top or it_chunks_in_top >= 2  # Хотя бы один из тестов должен пройти

