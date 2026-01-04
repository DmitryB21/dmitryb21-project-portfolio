"""
@file: ragas_adapters.py
@description: LangChain-совместимые адаптеры для GigaChat LLM и Embeddings для использования с RAGAS
@dependencies: langchain-core, langchain-community (опционально)
@created: 2024-12-22
"""

from typing import List, Optional, Any
from pydantic import Field, PrivateAttr

# Опциональный импорт LangChain
try:
    from langchain_core.language_models.llms import LLM
    from langchain_core.embeddings import Embeddings
    from langchain_core.callbacks.manager import CallbackManagerForLLMRun
    from langchain_core.outputs import LLMResult
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    # Создаём заглушки для типов
    LLM = object
    Embeddings = object
    CallbackManagerForLLMRun = Optional
    LLMResult = object

from app.generation.gigachat_client import LLMClient
from app.ingestion.embedding_service import EmbeddingService


if LANGCHAIN_AVAILABLE:
    class GigaChatLLMAdapter(LLM):
        """
        LangChain-совместимая обёртка для GigaChat LLMClient.
        Используется RAGAS для оценки метрик.
        """
        
        # Используем PrivateAttr для полей, которые не должны быть частью модели Pydantic
        _llm_client: LLMClient = PrivateAttr()
        
        def __init__(
            self,
            llm_client: LLMClient,
            **kwargs
        ):
            """
            Инициализация адаптера.
            
            Args:
                llm_client: Экземпляр LLMClient для GigaChat API
            """
            super().__init__(**kwargs)
            self._llm_client = llm_client
        
        @property
        def _llm_type(self) -> str:
            """Тип LLM для LangChain."""
            return "gigachat"
        
        def _call(
            self,
            prompt: str,
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
        ) -> str:
            """
            Вызов LLM для генерации ответа.
            
            Args:
                prompt: Промпт для генерации
                stop: Список стоп-слов (не используется в GigaChat)
                run_manager: Callback manager (не используется)
                **kwargs: Дополнительные параметры
                
            Returns:
                Сгенерированный текст
            """
            return self._llm_client.generate_answer(prompt)
        
        @property
        def _identifying_params(self) -> dict:
            """Параметры для идентификации модели."""
            return {
                "model": self._llm_client.model,
                "temperature": self._llm_client.temperature,
                "max_tokens": self._llm_client.max_tokens,
            }


if LANGCHAIN_AVAILABLE:
    class GigaChatEmbeddingsAdapter(Embeddings):
        """
        LangChain-совместимая обёртка для GigaChat EmbeddingService.
        Используется RAGAS для оценки метрик.
        """
        
        # Используем PrivateAttr для полей, которые не должны быть частью модели Pydantic
        _embedding_service: EmbeddingService = PrivateAttr()
        
        def __init__(
            self,
            embedding_service: EmbeddingService,
            **kwargs
        ):
            """
            Инициализация адаптера.
            
            Args:
                embedding_service: Экземпляр EmbeddingService для GigaChat API
            """
            super().__init__(**kwargs)
            self._embedding_service = embedding_service
        
        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            """
            Генерация embeddings для списка документов.
            
            Args:
                texts: Список текстов для генерации embeddings
                
            Returns:
                Список векторов embeddings
            """
            return self._embedding_service.generate_embeddings(texts)
        
        def embed_query(self, text: str) -> List[float]:
            """
            Генерация embedding для одного запроса.
            
            Args:
                text: Текст для генерации embedding
                
            Returns:
                Вектор embedding
            """
            embeddings = self._embedding_service.generate_embeddings([text])
            return embeddings[0] if embeddings else []

