"""
AdminAPI - REST API для мониторинга и управления
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Query, Response
from pydantic import BaseModel

from app.agent.agent import AgentController
from app.monitoring.prometheus_metrics import PrometheusMetrics


class SystemMetrics(BaseModel):
    """Системные метрики"""
    timestamp: str
    uptime_seconds: Optional[float] = None


class AgentMetrics(BaseModel):
    """Метрики агента"""
    total_queries: int = 0
    average_latency_ms: Optional[float] = None
    last_query_time: Optional[str] = None


class MetricsResponse(BaseModel):
    """Ответ с метриками"""
    system: SystemMetrics
    agent: AgentMetrics


class LogsResponse(BaseModel):
    """Ответ с логами"""
    logs: list
    total: int


def create_admin_router(
    agent_controller: Optional[AgentController] = None,
    prometheus_metrics: Optional[PrometheusMetrics] = None
) -> APIRouter:
    """
    Создание роутера для AdminAPI
    
    Args:
        agent_controller: Экземпляр AgentController
        prometheus_metrics: Экземпляр PrometheusMetrics (опционально)
    
    Returns:
        APIRouter с admin endpoints
    """
    router = APIRouter()
    
    if agent_controller is None:
        raise ValueError("agent_controller должен быть передан при создании роутера")
    
    # Храним контроллер и метрики в замыкании
    controller = agent_controller
    metrics = prometheus_metrics
    
    @router.get("/metrics", response_model=MetricsResponse, status_code=status.HTTP_200_OK)
    async def get_metrics() -> MetricsResponse:
        """
        Получение метрик системы и агента
        
        Returns:
            Метрики системы и агента
        """
        # Системные метрики
        system_metrics = SystemMetrics(
            timestamp=datetime.now().isoformat(),
            uptime_seconds=None  # В production можно добавить расчёт uptime
        )
        
        # Метрики агента
        decision_log = controller.decision_log
        logs = decision_log.get_log()
        
        # Подсчитываем метрики из логов
        total_queries = len([log for log in logs if log.action == "ask"])
        
        # Извлекаем latency из метаданных
        latency_values = [
            log.metadata.get("latency_ms")
            for log in logs
            if "latency_ms" in log.metadata
        ]
        avg_latency = sum(latency_values) / len(latency_values) if latency_values else None
        
        # Время последнего запроса
        last_query = None
        for log in reversed(logs):
            if log.action == "ask":
                last_query = log.timestamp.isoformat()
                break
        
        agent_metrics = AgentMetrics(
            total_queries=total_queries,
            average_latency_ms=avg_latency,
            last_query_time=last_query
        )
        
        return MetricsResponse(
            system=system_metrics,
            agent=agent_metrics
        )
    
    @router.get("/logs", response_model=LogsResponse, status_code=status.HTTP_200_OK)
    async def get_logs(limit: int = Query(default=100, ge=1, le=1000)) -> LogsResponse:
        """
        Получение логов решений агента
        
        Args:
            limit: Максимальное количество записей
        
        Returns:
            Логи решений агента
        """
        decision_log = controller.decision_log
        all_logs = decision_log.export_log()
        
        # Ограничиваем количество записей
        logs = all_logs[-limit:] if len(all_logs) > limit else all_logs
        
        return LogsResponse(
            logs=logs,
            total=len(all_logs)
        )
    
    @router.get("/metrics/prometheus", status_code=status.HTTP_200_OK)
    async def get_prometheus_metrics() -> Response:
        """
        Endpoint для Prometheus scrape
        
        Returns:
            Метрики в формате Prometheus text format
        """
        if metrics is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Prometheus metrics not available"
            )
        
        prometheus_data = metrics.get_metrics()
        return Response(
            content=prometheus_data,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
    
    return router

