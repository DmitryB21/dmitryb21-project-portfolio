"""
@file: embedding_service.py
@description: Сервис генерации эмбеддингов для текста с использованием OpenAI API.
@dependencies: openai, logging
@created: 2025-01-XX
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Ошибка при генерации эмбеддингов."""

    pass


class EmbeddingService:
    """Сервис генерации эмбеддингов для текста."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
    ) -> None:
        """
        Инициализация сервиса генерации эмбеддингов.

        Args:
            api_key: API ключ OpenAI
            model: Модель для генерации эмбеддингов (text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002)
            base_url: Базовый URL API (опционально)
        """
        if OpenAI is None:
            raise EmbeddingError(
                "OpenAI library is not installed. Install it with: pip install openai"
            )

        if not api_key:
            raise EmbeddingError("OpenAI API key is required")

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._vector_size = self._get_vector_size(model)

    def _get_vector_size(self, model: str) -> int:
        """Возвращает размерность вектора для модели."""
        sizes = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return sizes.get(model, 1536)

    @property
    def vector_size(self) -> int:
        """Размерность вектора эмбеддинга."""
        return self._vector_size

    def generate(self, text: str) -> list[float]:
        """
        Генерирует эмбеддинг для текста.

        Args:
            text: Текст для векторизации

        Returns:
            Список чисел (вектор эмбеддинга)

        Raises:
            EmbeddingError: При ошибке генерации
        """
        if not text or not text.strip():
            raise EmbeddingError("Text is empty")

        logger.debug("Generating embedding", extra={"text_length": len(text), "model": self._model})

        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=text,
            )

            embedding = response.data[0].embedding
            logger.debug("Embedding generated", extra={"vector_size": len(embedding)})

            return embedding
        except Exception as exc:
            logger.error("Embedding generation failed", extra={"error": str(exc), "text_length": len(text)})
            raise EmbeddingError(f"Embedding generation failed: {exc}") from exc

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Генерирует эмбеддинги для списка текстов.

        Args:
            texts: Список текстов для векторизации

        Returns:
            Список векторов эмбеддингов

        Raises:
            EmbeddingError: При ошибке генерации
        """
        if not texts:
            return []

        logger.debug("Generating batch embeddings", extra={"batch_size": len(texts), "model": self._model})

        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=texts,
            )

            embeddings = [item.embedding for item in response.data]
            logger.debug("Batch embeddings generated", extra={"count": len(embeddings)})

            return embeddings
        except Exception as exc:
            logger.error("Batch embedding generation failed", extra={"error": str(exc), "batch_size": len(texts)})
            raise EmbeddingError(f"Batch embedding generation failed: {exc}") from exc

