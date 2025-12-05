"""
@file: backend/services/providers/vk.py
@description: Адаптер загрузки медиаконтента из VK видео.
@dependencies: backend.services.providers.base, logging, pathlib
@created: 2025-11-12
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from .base import BaseProviderAdapter, DownloadResult, ProviderError

logger = logging.getLogger(__name__)


class VkAdapter(BaseProviderAdapter):
    """Адаптер загрузки видео с платформы VK."""

    name = "vk"

    def supports(self, url: str) -> bool:
        normalized = url.strip().lstrip("@").lower()
        return any(domain in normalized for domain in ("vk.com", "vkvideo.ru"))

    def download(self, url: str, destination: Path) -> DownloadResult:
        sanitized_url = self.sanitize_url(url)
        logger.info("Starting VK download", extra={"url": sanitized_url})

        temp_dir = Path(tempfile.mkdtemp(prefix="vk-yt-dlp-", dir=str(destination)))
        output_template = temp_dir / "%(id)s.%(ext)s"
        command = [
            self.executable,
            "--format",
            "bestaudio/best",
            "--no-playlist",
            "--newline",
            "--output",
            str(output_template),
            sanitized_url,
        ]

        try:
            self._run_command(command)
            downloaded_files = list(temp_dir.glob("*"))
            if not downloaded_files:
                raise ProviderError("yt-dlp did not produce any files for VK source")

            video_file = downloaded_files[0]
            target_path = destination / f"{uuid4().hex}{video_file.suffix}"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            video_file.replace(target_path)

            metadata = self._fetch_metadata(sanitized_url)
            return DownloadResult(video_path=target_path, metadata=metadata)
        finally:
            self._cleanup_temp_dir(temp_dir)

    def _run_command(self, command: list[str]) -> None:
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=False,
            )
        except FileNotFoundError as exc:
            raise ProviderError(
                f"Executable {self.executable} not found. Install yt-dlp."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise ProviderError(f"yt-dlp failed with code {exc.returncode}") from exc

    def _fetch_metadata(self, url: str) -> dict:
        command = [
            self.executable,
            "--dump-json",
            "--no-warnings",
            "--no-playlist",
            url,
        ]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.warning("Failed to fetch metadata via yt-dlp for VK", extra={"url": url})
            raise ProviderError("Cannot fetch metadata for VK source") from exc

        import json

        raw_data = json.loads(result.stdout)
        return {
            "title": raw_data.get("title"),
            "uploader": raw_data.get("uploader"),
            "duration": raw_data.get("duration"),
        }

    def _cleanup_temp_dir(self, temp_dir: Path) -> None:
        for file_path in temp_dir.glob("*"):
            try:
                file_path.unlink()
            except OSError:
                logger.warning("Cannot remove temporary file", extra={"file": str(file_path)})
        try:
            temp_dir.rmdir()
        except OSError:
            logger.warning("Cannot remove temporary directory", extra={"dir": str(temp_dir)})

