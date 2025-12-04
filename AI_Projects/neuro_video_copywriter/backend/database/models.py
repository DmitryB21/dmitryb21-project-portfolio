"""
@file: backend/database/models.py
@description: ORM-модели PostgreSQL для хранения видео, транскриптов и методичек.
@dependencies: sqlalchemy, datetime, uuid
@created: 2025-11-12
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class Video(Base):
    """Основная сущность видеоматериала."""

    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    audio_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False
    )

    transcripts: Mapped[list["Transcript"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    summaries: Mapped[list["Summary"]] = relationship(back_populates="video", cascade="all, delete-orphan")


class Transcript(Base):
    """Транскрипты аудио дорожек."""

    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="ru")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow, nullable=False)

    video: Mapped[Video] = relationship(back_populates="transcripts")


class Summary(Base):
    """Методички/резюме по лекциям."""

    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow, nullable=False)

    video: Mapped[Video] = relationship(back_populates="summaries")


class ProcessingJob(Base):
    """Журнал выполнения фоновых задач."""

    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False
    )

    video: Mapped[Optional[Video]] = relationship()

