"""
@file: backend/repositories/summary_repository.py
@description: Репозиторий методичек (summaries).
@dependencies: sqlalchemy.orm, backend.database.models
@created: 2025-11-12
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from database import models
from repositories.base import Repository


class SummaryRepository(Repository[models.Summary]):
    """Операции с методичками."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_by_video(self, video_id: UUID) -> Optional[models.Summary]:
        return (
            self._session.query(models.Summary)
            .filter(models.Summary.video_id == video_id)
            .order_by(models.Summary.created_at.desc())
            .first()
        )

    def upsert_for_video(
        self,
        video_id: UUID,
        *,
        title: str,
        data: dict,
    ) -> models.Summary:
        summary = models.Summary(
            video_id=video_id,
            title=title,
            data=data,
        )
        self.add(summary)
        self._session.flush()
        return summary

    def delete_by_video(self, video_id: UUID) -> None:
        self._session.query(models.Summary).filter(models.Summary.video_id == video_id).delete(synchronize_session=False)

