"""
@file: transcript_indexer.py
@description: Сервис индексации транскриптов в векторное хранилище Qdrant.
@dependencies: backend.services.embedding_service, backend.services.vector_store, uuid
@created: 2025-01-XX
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional
from uuid import UUID

from services.embedding_service import EmbeddingError, EmbeddingService
from services.vector_store.client import VectorStoreClient

logger = logging.getLogger(__name__)


class IndexingError(Exception):
    """Ошибка при индексации транскрипта."""

    pass


class TranscriptIndexer:
    """Сервис индексации транскриптов в векторное хранилище."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStoreClient,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> None:
        """
        Инициализация сервиса индексации.

        Args:
            embedding_service: Сервис генерации эмбеддингов
            vector_store: Клиент векторного хранилища
            chunk_size: Размер чанка в символах
            chunk_overlap: Перекрытие между чанками в символах
        """
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

        # Убеждаемся, что коллекция существует
        self._vector_store.ensure_collection(embedding_service.vector_size)

    def index_transcript(
        self,
        transcript_text: str,
        video_id: UUID,
        transcript_id: UUID,
        segments: Optional[list[dict]] = None,
    ) -> None:
        """
        Индексирует транскрипт в векторное хранилище.

        Args:
            transcript_text: Полный текст транскрипта
            video_id: ID видео
            transcript_id: ID транскрипта
            segments: Список сегментов с таймкодами (опционально)

        Raises:
            IndexingError: При ошибке индексации
        """
        if not transcript_text or not transcript_text.strip():
            raise IndexingError("Transcript text is empty")

        logger.info(
            "Indexing transcript",
            extra={
                "video_id": str(video_id),
                "transcript_id": str(transcript_id),
                "text_length": len(transcript_text),
            },
        )

        try:
            # Разбиваем транскрипт на чанки
            chunks = self._split_into_chunks(transcript_text, segments)

            # Генерируем эмбеддинги для всех чанков
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = self._embedding_service.generate_batch(chunk_texts)

            # Формируем точки для Qdrant
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                point_id = uuid.uuid4()
                points.append(
                    {
                        "id": str(point_id),
                        "vector": embedding,
                        "text": chunk["text"],
                        "metadata": chunk.get("metadata", {}),
                    }
                )

            # Сохраняем в векторное хранилище
            self._vector_store.upsert_transcript_chunks(video_id, transcript_id, points)

            logger.info(
                "Transcript indexed successfully",
                extra={
                    "video_id": str(video_id),
                    "transcript_id": str(transcript_id),
                    "chunks_count": len(points),
                },
            )
        except EmbeddingError as exc:
            logger.error("Embedding error during indexing", extra={"error": str(exc)})
            raise IndexingError(f"Embedding error: {exc}") from exc
        except Exception as exc:
            logger.error("Indexing failed", extra={"error": str(exc)})
            raise IndexingError(f"Indexing failed: {exc}") from exc

    def _split_into_chunks(
        self,
        text: str,
        segments: Optional[list[dict]] = None,
    ) -> list[dict]:
        """
        Разбивает текст на чанки.

        Args:
            text: Текст для разбиения
            segments: Сегменты с таймкодами (если есть)

        Returns:
            Список чанков с метаданными
        """
        if segments:
            # Используем сегменты для более точного разбиения
            chunks = []
            current_chunk = []
            current_length = 0

            for segment in segments:
                segment_text = segment.get("text", "").strip()
                if not segment_text:
                    continue

                segment_length = len(segment_text)
                start_time = segment.get("start", 0.0)
                end_time = segment.get("end", 0.0)

                # Если текущий чанк + новый сегмент превышает размер, сохраняем чанк
                if current_length + segment_length > self._chunk_size and current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append(
                        {
                            "text": chunk_text,
                            "metadata": {
                                "start_time": current_chunk[0].get("start_time", 0.0),
                                "end_time": current_chunk[-1].get("end_time", 0.0),
                                "timestamp": self._format_timestamp(current_chunk[0].get("start_time", 0.0)),
                            },
                        }
                    )
                    # Начинаем новый чанк с перекрытием
                    overlap_size = min(self._chunk_overlap, len(current_chunk))
                    current_chunk = current_chunk[-overlap_size:] if overlap_size > 0 else []
                    current_length = sum(len(c.get("text", "")) for c in current_chunk)

                current_chunk.append(
                    {
                        "text": segment_text,
                        "start_time": start_time,
                        "end_time": end_time,
                    }
                )
                current_length += segment_length

            # Добавляем последний чанк
            if current_chunk:
                chunk_text = " ".join(c["text"] for c in current_chunk)
                chunks.append(
                    {
                        "text": chunk_text,
                        "metadata": {
                            "start_time": current_chunk[0].get("start_time", 0.0),
                            "end_time": current_chunk[-1].get("end_time", 0.0),
                            "timestamp": self._format_timestamp(current_chunk[0].get("start_time", 0.0)),
                        },
                    }
                )

            return chunks
        else:
            # Простое разбиение по символам
            chunks = []
            start = 0

            while start < len(text):
                end = min(start + self._chunk_size, len(text))

                # Пытаемся разбить по предложению
                if end < len(text):
                    # Ищем последнюю точку, восклицательный или вопросительный знак
                    for i in range(end, max(start, end - 100), -1):
                        if text[i] in ".!?\n":
                            end = i + 1
                            break

                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append(
                        {
                            "text": chunk_text,
                            "metadata": {},
                        }
                    )

                # Перекрытие
                start = max(start + 1, end - self._chunk_overlap)

            return chunks

    def _format_timestamp(self, seconds: float) -> str:
        """Форматирует секунды в формат HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

