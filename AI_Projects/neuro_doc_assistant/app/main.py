"""
FastAPI entrypoint для Neuro_Doc_Assistant
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import create_app as create_chat_app
from app.api.admin import create_admin_router
from app.agent.agent import AgentController
from app.retrieval.retriever import Retriever
from app.retrieval.metadata_filter import MetadataFilter
from app.reranking.reranker import Reranker
from app.generation.prompt_builder import PromptBuilder
from app.generation.gigachat_client import LLMClient
from app.evaluation.metrics import MetricsCollector
from app.evaluation.ragas_evaluator import RAGASEvaluator
from app.ingestion.embedding_service import EmbeddingService
from qdrant_client import QdrantClient


def create_agent_controller() -> AgentController:
    """
    Создание и инициализация AgentController с реальными зависимостями
    
    Returns:
        Инициализированный AgentController
    """
    # Инициализация Qdrant клиента
    # Поддерживаем оба варианта: QDRANT_URL или QDRANT_HOST + QDRANT_PORT
    qdrant_url = os.getenv("QDRANT_URL")
    if not qdrant_url:
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
    
    qdrant_client = QdrantClient(url=qdrant_url)
    
    # Инициализация EmbeddingService
    # Используем GIGACHAT_AUTH_KEY для OAuth 2.0 аутентификации
    # Поддержка обратной совместимости: если GIGACHAT_AUTH_KEY не установлен, используем GIGACHAT_API_KEY
    gigachat_auth_key = os.getenv("GIGACHAT_AUTH_KEY")
    if not gigachat_auth_key:
        # Обратная совместимость: используем старый формат, если новый не установлен
        old_api_key = os.getenv("GIGACHAT_API_KEY")
        if old_api_key:
            gigachat_auth_key = old_api_key
            print("Warning: Используется старый формат GIGACHAT_API_KEY. Рекомендуется переименовать в GIGACHAT_AUTH_KEY.")
    
    gigachat_scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    use_mock_mode = not gigachat_auth_key or os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true"
    
    embedding_service = EmbeddingService(
        model_version=os.getenv("EMBEDDING_MODEL_VERSION", "GigaChat"),
        embedding_dim=int(os.getenv("EMBEDDING_DIM", "1536")),
        auth_key=gigachat_auth_key,
        scope=gigachat_scope,
        mock_mode=use_mock_mode
    )
    
    # Инициализация компонентов
    retriever = Retriever(
        qdrant_client=qdrant_client,
        embedding_service=embedding_service,
        collection_name=os.getenv("QDRANT_COLLECTION", "neuro_docs")
    )
    metadata_filter = MetadataFilter()
    reranker = Reranker()  # Опциональный модуль для улучшения Precision@3
    prompt_builder = PromptBuilder()
    
    # GigaChat API настройки для LLMClient
    # Используем те же настройки, что и для EmbeddingService
    llm_client = LLMClient(
        auth_key=gigachat_auth_key,
        scope=gigachat_scope,
        mock_mode=use_mock_mode
    )
    
    metrics_collector = MetricsCollector()
    ragas_evaluator = RAGASEvaluator(mock_mode=True)  # В production можно переключить на реальный RAGAS
    
    # Инициализация Prometheus метрик (опционально, если prometheus-client установлен)
    try:
        from app.monitoring.prometheus_metrics import PrometheusMetrics
        prometheus_metrics = PrometheusMetrics()
    except (ImportError, Exception) as e:
        prometheus_metrics = None
        print(f"Warning: Prometheus metrics will be disabled. Reason: {e}")
    
    # Создание AgentController
    controller = AgentController(
        retriever=retriever,
        metadata_filter=metadata_filter,
        prompt_builder=prompt_builder,
        llm_client=llm_client,
        metrics_collector=metrics_collector,
        ragas_evaluator=ragas_evaluator,
        reranker=reranker,
        prometheus_metrics=prometheus_metrics
    )
    
    return controller, prometheus_metrics


def create_app() -> FastAPI:
    """
    Создание FastAPI приложения с полной интеграцией
    
    Returns:
        FastAPI приложение
    """
    # Создаём AgentController и PrometheusMetrics
    agent_controller, prometheus_metrics = create_agent_controller()
    
    # Создаём основное приложение с QueryAPI
    app = create_chat_app(agent_controller=agent_controller)
    
    # Добавляем AdminAPI с Prometheus endpoint
    admin_router = create_admin_router(
        agent_controller=agent_controller,
        prometheus_metrics=prometheus_metrics
    )
    app.include_router(admin_router, prefix="/admin", tags=["admin"])
    
    # Настройка CORS (для Streamlit UI)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # В production указать конкретные домены
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


if __name__ == "__main__":
    import sys
    import uvicorn
    
    # Добавляем текущую директорию в PYTHONPATH, если её там нет
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    # Создаём приложение для запуска
    app = create_app()
    
    # Настройка логирования uvicorn для более детального вывода ошибок
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=os.getenv("API_RELOAD", "false").lower() == "true",
        log_level="info"  # Можно изменить на "debug" для более детальных логов
    )

