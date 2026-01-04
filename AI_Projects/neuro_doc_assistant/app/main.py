"""
FastAPI entrypoint для Neuro_Doc_Assistant
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Загружаем переменные окружения из .env файла
load_dotenv()

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

# Опциональный импорт адаптеров для RAGAS
try:
    from app.evaluation.ragas_adapters import GigaChatLLMAdapter, GigaChatEmbeddingsAdapter
    RAGAS_ADAPTERS_AVAILABLE = True
except ImportError:
    RAGAS_ADAPTERS_AVAILABLE = False
    GigaChatLLMAdapter = None
    GigaChatEmbeddingsAdapter = None
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
    
    # Инициализация RAGAS evaluator с реальным RAGAS
    # Определяем, использовать ли реальный RAGAS или mock mode
    use_ragas_mock = os.getenv("RAGAS_MOCK_MODE", "false").lower() == "true"
    
    # Проверяем доступность адаптеров (требуют langchain-core)
    if use_ragas_mock or not RAGAS_ADAPTERS_AVAILABLE:
        if not RAGAS_ADAPTERS_AVAILABLE:
            print("⚠️  LangChain не установлен. RAGAS будет работать в mock mode.")
            print("   Для использования реального RAGAS установите: pip install langchain-core langchain-community")
        ragas_evaluator = RAGASEvaluator(mock_mode=True)
    else:
        try:
            # Создаём адаптеры для RAGAS
            llm_adapter = GigaChatLLMAdapter(llm_client=llm_client)
            embeddings_adapter = GigaChatEmbeddingsAdapter(embedding_service=embedding_service)
            
            # Инициализируем RAGAS evaluator с реальными адаптерами
            ragas_evaluator = RAGASEvaluator(
                mock_mode=False,
                llm_adapter=llm_adapter,
                embeddings_adapter=embeddings_adapter
            )
        except Exception as e:
            print(f"⚠️  Ошибка при инициализации RAGAS адаптеров: {e}")
            print("   RAGAS будет работать в mock mode.")
            ragas_evaluator = RAGASEvaluator(mock_mode=True)
    
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
    # Получаем порт из переменной окружения
    # Приоритет: системная переменная окружения > .env файл > значение по умолчанию
    # Сначала проверяем системную переменную (установленную в batch файле)
    port_str = os.environ.get("API_PORT")  # os.environ.get() проверяет только системные переменные
    if not port_str:
        # Если системной переменной нет, проверяем .env (уже загружен через load_dotenv())
        port_str = os.getenv("API_PORT")
    
    if port_str:
        try:
            port = int(port_str)
            source = "системной переменной окружения" if "API_PORT" in os.environ else ".env файла"
            print(f"ℹ️  Используется порт {port} из {source} (API_PORT={port_str})")
        except ValueError:
            print(f"⚠️  Неверное значение API_PORT: {port_str}. Используется порт 8000 по умолчанию.")
            port = 8000
    else:
        port = 8000
        print(f"ℹ️  Используется порт по умолчанию: {port} (API_PORT не установлен)")
    
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

