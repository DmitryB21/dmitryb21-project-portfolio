"""
Тесты для PrometheusMetrics - сбор метрик для мониторинга
"""

import pytest
import time
import sys
from unittest.mock import Mock, MagicMock, patch


@pytest.fixture(autouse=True)
def mock_prometheus_client():
    """Фикстура для мокирования prometheus_client перед импортом"""
    # Мокаем prometheus_client на уровне sys.modules
    mock_prometheus = MagicMock()
    mock_prometheus.Counter = MagicMock(return_value=MagicMock())
    mock_prometheus.Histogram = MagicMock(return_value=MagicMock())
    mock_prometheus.Gauge = MagicMock(return_value=MagicMock())
    mock_prometheus.CollectorRegistry = MagicMock()
    mock_prometheus.generate_latest = MagicMock(return_value=b'# metrics')
    mock_prometheus.REGISTRY = MagicMock()
    
    with patch.dict('sys.modules', {'prometheus_client': mock_prometheus}):
        yield mock_prometheus


class TestPrometheusMetrics:
    """Тесты для PrometheusMetrics"""
    
    def test_metrics_initialization(self, mock_prometheus_client):
        """Тест: инициализация Prometheus метрик"""
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        
        metrics = PrometheusMetrics()
        
        # Проверяем, что метрики созданы
        assert metrics is not None
        assert hasattr(metrics, 'request_counter')
        assert hasattr(metrics, 'request_latency')
        assert hasattr(metrics, 'error_counter')
        assert hasattr(metrics, 'active_requests')
    
    def test_record_request(self, mock_prometheus_client):
        """Тест: запись метрики запроса"""
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        
        metrics = PrometheusMetrics()
        
        # Записываем запрос
        metrics.record_request()
        
        # Проверяем, что inc() был вызван
        metrics.request_counter.inc.assert_called_once()
    
    def test_record_latency(self, mock_prometheus_client):
        """Тест: запись метрики latency"""
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        
        metrics = PrometheusMetrics()
        
        # Записываем latency
        metrics.record_latency(0.5)  # 500ms
        
        # Проверяем, что observe() был вызван с правильным значением
        metrics.request_latency.observe.assert_called_once_with(0.5)
    
    def test_record_error(self, mock_prometheus_client):
        """Тест: запись метрики ошибки"""
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        
        metrics = PrometheusMetrics()
        
        # Записываем ошибку
        metrics.record_error("api_error")
        
        # Проверяем, что labels() и inc() были вызваны
        metrics.error_counter.labels.assert_called_once_with(error_type="api_error")
        metrics.error_counter.labels.return_value.inc.assert_called_once()
    
    def test_record_retrieval_latency(self, mock_prometheus_client):
        """Тест: запись метрики retrieval latency"""
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        
        metrics = PrometheusMetrics()
        
        # Записываем retrieval latency
        metrics.record_retrieval_latency(0.15)  # 150ms
        
        # Проверяем, что observe() был вызван
        metrics.retrieval_latency.observe.assert_called_once_with(0.15)
    
    def test_record_generation_latency(self, mock_prometheus_client):
        """Тест: запись метрики generation latency"""
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        
        metrics = PrometheusMetrics()
        
        # Записываем generation latency
        metrics.record_generation_latency(0.8)  # 800ms
        
        # Проверяем, что observe() был вызван
        metrics.generation_latency.observe.assert_called_once_with(0.8)
    
    def test_active_requests_gauge(self, mock_prometheus_client):
        """Тест: gauge для активных запросов"""
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        
        metrics = PrometheusMetrics()
        
        # Увеличиваем активные запросы
        metrics.increment_active_requests()
        metrics.active_requests.inc.assert_called_once()
        
        # Уменьшаем активные запросы
        metrics.decrement_active_requests()
        metrics.active_requests.dec.assert_called_once()
    
    def test_latency_percentiles(self, mock_prometheus_client):
        """Тест: расчёт перцентилей latency"""
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        
        metrics = PrometheusMetrics()
        
        # Записываем несколько значений latency
        latencies = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        for latency in latencies:
            metrics.record_latency(latency)
        
        # Проверяем, что observe() был вызван для каждого значения
        assert metrics.request_latency.observe.call_count == len(latencies)
    
    def test_qps_calculation(self, mock_prometheus_client):
        """Тест: расчёт QPS (queries per second)"""
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        
        metrics = PrometheusMetrics()
        
        # Записываем несколько запросов
        for _ in range(5):
            metrics.record_request()
        
        # Проверяем, что inc() был вызван 5 раз
        assert metrics.request_counter.inc.call_count == 5
    
    def test_error_types_tracking(self, mock_prometheus_client):
        """Тест: отслеживание разных типов ошибок"""
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        
        metrics = PrometheusMetrics()
        
        # Записываем разные типы ошибок
        error_types = ["api_error", "timeout_error", "validation_error"]
        for error_type in error_types:
            metrics.record_error(error_type)
        
        # Проверяем, что labels() был вызван для каждого типа ошибки
        assert metrics.error_counter.labels.call_count == len(error_types)
    
    def test_context_manager_for_latency(self, mock_prometheus_client):
        """Тест: использование context manager для измерения latency"""
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        
        metrics = PrometheusMetrics()
        
        # Используем context manager
        with metrics.measure_latency():
            time.sleep(0.01)  # Небольшая задержка
        
        # Проверяем, что record_latency был вызван
        metrics.request_latency.observe.assert_called_once()
        # Проверяем, что значение latency > 0
        call_args = metrics.request_latency.observe.call_args[0][0]
        assert call_args > 0

