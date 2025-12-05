"""
@file: backend/database/session.py
@description: Конфигурация SQLAlchemy engine и сессий.
@dependencies: sqlalchemy, backend.config
@created: 2025-11-12
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import Settings, get_settings
from database.base import Base


def _create_engine(settings: Settings):
    """Создает экземпляр SQLAlchemy engine."""
    return create_engine(
        settings.database_url,
        echo=settings.environment == "development",
        future=True,
    )


def get_session_factory() -> sessionmaker[Session]:
    """Возвращает sessionmaker с ленивой инициализацией."""
    settings = get_settings()
    engine = _create_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_database() -> None:
    """Создает таблицы при необходимости (для локальной разработки)."""
    settings = get_settings()
    engine = _create_engine(settings)
    Base.metadata.create_all(engine)


def get_db_session(factory: Callable[[], sessionmaker[Session]] | None = None) -> Generator[Session, None, None]:
    """Зависимость FastAPI для получения сессии."""
    session_factory = factory or get_session_factory()
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

