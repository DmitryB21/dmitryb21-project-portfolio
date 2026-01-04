"""
@file: prometheus_metrics.py
@description: PrometheusMetrics - сбор метрик для мониторинга latency, QPS и ошибок
@dependencies: prometheus_client
@created: 2024-12-19
"""

import time
from contextlib import contextmanager
from typing import Optional, Any


def _import_prometheus_client():
    """Импорт prometheus_client с обработкой ошибок"""
    try:
        from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, REGISTRY
        return Counter, Histogram, Gauge, CollectorRegistry, generate_latest, REGISTRY
    except ImportError:
        return None, None, None, None, None, None


class PrometheusMetrics:
    """
    Класс для сбора Prometheus метрик.
    
    Отвечает за:
    - Сбор метрик latency (end-to-end, retrieval, generation)
    - Сбор метрик QPS (queries per second)
    - Сбор метрик ошибок
    - Отслеживание активных запросов
    """
    
    def __init__(self, registry: Optional[Any] = None):
        """
        Инициализация PrometheusMetrics.
        
        Args:
            registry: Prometheus registry (если None, используется REGISTRY по умолчанию)
        
        Raises:
            ImportError: Если prometheus_client не установлен
        """
        Counter, Histogram, Gauge, CollectorRegistry, generate_latest, REGISTRY = _import_prometheus_client()
        
        if Counter is None:
            raise ImportError(
                "prometheus_client is not installed. "
                "Install it with: pip install prometheus-client"
            )
        
        self.Counter = Counter
        self.Histogram = Histogram
        self.Gauge = Gauge
        self.CollectorRegistry = CollectorRegistry
        self.generate_latest = generate_latest
        self.REGISTRY = REGISTRY
        
        self.registry = registry or REGISTRY
        
        # Счётчик запросов
        self.request_counter = self.Counter(
            'neuro_doc_assistant_requests_total',
            'Total number of requests',
            registry=self.registry
        )
        
        # Гистограмма latency для end-to-end запросов
        self.request_latency = self.Histogram(
            'neuro_doc_assistant_request_latency_seconds',
            'Request latency in seconds',
            buckets=[0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.3, 2.0, 5.0],
            registry=self.registry
        )
        
        # Гистограмма latency для retrieval
        self.retrieval_latency = self.Histogram(
            'neuro_doc_assistant_retrieval_latency_seconds',
            'Retrieval latency in seconds',
            buckets=[0.01, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5],
            registry=self.registry
        )
        
        # Гистограмма latency для generation
        self.generation_latency = self.Histogram(
            'neuro_doc_assistant_generation_latency_seconds',
            'Generation latency in seconds',
            buckets = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 2.0, 2.5, 3.0],
            registry=self.registry
        )
        
        # Gauge для последних значений latency (для мониторинга текущего состояния)
        self.last_request_latency = self.Gauge(
            'neuro_doc_assistant_request_latency_last_seconds',
            'Last request latency in seconds',
            registry=self.registry
        )
        
        self.last_retrieval_latency = self.Gauge(
            'neuro_doc_assistant_retrieval_latency_last_seconds',
            'Last retrieval latency in seconds',
            registry=self.registry
        )
        
        self.last_generation_latency = self.Gauge(
            'neuro_doc_assistant_generation_latency_last_seconds',
            'Last generation latency in seconds',
            registry=self.registry
        )
        
        # Счётчик ошибок с типами
        self.error_counter = self.Counter(
            'neuro_doc_assistant_errors_total',
            'Total number of errors',
            ['error_type'],
            registry=self.registry
        )
        
        # Gauge для активных запросов
        self.active_requests = self.Gauge(
            'neuro_doc_assistant_active_requests',
            'Number of active requests',
            registry=self.registry
        )
    
    def record_request(self) -> None:
        """Записывает метрику запроса"""
        self.request_counter.inc()
    
    def record_latency(self, latency_seconds: float) -> None:
        """
        Записывает метрику end-to-end latency.
        
        Args:
            latency_seconds: Latency в секундах
        """
        self.request_latency.observe(latency_seconds)
        self.last_request_latency.set(latency_seconds)
    
    def record_retrieval_latency(self, latency_seconds: float) -> None:
        """
        Записывает метрику retrieval latency.
        
        Args:
            latency_seconds: Latency в секундах
        """
        self.retrieval_latency.observe(latency_seconds)
        self.last_retrieval_latency.set(latency_seconds)
    
    def record_generation_latency(self, latency_seconds: float) -> None:
        """
        Записывает метрику generation latency.
        
        Args:
            latency_seconds: Latency в секундах
        """
        self.generation_latency.observe(latency_seconds)
        self.last_generation_latency.set(latency_seconds)
    
    def record_error(self, error_type: str) -> None:
        """
        Записывает метрику ошибки.
        
        Args:
            error_type: Тип ошибки (api_error, timeout_error, validation_error и др.)
        """
        self.error_counter.labels(error_type=error_type).inc()
    
    def increment_active_requests(self) -> None:
        """Увеличивает счётчик активных запросов"""
        self.active_requests.inc()
    
    def decrement_active_requests(self) -> None:
        """Уменьшает счётчик активных запросов"""
        self.active_requests.dec()
    
    @contextmanager
    def measure_latency(self):
        """
        Context manager для измерения latency.
        
        Usage:
            with metrics.measure_latency():
                # код для измерения
        """
        start_time = time.time()
        try:
            yield
        finally:
            latency = time.time() - start_time
            self.record_latency(latency)
    
    def get_metrics(self) -> bytes:
        """
        Возвращает метрики в формате Prometheus.
        
        Returns:
            Метрики в формате Prometheus text format
        """
        return self.generate_latest(self.registry)

