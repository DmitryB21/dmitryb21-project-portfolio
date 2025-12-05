"""
@file: backend/services/providers/__init__.py
@description: Реестр адаптеров провайдеров видео для загрузки медиа.
@dependencies: backend.services.providers.base, backend.services.providers.youtube, backend.services.providers.vk, backend.services.providers.rutube
@created: 2025-11-12
"""

from .base import BaseProviderAdapter, DownloadResult, ProviderError
from .youtube import YouTubeAdapter
from .vk import VkAdapter
from .rutube import RuTubeAdapter

__all__ = [
    "BaseProviderAdapter",
    "ProviderError",
    "DownloadResult",
    "YouTubeAdapter",
    "VkAdapter",
    "RuTubeAdapter",
]

