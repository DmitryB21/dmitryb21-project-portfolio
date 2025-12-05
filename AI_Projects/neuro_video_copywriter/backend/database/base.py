"""
@file: backend/database/base.py
@description: Базовые декларативные модели SQLAlchemy.
@dependencies: sqlalchemy.orm
@created: 2025-11-12
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""

    pass

