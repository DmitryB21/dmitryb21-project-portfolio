"""
@file: backend/services/storage/__init__.py
@description: Пакет стратегий хранения медиаданных.
@dependencies: backend.services.storage.base, backend.services.storage.local
@created: 2025-11-12
"""

from .base import MediaContext, MediaLocation, MediaStorage, StorageError
from .local import LocalFileStorage

__all__ = [
    "MediaContext",
    "MediaLocation",
    "MediaStorage",
    "StorageError",
    "LocalFileStorage",
]

