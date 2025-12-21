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
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_client = QdrantClient(url=qdrant_url)
    
    # Инициализация EmbeddingService
    embedding_service = EmbeddingService(
        api_key=os.getenv("GIGACHAT_API_KEY"),
        model_version=os.getenv("EMBEDDING_MODEL_VERSION", "GigaChat"),
        embedding_dim=int(os.getenv("EMBEDDING_DIM", "1536"))
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
    
    # GigaChat API настройки
    gigachat_api_key = os.getenv("GIGACHAT_API_KEY")
    
    llm_client = LLMClient(
        api_key=gigachat_api_key,
        mock_mode=os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true"
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
    import uvicorn
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    # Создаём приложение для запуска
    app = create_app()
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=os.getenv("API_RELOAD", "false").lower() == "true"
    )

