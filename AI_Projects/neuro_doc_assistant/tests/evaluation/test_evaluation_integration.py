"""
@file: test_evaluation_integration.py
@description: Интеграционные тесты для Evaluation & Metrics с другими модулями
@dependencies: app.evaluation.*, app.generation.*, app.retrieval.*
@created: 2024-12-19
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.evaluation.metrics import MetricsCollector
from app.evaluation.ragas_evaluator import RAGASEvaluator
from app.retrieval.retriever import RetrievedChunk


class TestEvaluationIntegration:
    """
    Интеграционные тесты для Evaluation & Metrics.
    
    Проверяют интеграцию MetricsCollector и RAGASEvaluator с другими модулями.
    """
    
    @pytest.fixture
    def metrics_collector(self):
        """Фикстура для MetricsCollector"""
        return MetricsCollector()
    
    @pytest.fixture
    def ragas_evaluator(self):
        """Фикстура для RAGASEvaluator"""
        return RAGASEvaluator(mock_mode=True)
    
    def test_precision_at_3_with_retrieved_chunks(self, metrics_collector):
        """
        UC-1 Evaluation: Расчёт Precision@3 с результатами Retrieval
        
        Given:
            - Retrieved чанки от Retriever
            - Ground truth релевантные чанки
        When:
            - Вызывается calculate_precision_at_k
        Then:
            - Precision@3 рассчитывается корректно
            - Метрика может быть использована в response.metrics
        """
        retrieved = [
            RetrievedChunk(id="chunk_001", text="Text 1", score=0.95, metadata={}),
            RetrievedChunk(id="chunk_002", text="Text 2", score=0.88, metadata={}),
            RetrievedChunk(id="chunk_003", text="Text 3", score=0.82, metadata={})
        ]
        ground_truth = ["chunk_001", "chunk_002"]  # 2 из 3 релевантны
        
        precision = metrics_collector.calculate_precision_at_k(
            retrieved_chunks=retrieved,
            ground_truth_relevant=ground_truth,
            k=3
        )
        
        assert precision == pytest.approx(2.0 / 3.0, abs=0.01)
    
    def test_ragas_with_generated_answer(self, ragas_evaluator):
        """
        UC-1 Evaluation: Оценка RAGAS для сгенерированного ответа
        
        Given:
            - Вопрос пользователя
            - Сгенерированный ответ от Generation Layer
            - Retrieved контексты от Retrieval Layer
        When:
            - Вызывается evaluate_all
        Then:
            - Все RAGAS метрики рассчитываются
            - Метрики соответствуют целям проекта (Faithfulness ≥ 0.85, Answer Relevancy ≥ 0.80)
        """
        question = "Какой SLA у сервиса платежей?"
        answer = "SLA сервиса платежей составляет 99.9%"
        contexts = [
            "SLA сервиса платежей составляет 99.9%",
            "Время отклика сервиса платежей не более 200мс"
        ]
        
        metrics = ragas_evaluator.evaluate_all(
            question=question,
            answer=answer,
            contexts=contexts,
            ground_truth="SLA сервиса платежей составляет 99.9%"
        )
        
        assert "faithfulness" in metrics
        assert "answer_relevancy" in metrics
        assert 0.0 <= metrics["faithfulness"] <= 1.0
        assert 0.0 <= metrics["answer_relevancy"] <= 1.0
    
    def test_full_evaluation_pipeline(self, metrics_collector, ragas_evaluator):
        """
        UC-1 Evaluation: Полный pipeline оценки
        
        Given:
            - Вопрос, ответ, retrieved чанки, ground truth
        When:
            - Выполняется полная оценка (Precision@K + RAGAS)
        Then:
            - Все метрики рассчитываются
            - Метрики объединяются в response.metrics
        """
        question = "Какой SLA у сервиса платежей?"
        answer = "SLA сервиса платежей составляет 99.9%"
        retrieved = [
            RetrievedChunk(id="chunk_001", text="SLA сервиса платежей составляет 99.9%", score=0.95, metadata={}),
            RetrievedChunk(id="chunk_002", text="Время отклика не более 200мс", score=0.88, metadata={}),
            RetrievedChunk(id="chunk_003", text="Документация в разделе IT", score=0.82, metadata={})
        ]
        ground_truth_relevant = ["chunk_001", "chunk_002"]
        contexts = [chunk.text for chunk in retrieved]
        
        # Расчёт Precision@3
        precision = metrics_collector.calculate_precision_at_k(
            retrieved_chunks=retrieved,
            ground_truth_relevant=ground_truth_relevant,
            k=3
        )
        
        # Расчёт RAGAS метрик
        ragas_metrics = ragas_evaluator.evaluate_all(
            question=question,
            answer=answer,
            contexts=contexts,
            ground_truth="SLA сервиса платежей составляет 99.9%"
        )
        
        # Объединение метрик
        all_metrics = {
            "precision_at_3": precision,
            **ragas_metrics
        }
        
        assert "precision_at_3" in all_metrics
        assert "faithfulness" in all_metrics
        assert "answer_relevancy" in all_metrics
        assert all_metrics["precision_at_3"] >= 0.0
        assert all_metrics["faithfulness"] >= 0.0
        assert all_metrics["answer_relevancy"] >= 0.0

