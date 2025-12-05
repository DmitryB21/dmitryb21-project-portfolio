"""
@file: backend/repositories/processing_job_repository.py
@description: Репозиторий для мониторинга фоновых задач.
@dependencies: sqlalchemy.orm, backend.database.models
@created: 2025-11-12
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from backend.database import models
from backend.repositories.base import Repository


class ProcessingJobRepository(Repository[models.ProcessingJob]):
    """Операции с журналом задач."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def mark_status(self, job_id: UUID, status: str, error: Optional[str] = None) -> None:
        self._session.query(models.ProcessingJob).filter(models.ProcessingJob.id == job_id).update(
            {"status": status, "error": error}
        )

    def list_pending(self, limit: int = 100) -> list[models.ProcessingJob]:
        return (
            self._session.query(models.ProcessingJob)
            .filter(models.ProcessingJob.status == "pending")
            .order_by(models.ProcessingJob.created_at.asc())
            .limit(limit)
            .all()
        )

