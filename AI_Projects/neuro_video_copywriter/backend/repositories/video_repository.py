"""
@file: backend/repositories/video_repository.py
@description: Операции с сущностью Video в PostgreSQL.
@dependencies: sqlalchemy.orm, backend.database.models
@created: 2025-11-12
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from database import models
from repositories.base import Repository


class VideoRepository(Repository[models.Video]):
    """Репозиторий видеоматериалов."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def find_by_url(self, url: str) -> Optional[models.Video]:
        return self._session.query(models.Video).filter(models.Video.source_url == url).one_or_none()

    def list(self, limit: int = 50) -> list[models.Video]:
        return (
            self._session.query(models.Video)
            .order_by(models.Video.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_by_id(self, video_id: UUID) -> Optional[models.Video]:
        return self._session.get(models.Video, video_id)

    def update_status(self, video_id: UUID, status: str) -> None:
        self._session.query(models.Video).filter(models.Video.id == video_id).update({"status": status})

    def upsert_downloaded_video(
        self,
        *,
        source_url: str,
        provider: str,
        audio_path: str,
        title: Optional[str] = None,
        status: str = "downloaded",
    ) -> models.Video:
        video = self.find_by_url(source_url)
        if video is None:
            video = models.Video(
                source_url=source_url,
                provider=provider,
                title=title,
                status=status,
                audio_path=audio_path,
            )
            self.add(video)
        else:
            video.provider = provider
            video.status = status
            video.audio_path = audio_path
            if title:
                video.title = title

        self._session.flush()
        return video

