"""
@file: backend/services/providers/base.py
@description: Базовые интерфейсы и структуры данных для адаптеров загрузки видео.
@dependencies: typing, pathlib
@created: 2025-11-12
"""

from __future__ import annotations

import abc
import dataclasses
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXECUTABLE = "yt-dlp"


@dataclasses.dataclass(frozen=True, slots=True)
class DownloadResult:
    """Результат загрузки видео/аудио."""

    video_path: Path
    metadata: Mapping[str, Any]


class ProviderError(Exception):
    """Базовое исключение адаптеров провайдеров."""


class BaseProviderAdapter(abc.ABC):
    """Абстрактный адаптер для загрузки медиаконтента из внешних источников."""

    name: str

    def __init__(self, executable: str = DEFAULT_EXECUTABLE) -> None:
        self._executable = executable or DEFAULT_EXECUTABLE

    @abc.abstractmethod
    def supports(self, url: str) -> bool:
        """Проверяет, может ли адаптер обработать указанный URL."""

    @abc.abstractmethod
    def download(self, url: str, destination: Path) -> DownloadResult:
        """Выполняет загрузку видео и возвращает путь к файлу и метаданные."""

    def sanitize_url(self, url: str) -> str:
        """Расширяемый хук для нормализации URL перед загрузкой."""
        cleaned = url.strip()
        if cleaned.startswith("@"):
            cleaned = cleaned.lstrip("@")
        return cleaned

    @property
    def executable(self) -> str:
        """Возвращает путь к исполняемому файлу yt-dlp."""
        return self._executable

