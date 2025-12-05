"""
@file: backend/repositories/transcript_repository.py
@description: Репозиторий транскриптов и взаимодействие с Qdrant.
@dependencies: sqlalchemy.orm, backend.database.models, backend.services.vector_store
@created: 2025-11-12
"""

from __future__ import annotations

from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from database import models
from repositories.base import Repository
from services.vector_store.client import VectorStoreClient


class TranscriptRepository(Repository[models.Transcript]):
    """Репозиторий транскриптов с интеграцией Qdrant."""

    def __init__(self, session: Session, vector_client: VectorStoreClient) -> None:
        super().__init__(session)
        self._vector_client = vector_client

    def create(
        self,
        video_id: UUID,
        *,
        language: str,
        content: str,
        extra: dict,
    ) -> models.Transcript:
        transcript = models.Transcript(
            video_id=video_id,
            language=language,
            content=content,
            extra=extra,
        )
        self.add(transcript)
        self._session.flush()
        return transcript

    def list_by_video(self, video_id: UUID) -> list[models.Transcript]:
        return (
            self._session.query(models.Transcript)
            .filter(models.Transcript.video_id == video_id)
            .order_by(models.Transcript.created_at.asc())
            .all()
        )

    def get_latest_by_video(self, video_id: UUID) -> Optional[models.Transcript]:
        return (
            self._session.query(models.Transcript)
            .filter(models.Transcript.video_id == video_id)
            .order_by(models.Transcript.created_at.desc())
            .first()
        )

    def add_with_embeddings(self, transcript: models.Transcript, chunks: Iterable[dict]) -> models.Transcript:
        """Сохраняет транскрипт и соответствующие эмбеддинги в Qdrant."""
        self.add(transcript)
        self._vector_client.upsert_transcript_chunks(
            video_id=transcript.video_id,
            transcript_id=transcript.id,
            chunks=chunks,
        )
        return transcript

    def delete_by_video(self, video_id: UUID) -> None:
        """Удаляет транскрипт и эмбеддинги."""
        transcripts = self.list_by_video(video_id)
        for transcript in transcripts:
            self._session.delete(transcript)
            self._vector_client.delete_transcript_chunks(transcript_id=transcript.id)

