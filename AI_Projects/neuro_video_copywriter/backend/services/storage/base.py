"""
@file: backend/services/storage/base.py
@description: Интерфейсы и структуры данных для хранения медиаконтента.
@dependencies: dataclasses, pathlib, typing
@created: 2025-11-12
"""

from __future__ import annotations

import abc
import dataclasses
from pathlib import Path
from typing import Mapping, Optional


@dataclasses.dataclass(frozen=True, slots=True)
class MediaContext:
    """Контекст сохранения медиафайла."""

    request_id: str
    checksum: Optional[str] = None
    metadata: Mapping[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, slots=True)
class MediaLocation:
    """Расположение сохранённого медиафайла."""

    uri: str
    path: Path


class StorageError(Exception):
    """Базовое исключение хранилища медиа."""


class MediaStorage(abc.ABC):
    """Абстрактный интерфейс для стратегий хранения медиа."""

    @abc.abstractmethod
    def save(self, file_path: Path, context: MediaContext) -> MediaLocation:
        """Сохраняет файл и возвращает место хранения."""

    @abc.abstractmethod
    def delete(self, location: MediaLocation) -> None:
        """Удаляет ранее сохранённый файл."""

