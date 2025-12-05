"""
@file: consultant_agent.py
@description: RAG-пайплайн для чат-консультанта с контекстом лекции.
@dependencies: openai, backend.services.embedding_service, backend.services.vector_store
@created: 2025-01-XX
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

from services.embedding_service import EmbeddingError, EmbeddingService
from services.vector_store.client import VectorStoreClient

logger = logging.getLogger(__name__)


class ConsultantError(Exception):
    """Ошибка при работе консультанта."""

    pass


class ConsultantAgent:
    """RAG-пайплайн для ответов на вопросы по содержанию лекции."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStoreClient,
        llm_api_key: str,
        llm_model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ) -> None:
        """
        Инициализация консультанта.

        Args:
            embedding_service: Сервис генерации эмбеддингов
            vector_store: Клиент векторного хранилища
            llm_api_key: API ключ OpenAI для LLM
            llm_model: Модель LLM для генерации ответов
            base_url: Базовый URL API (опционально)
        """
        if OpenAI is None:
            raise ConsultantError(
                "OpenAI library is not installed. Install it with: pip install openai"
            )

        if not llm_api_key:
            raise ConsultantError("LLM API key is required")

        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._llm_client = OpenAI(api_key=llm_api_key, base_url=base_url)
        self._llm_model = llm_model

        # Убеждаемся, что коллекция существует
        self._vector_store.ensure_collection(embedding_service.vector_size)

    def answer(
        self,
        question: str,
        video_id: Optional[str] = None,
        top_k: int = 5,
        language: str = "ru",
    ) -> tuple[str, list[dict]]:
        """
        Отвечает на вопрос на основе контекста из векторного хранилища.

        Args:
            question: Вопрос пользователя
            video_id: ID видео для фильтрации (опционально)
            top_k: Количество релевантных фрагментов для извлечения
            language: Язык ответа

        Returns:
            Кортеж (ответ, источники): ответ на вопрос и список источников

        Raises:
            ConsultantError: При ошибке генерации ответа
        """
        if not question or not question.strip():
            raise ConsultantError("Question is empty")

        logger.info(
            "Processing question",
            extra={"question_length": len(question), "video_id": video_id, "top_k": top_k},
        )

        try:
            # 1. Генерируем эмбеддинг для вопроса
            query_embedding = self._embedding_service.generate(question)

            # 2. Ищем релевантные фрагменты в векторном хранилище
            search_results = self._vector_store.search(query_embedding, top_k=top_k)

            if not search_results:
                logger.warning("No relevant context found", extra={"question": question})
                return (self._get_no_context_response(language), [])

            # 3. Фильтруем результаты по video_id если указан
            filtered_results = search_results
            if video_id:
                filtered_results = [
                    r for r in search_results
                    if r.get("payload", {}).get("video_id") == video_id
                ]

            if not filtered_results:
                logger.warning("No relevant context found for video", extra={"question": question, "video_id": video_id})
                return (self._get_no_context_response(language), [])

            # 4. Формируем контекст из найденных фрагментов
            context = self._build_context(filtered_results, video_id)

            # 5. Генерируем ответ через LLM с контекстом
            answer = self._generate_answer(question, context, language)

            # 6. Формируем источники
            sources = self._format_sources(filtered_results)

            logger.info("Answer generated", extra={"answer_length": len(answer), "sources_count": len(sources)})

            return (answer, sources)
        except EmbeddingError as exc:
            logger.error("Embedding error", extra={"error": str(exc)})
            raise ConsultantError(f"Embedding error: {exc}") from exc
        except Exception as exc:
            logger.error("Consultant error", extra={"error": str(exc), "question": question})
            raise ConsultantError(f"Failed to generate answer: {exc}") from exc

    def _build_context(self, search_results: list[dict], video_id: Optional[str]) -> str:
        """Строит контекст из результатов поиска."""
        context_parts = []
        for i, result in enumerate(search_results, 1):
            payload = result.get("payload", {})
            text = payload.get("text", "")
            metadata = payload.get("metadata", {})
            timestamp = metadata.get("timestamp") or metadata.get("start_time")

            if video_id and payload.get("video_id") != video_id:
                continue

            part = f"[Фрагмент {i}]"
            if timestamp:
                part += f" (время: {timestamp})"
            part += f": {text}"
            context_parts.append(part)

        return "\n\n".join(context_parts)

    def _generate_answer(self, question: str, context: str, language: str) -> str:
        """Генерирует ответ через LLM с использованием контекста."""
        if language == "ru":
            system_prompt = """Ты - помощник-консультант, который отвечает на вопросы по содержанию лекции или видео.
Используй предоставленный контекст для формирования точного и полезного ответа.
Если в контексте нет информации для ответа, честно скажи об этом.
Отвечай на русском языке, будь кратким и по делу."""
            user_prompt = f"""Контекст из лекции:

{context}

Вопрос: {question}

Ответь на вопрос, используя информацию из контекста."""
        else:
            system_prompt = """You are a consultant assistant that answers questions about lecture or video content.
Use the provided context to form an accurate and helpful answer.
If the context doesn't contain information to answer, say so honestly.
Answer in English, be concise and to the point."""
            user_prompt = f"""Context from the lecture:

{context}

Question: {question}

Answer the question using information from the context."""

        try:
            response = self._llm_client.chat.completions.create(
                model=self._llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )

            answer = response.choices[0].message.content
            if not answer:
                raise ConsultantError("Empty response from LLM")

            return answer.strip()
        except Exception as exc:
            logger.error("LLM generation failed", extra={"error": str(exc)})
            raise ConsultantError(f"LLM generation failed: {exc}") from exc

    def _get_no_context_response(self, language: str) -> str:
        """Возвращает ответ, когда контекст не найден."""
        if language == "ru":
            return "К сожалению, я не нашел релевантной информации в базе знаний для ответа на ваш вопрос. Попробуйте переформулировать вопрос или убедитесь, что транскрипт лекции был обработан и проиндексирован."
        else:
            return "Unfortunately, I couldn't find relevant information in the knowledge base to answer your question. Try rephrasing the question or make sure the lecture transcript has been processed and indexed."

    def _format_sources(self, search_results: list[dict]) -> list[dict]:
        """Форматирует источники для ответа."""
        sources = []
        for result in search_results:
            payload = result.get("payload", {})
            metadata = payload.get("metadata", {})
            source = {
                "text": payload.get("text", ""),
                "score": result.get("score", 0.0),
                "video_id": payload.get("video_id"),
                "transcript_id": payload.get("transcript_id"),
                "timestamp": metadata.get("timestamp") or metadata.get("start_time"),
            }
            sources.append(source)
        return sources

