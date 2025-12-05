"""
@file: backend/services/video_downloader.py
@description: Оркестратор загрузки видео и извлечения аудио с использованием провайдеров и хранилищ.
@dependencies: backend.services.providers, backend.services.storage, logging, dataclasses
@created: 2025-11-12
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Iterable, Mapping, Optional
from uuid import uuid4

from .providers import (
    BaseProviderAdapter,
    DownloadResult,
    ProviderError,
    RuTubeAdapter,
    VkAdapter,
    YouTubeAdapter,
)
from .providers.base import DEFAULT_EXECUTABLE
from .storage import MediaContext, MediaLocation, MediaStorage, StorageError

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class VideoDownloadRequest:
    url: str
    provider_hint: Optional[str] = None
    request_id: Optional[str] = None
    context_metadata: Optional[Mapping[str, str]] = None


@dataclasses.dataclass(slots=True)
class VideoDownloadResponse:
    audio_location: MediaLocation
    provider: str
    metadata: Mapping[str, object]


class VideoDownloadService:
    """Оркестратор, выбирающий подходящий адаптер, выполняющий загрузку и сохраняющий медиа."""

    def __init__(
        self,
        storage: MediaStorage,
        adapters: Optional[Iterable[BaseProviderAdapter]] = None,
        workdir: Optional[Path] = None,
        yt_dlp_executable: str = DEFAULT_EXECUTABLE,
    ) -> None:
        self._storage = storage
        self._workdir = workdir or Path("data/downloads")
        self._workdir.mkdir(parents=True, exist_ok=True)
        self._executable = yt_dlp_executable or DEFAULT_EXECUTABLE
        self._adapters = list(adapters) if adapters else self._default_adapters()

    def _default_adapters(self) -> list[BaseProviderAdapter]:
        return [
            YouTubeAdapter(executable=self._executable),
            VkAdapter(executable=self._executable),
            RuTubeAdapter(executable=self._executable),
        ]

    def handle(self, request: VideoDownloadRequest) -> VideoDownloadResponse:
        logger.info("Handling video download request", extra={"url": request.url})

        normalized_url = self._normalize_url(request.url)
        adapter = self._select_adapter(normalized_url, request.provider_hint)
        download_dir = self._prepare_workdir(adapter)

        try:
            download_result = adapter.download(normalized_url, download_dir)
            context = MediaContext(
                request_id=request.request_id or download_dir.name,
                metadata=request.context_metadata or {},
                checksum=None,
            )
            location = self._storage.save(download_result.video_path, context)
        except ProviderError as exc:
            logger.error(
                "Provider failed to download content",
                extra={"url": request.url, "provider": adapter.name},
            )
            raise
        except StorageError as exc:
            logger.error(
                "Failed to persist downloaded media",
                extra={"url": request.url, "provider": adapter.name},
            )
            raise
        finally:
            self._cleanup_path(download_dir)

        merged_metadata = dict(download_result.metadata)
        merged_metadata.update(request.context_metadata or {})

        return VideoDownloadResponse(
            audio_location=location,
            provider=adapter.name,
            metadata=merged_metadata,
        )

    def _select_adapter(self, url: str, provider_hint: Optional[str]) -> BaseProviderAdapter:
        if provider_hint:
            for adapter in self._adapters:
                if adapter.name == provider_hint:
                    return adapter
            raise ProviderError(f"No adapter for hint '{provider_hint}'")

        for adapter in self._adapters:
            if adapter.supports(url):
                return adapter

        raise ProviderError("No provider adapter supports given URL")

    def _normalize_url(self, url: str) -> str:
        if not url:
            return url
        cleaned = url.strip()
        if cleaned.startswith("@"):
            cleaned = cleaned.lstrip("@")
        return cleaned

    def _prepare_workdir(self, adapter: BaseProviderAdapter) -> Path:
        target_dir = self._workdir / adapter.name / uuid4().hex
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def _cleanup_path(self, path: Path) -> None:
        for child in path.glob("*"):
            try:
                child.unlink()
            except OSError:
                logger.warning("Cannot remove working file", extra={"file": str(child)})

        try:
            path.rmdir()
        except OSError:
            logger.debug("Working directory is not empty", extra={"dir": str(path)})

