"""
@file: backend/repositories/base.py
@description: Базовые классы и утилиты репозиториев PostgreSQL.
@dependencies: sqlalchemy.orm
@created: 2025-11-12
"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class Repository(Generic[ModelT]):
    """Базовый репозиторий поверх SQLAlchemy сессии."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, instance: ModelT) -> ModelT:
        self._session.add(instance)
        return instance

    def delete(self, instance: ModelT) -> None:
        self._session.delete(instance)

    def get(self, model: type[ModelT], obj_id) -> Optional[ModelT]:
        return self._session.get(model, obj_id)

