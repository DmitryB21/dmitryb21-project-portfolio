"""
@file: metrics.py
@description: MetricsCollector - расчёт Precision@K и сбор latency/throughput метрик
@dependencies: app.retrieval.retriever
@created: 2024-12-19
"""

from typing import List, Dict, Any
from app.retrieval.retriever import RetrievedChunk


class MetricsCollector:
    """
    Сборщик метрик для оценки качества системы.
    
    Отвечает за:
    - Расчёт Precision@K для retrieved результатов
    - Сбор latency метрик (retrieval, generation, end-to-end)
    - Сбор throughput метрик (QPS)
    """
    
    def __init__(self):
        """Инициализация MetricsCollector"""
        pass
    
    def calculate_precision_at_k(
        self,
        retrieved_chunks: List[RetrievedChunk],
        ground_truth_relevant: List[str],
        k: int
    ) -> float:
        """
        Рассчитывает Precision@K.
        
        Precision@K = (количество релевантных чанков в топ-K) / K
        
        Args:
            retrieved_chunks: Список retrieved чанков, отсортированных по score (от большего к меньшему)
            ground_truth_relevant: Список ID релевантных чанков (ground truth)
            k: Количество чанков для расчёта (3, 5, 8)
            
        Returns:
            Precision@K (0.0-1.0)
        """
        if not retrieved_chunks:
            return 0.0
        
        if not ground_truth_relevant:
            return 0.0
        
        # Берём топ-K чанков
        top_k_chunks = retrieved_chunks[:k]
        
        # Подсчитываем количество релевантных чанков в топ-K
        relevant_count = sum(
            1 for chunk in top_k_chunks
            if chunk.id in ground_truth_relevant
        )
        
        # Precision@K = количество релевантных / K
        precision = relevant_count / len(top_k_chunks)
        
        return precision
    
    def collect_latency_metrics(
        self,
        retrieval_latency_ms: float,
        generation_latency_ms: float,
        end_to_end_latency_ms: float
    ) -> Dict[str, float]:
        """
        Собирает latency метрики.
        
        Args:
            retrieval_latency_ms: Latency retrieval в миллисекундах
            generation_latency_ms: Latency generation в миллисекундах
            end_to_end_latency_ms: End-to-end latency в миллисекундах
            
        Returns:
            Словарь с метриками latency
        """
        return {
            "retrieval_latency_ms": retrieval_latency_ms,
            "generation_latency_ms": generation_latency_ms,
            "end_to_end_latency_ms": end_to_end_latency_ms
        }
    
    def collect_throughput_metrics(
        self,
        total_queries: int,
        time_seconds: float
    ) -> Dict[str, Any]:
        """
        Собирает throughput метрики.
        
        Args:
            total_queries: Общее количество обработанных запросов
            time_seconds: Время в секундах
            
        Returns:
            Словарь с метриками throughput (QPS)
        """
        qps = total_queries / time_seconds if time_seconds > 0 else 0.0
        
        return {
            "total_queries": total_queries,
            "time_seconds": time_seconds,
            "qps": qps
        }

