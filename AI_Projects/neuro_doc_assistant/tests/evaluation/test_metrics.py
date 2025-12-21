"""
@file: test_metrics.py
@description: Тесты для MetricsCollector - расчёт Precision@K и других метрик
@dependencies: app.evaluation.metrics, app.retrieval.retriever
@created: 2024-12-19
"""

import pytest
from app.evaluation.metrics import MetricsCollector
from app.retrieval.retriever import RetrievedChunk


class TestMetricsCollector:
    """
    Тесты для MetricsCollector компонента.
    
    MetricsCollector отвечает за:
    - Расчёт Precision@K для retrieved результатов
    - Сбор latency метрик (retrieval, generation, end-to-end)
    - Сбор throughput метрик
    """
    
    @pytest.fixture
    def metrics_collector(self):
        """Фикстура для создания экземпляра MetricsCollector"""
        return MetricsCollector()
    
    @pytest.fixture
    def sample_retrieved_chunks(self):
        """Создаёт тестовые RetrievedChunk объекты"""
        return [
            RetrievedChunk(
                id="chunk_001",
                text="SLA сервиса платежей составляет 99.9%",
                score=0.95,
                metadata={"doc_id": "doc_001", "source": "it"}
            ),
            RetrievedChunk(
                id="chunk_002",
                text="Время отклика сервиса платежей не более 200мс",
                score=0.88,
                metadata={"doc_id": "doc_001", "source": "it"}
            ),
            RetrievedChunk(
                id="chunk_003",
                text="Документация по SLA сервисов находится в разделе IT",
                score=0.82,
                metadata={"doc_id": "doc_002", "source": "it"}
            )
        ]
    
    def test_calculate_precision_at_3(self, metrics_collector, sample_retrieved_chunks):
        """
        UC-1 Evaluation: Расчёт Precision@3
        
        Given:
            - Список retrieved чанков (K=3)
            - Ground truth: первые 2 чанка релевантны, третий нерелевантен
        When:
            - Вызывается calculate_precision_at_k с k=3
        Then:
            - Возвращается Precision@3 = 2/3 ≈ 0.67
            - Значение в диапазоне [0.0, 1.0]
        """
        # Симулируем ground truth: первые 2 чанка релевантны
        ground_truth_relevant = [sample_retrieved_chunks[0].id, sample_retrieved_chunks[1].id]
        
        precision = metrics_collector.calculate_precision_at_k(
            retrieved_chunks=sample_retrieved_chunks,
            ground_truth_relevant=ground_truth_relevant,
            k=3
        )
        
        assert precision is not None
        assert isinstance(precision, float)
        assert 0.0 <= precision <= 1.0
        assert precision == pytest.approx(2.0 / 3.0, abs=0.01)  # 2 релевантных из 3
    
    def test_calculate_precision_at_3_all_relevant(self, metrics_collector, sample_retrieved_chunks):
        """
        UC-1 Evaluation: Precision@3 = 1.0 когда все чанки релевантны
        
        Given:
            - Список retrieved чанков (K=3)
            - Ground truth: все 3 чанка релевантны
        When:
            - Вызывается calculate_precision_at_k с k=3
        Then:
            - Возвращается Precision@3 = 1.0
        """
        ground_truth_relevant = [chunk.id for chunk in sample_retrieved_chunks]
        
        precision = metrics_collector.calculate_precision_at_k(
            retrieved_chunks=sample_retrieved_chunks,
            ground_truth_relevant=ground_truth_relevant,
            k=3
        )
        
        assert precision == pytest.approx(1.0, abs=0.01)
    
    def test_calculate_precision_at_3_none_relevant(self, metrics_collector, sample_retrieved_chunks):
        """
        UC-1 Evaluation: Precision@3 = 0.0 когда нет релевантных чанков
        
        Given:
            - Список retrieved чанков (K=3)
            - Ground truth: нет релевантных чанков
        When:
            - Вызывается calculate_precision_at_k с k=3
        Then:
            - Возвращается Precision@3 = 0.0
        """
        ground_truth_relevant = []
        
        precision = metrics_collector.calculate_precision_at_k(
            retrieved_chunks=sample_retrieved_chunks,
            ground_truth_relevant=ground_truth_relevant,
            k=3
        )
        
        assert precision == pytest.approx(0.0, abs=0.01)
    
    def test_calculate_precision_at_5(self, metrics_collector):
        """
        UC-1 Evaluation: Расчёт Precision@5
        
        Given:
            - Список retrieved чанков (K=5)
        When:
            - Вызывается calculate_precision_at_k с k=5
        Then:
            - Возвращается Precision@5
        """
        chunks = [
            RetrievedChunk(id=f"chunk_{i:03d}", text=f"Text {i}", score=0.9 - i*0.1, metadata={})
            for i in range(5)
        ]
        ground_truth_relevant = [chunks[0].id, chunks[1].id, chunks[2].id]  # 3 из 5 релевантны
        
        precision = metrics_collector.calculate_precision_at_k(
            retrieved_chunks=chunks,
            ground_truth_relevant=ground_truth_relevant,
            k=5
        )
        
        assert precision == pytest.approx(3.0 / 5.0, abs=0.01)
    
    def test_calculate_precision_at_k_less_than_k(self, metrics_collector):
        """
        UC-1 Evaluation: Обработка случая, когда retrieved меньше K
        
        Given:
            - Список retrieved чанков (2 чанка)
            - Запрос Precision@3
        When:
            - Вызывается calculate_precision_at_k с k=3
        Then:
            - Возвращается Precision@2 (по фактическому количеству)
        """
        chunks = [
            RetrievedChunk(id="chunk_001", text="Text 1", score=0.95, metadata={}),
            RetrievedChunk(id="chunk_002", text="Text 2", score=0.88, metadata={})
        ]
        ground_truth_relevant = [chunks[0].id]  # 1 из 2 релевантен
        
        precision = metrics_collector.calculate_precision_at_k(
            retrieved_chunks=chunks,
            ground_truth_relevant=ground_truth_relevant,
            k=3
        )
        
        assert precision == pytest.approx(1.0 / 2.0, abs=0.01)
    
    def test_collect_latency_metrics(self, metrics_collector):
        """
        UC-7 Evaluation: Сбор latency метрик
        
        Given:
            - Latency для retrieval, generation, end-to-end
        When:
            - Вызывается collect_latency_metrics
        Then:
            - Метрики сохраняются
            - Метрики доступны для получения
        """
        metrics = metrics_collector.collect_latency_metrics(
            retrieval_latency_ms=150.0,
            generation_latency_ms=800.0,
            end_to_end_latency_ms=1000.0
        )
        
        assert metrics is not None
        assert "retrieval_latency_ms" in metrics
        assert "generation_latency_ms" in metrics
        assert "end_to_end_latency_ms" in metrics
        assert metrics["retrieval_latency_ms"] == 150.0
        assert metrics["generation_latency_ms"] == 800.0
        assert metrics["end_to_end_latency_ms"] == 1000.0
    
    def test_latency_metrics_meet_targets(self, metrics_collector):
        """
        UC-7 Evaluation: Проверка соответствия latency целям
        
        Given:
            - Latency метрики
        When:
            - Проверяются цели (p95 < 200мс для retrieval, < 1.3 сек для end-to-end)
        Then:
            - Метрики соответствуют или не соответствуют целям
        """
        # Тест с метриками, соответствующими целям
        metrics_good = metrics_collector.collect_latency_metrics(
            retrieval_latency_ms=150.0,
            generation_latency_ms=800.0,
            end_to_end_latency_ms=1000.0
        )
        
        # Проверяем, что метрики в пределах целей
        assert metrics_good["retrieval_latency_ms"] < 200.0
        assert metrics_good["end_to_end_latency_ms"] < 1300.0
        
        # Тест с метриками, не соответствующими целям
        metrics_bad = metrics_collector.collect_latency_metrics(
            retrieval_latency_ms=300.0,
            generation_latency_ms=1500.0,
            end_to_end_latency_ms=2000.0
        )
        
        # Проверяем, что метрики превышают цели
        assert metrics_bad["retrieval_latency_ms"] > 200.0
        assert metrics_bad["end_to_end_latency_ms"] > 1300.0
    
    def test_collect_throughput_metrics(self, metrics_collector):
        """
        UC-7 Evaluation: Сбор throughput метрик
        
        Given:
            - Количество обработанных запросов за период
        When:
            - Вызывается collect_throughput_metrics
        Then:
            - Метрики сохраняются
            - QPS (queries per second) рассчитывается
        """
        metrics = metrics_collector.collect_throughput_metrics(
            total_queries=100,
            time_seconds=60.0
        )
        
        assert metrics is not None
        assert "total_queries" in metrics
        assert "time_seconds" in metrics
        assert "qps" in metrics
        assert metrics["qps"] == pytest.approx(100.0 / 60.0, abs=0.01)
    
    def test_metrics_structure(self, metrics_collector, sample_retrieved_chunks):
        """
        UC-1 Evaluation: Структура возвращаемых метрик
        
        Given:
            - Retrieved чанки и ground truth
        When:
            - Вызываются методы расчёта метрик
        Then:
            - Метрики возвращаются в структурированном виде (dict)
            - Метрики могут быть использованы в response.metrics
        """
        ground_truth_relevant = [sample_retrieved_chunks[0].id, sample_retrieved_chunks[1].id]
        
        precision = metrics_collector.calculate_precision_at_k(
            retrieved_chunks=sample_retrieved_chunks,
            ground_truth_relevant=ground_truth_relevant,
            k=3
        )
        
        # Проверяем, что precision может быть использован в response.metrics
        metrics = {
            "precision_at_3": precision
        }
        
        assert "precision_at_3" in metrics
        assert isinstance(metrics["precision_at_3"], float)
        assert 0.0 <= metrics["precision_at_3"] <= 1.0

