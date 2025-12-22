"""
AdminAPI - REST API для мониторинга и управления
"""

import os
import requests
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Query, Response
from pydantic import BaseModel
from dotenv import load_dotenv

from app.agent.agent import AgentController
from app.monitoring.prometheus_metrics import PrometheusMetrics

load_dotenv()


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


class ServiceStatus(BaseModel):
    """Статус сервиса"""
    available: bool
    message: str
    details: Optional[dict] = None


class ServicesStatusResponse(BaseModel):
    """Ответ со статусом сервисов"""
    qdrant: ServiceStatus
    gigachat_api: ServiceStatus


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
    
    @router.get("/services/status", response_model=ServicesStatusResponse, status_code=status.HTTP_200_OK)
    async def get_services_status() -> ServicesStatusResponse:
        """
        Проверка статуса внешних сервисов (Qdrant и GigaChat API)
        
        Returns:
            Статус доступности Qdrant и GigaChat API
        """
        # Проверка Qdrant
        qdrant_status = _check_qdrant_status(controller)
        
        # Проверка GigaChat API
        gigachat_status = _check_gigachat_api_status()
        
        return ServicesStatusResponse(
            qdrant=qdrant_status,
            gigachat_api=gigachat_status
        )
    
    return router


def _check_qdrant_status(controller: AgentController) -> ServiceStatus:
    """
    Проверка доступности Qdrant
    
    Args:
        controller: AgentController с доступом к Qdrant клиенту
        
    Returns:
        ServiceStatus с информацией о доступности Qdrant
    """
    try:
        qdrant_client = controller.retriever.qdrant_client
        
        # Пытаемся получить список коллекций
        collections = qdrant_client.get_collections()
        
        # Проверяем наличие коллекции neuro_docs
        collection_name = os.getenv("QDRANT_COLLECTION", "neuro_docs")
        collection_names = [col.name for col in collections.collections]
        
        if collection_name in collection_names:
            # Получаем информацию о коллекции
            collection_info = qdrant_client.get_collection(collection_name)
            return ServiceStatus(
                available=True,
                message=f"✅ Qdrant доступен. Коллекция '{collection_name}' найдена.",
                details={
                    "collection_name": collection_name,
                    "points_count": collection_info.points_count,
                    "vector_size": collection_info.config.params.vectors.size,
                    "distance": collection_info.config.params.vectors.distance.value
                }
            )
        else:
            return ServiceStatus(
                available=True,
                message=f"⚠️ Qdrant доступен, но коллекция '{collection_name}' не найдена.",
                details={
                    "collection_name": collection_name,
                    "available_collections": collection_names
                }
            )
    except Exception as e:
        return ServiceStatus(
            available=False,
            message=f"❌ Qdrant недоступен: {str(e)}",
            details={
                "error": str(e),
                "qdrant_url": os.getenv("QDRANT_URL") or f"http://{os.getenv('QDRANT_HOST', 'localhost')}:{os.getenv('QDRANT_PORT', '6333')}"
            }
        )


def _check_gigachat_api_status() -> ServiceStatus:
    """
    Проверка доступности GigaChat API
    
    Returns:
        ServiceStatus с информацией о доступности GigaChat API
    """
    # Используем GIGACHAT_AUTH_KEY для OAuth 2.0 аутентификации
    auth_key = os.getenv("GIGACHAT_AUTH_KEY")
    # Проверяем старый формат для обратной совместимости
    old_api_key = os.getenv("GIGACHAT_API_KEY")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    mock_mode = os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true"
    
    # Если используется старый формат, предупреждаем
    using_old_format = bool(old_api_key) and not auth_key
    
    # Официальные endpoints
    api_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    embeddings_url = "https://gigachat.devices.sberbank.ru/api/v1/embeddings"
    
    # Если mock mode включен, считаем что API не используется
    if mock_mode:
        return ServiceStatus(
            available=False,
            message="⚠️ GigaChat API не используется (mock mode включен)",
            details={
                "mock_mode": True,
                "auth_key_set": bool(auth_key),
                "note": "Используются mock embeddings и ответы на основе контекста"
            }
        )
    
    # Если auth_key не установлен
    if not auth_key:
        message = "❌ GigaChat OAuth ключ не установлен"
        note = "Установите GIGACHAT_AUTH_KEY (Base64 encoded Client ID:Client Secret) в .env для использования реального API"
        
        if using_old_format:
            message = "⚠️ Обнаружен старый формат GIGACHAT_API_KEY"
            note = (
                "Обнаружен старый формат GIGACHAT_API_KEY. "
                "Для OAuth 2.0 аутентификации необходимо использовать GIGACHAT_AUTH_KEY "
                "(Base64 encoded Client ID:Client Secret). "
                "См. docs/gigachat_oauth_setup.md для инструкций."
            )
        
        return ServiceStatus(
            available=False,
            message=message,
            details={
                "auth_key_set": False,
                "old_api_key_set": using_old_format,
                "mock_mode": False,
                "note": note
            }
        )
    
    # Пытаемся проверить доступность API (без реального запроса к API endpoint)
    try:
        # Проверяем только доступность домена (HEAD запрос к корню)
        # Это не стоит токенов и не делает реальный API вызов
        # Отключаем проверку SSL для GigaChat API
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = requests.head(
            "https://gigachat.devices.sberbank.ru",
            timeout=5,
            allow_redirects=True,
            verify=False  # Отключаем проверку SSL
        )
        
        # Если получили ответ (даже 404 или редирект), значит домен доступен
        return ServiceStatus(
            available=True,
            message="✅ GigaChat API доступен (домен доступен, OAuth ключ установлен)",
            details={
                "auth_key_set": True,
                "scope": scope,
                "mock_mode": False,
                "api_url": api_url,
                "embeddings_url": embeddings_url,
                "status_code": response.status_code,
                "note": "Проверена только доступность домена. Реальная работа API будет проверена при первом запросе."
            }
        )
    except requests.exceptions.ConnectionError as e:
        error_str = str(e)
        # Определяем тип ошибки
        if "getaddrinfo failed" in error_str or "NameResolutionError" in error_str:
            error_type = "DNS resolution failed"
            recommendation = "Проверьте интернет-соединение и DNS настройки. При отсутствии интернета используйте mock mode (GIGACHAT_MOCK_MODE=true)."
        elif "Max retries exceeded" in error_str:
            error_type = "Connection timeout"
            recommendation = "Проверьте интернет-соединение. Возможно, api.gigachat.ai недоступен. Используйте mock mode (GIGACHAT_MOCK_MODE=true) для работы без интернета."
        else:
            error_type = "Connection error"
            recommendation = "Проверьте интернет-соединение и доступность api.gigachat.ai. Используйте mock mode (GIGACHAT_MOCK_MODE=true) для работы без интернета."
        
        return ServiceStatus(
            available=False,
            message=f"❌ Не удалось подключиться к GigaChat API: {error_type}",
            details={
                "auth_key_set": True,
                "scope": scope,
                "mock_mode": False,
                "api_url": api_url,
                "embeddings_url": embeddings_url,
                "error": error_str,
                "error_type": error_type,
                "recommendation": recommendation,
                "note": "Система автоматически переключится на mock mode при генерации embeddings и ответов, если API недоступен."
            }
        )
    except requests.exceptions.Timeout as e:
        return ServiceStatus(
            available=False,
            message="❌ Таймаут при подключении к GigaChat API",
            details={
                "auth_key_set": True,
                "scope": scope,
                "mock_mode": False,
                "api_url": api_url,
                "embeddings_url": embeddings_url,
                "error": str(e),
                "error_type": "Timeout",
                "recommendation": "Проверьте интернет-соединение. Используйте mock mode (GIGACHAT_MOCK_MODE=true) для работы без интернета.",
                "note": "Система автоматически переключится на mock mode при генерации embeddings и ответов, если API недоступен."
            }
        )
    except Exception as e:
        return ServiceStatus(
            available=False,
            message=f"⚠️ Ошибка при проверке GigaChat API: {str(e)}",
            details={
                "auth_key_set": True,
                "scope": scope,
                "mock_mode": False,
                "api_url": api_url,
                "embeddings_url": embeddings_url,
                "error": str(e),
                "error_type": "Unknown error",
                "recommendation": "Проверьте настройки сети и доступность gigachat.devices.sberbank.ru. Используйте mock mode (GIGACHAT_MOCK_MODE=true) для работы без интернета.",
                "note": "Система автоматически переключится на mock mode при генерации embeddings и ответов, если API недоступен."
            }
        )

