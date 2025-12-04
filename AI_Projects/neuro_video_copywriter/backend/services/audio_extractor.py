"""
@file: audio_extractor.py
@description: Сервис извлечения аудио из видеофайлов с использованием ffmpeg.
@dependencies: subprocess, pathlib, logging, dataclasses
@created: 2025-01-XX
"""

from __future__ import annotations

import dataclasses
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class AudioExtractionOptions:
    """Опции для извлечения аудио."""

    output_format: str = "wav"
    sample_rate: int = 16000
    channels: int = 1  # mono
    codec: str = "pcm_s16le"


@dataclasses.dataclass(slots=True)
class AudioExtractionResult:
    """Результат извлечения аудио."""

    audio_path: Path
    duration_seconds: Optional[float] = None
    sample_rate: int = 16000
    format: str = "wav"


class AudioExtractionError(Exception):
    """Ошибка при извлечении аудио."""

    pass


class AudioExtractor:
    """Сервис извлечения аудио из видеофайлов через ffmpeg."""

    def __init__(
        self,
        ffmpeg_executable: str = "ffmpeg",
        workdir: Optional[Path] = None,
    ) -> None:
        """
        Инициализация сервиса извлечения аудио.

        Args:
            ffmpeg_executable: Путь к исполняемому файлу ffmpeg
            workdir: Рабочая директория для временных файлов
        """
        self._ffmpeg = ffmpeg_executable
        self._workdir = workdir or Path("data/workdir")
        self._workdir.mkdir(parents=True, exist_ok=True)

    def extract(
        self,
        video_path: Path,
        output_path: Optional[Path] = None,
        options: Optional[AudioExtractionOptions] = None,
    ) -> AudioExtractionResult:
        """
        Извлекает аудио из видеофайла.

        Args:
            video_path: Путь к исходному видеофайлу
            output_path: Путь для сохранения аудио (если None, генерируется автоматически)
            options: Опции извлечения

        Returns:
            AudioExtractionResult с информацией об извлеченном аудио

        Raises:
            AudioExtractionError: При ошибке выполнения ffmpeg
        """
        if not video_path.exists():
            raise AudioExtractionError(f"Video file not found: {video_path}")

        options = options or AudioExtractionOptions()

        if output_path is None:
            output_path = self._workdir / f"{video_path.stem}.{options.output_format}"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Extracting audio from video",
            extra={
                "video_path": str(video_path),
                "output_path": str(output_path),
                "format": options.output_format,
                "sample_rate": options.sample_rate,
            },
        )

        try:
            duration = self._get_video_duration(video_path)
            self._extract_audio(video_path, output_path, options)
        except subprocess.CalledProcessError as exc:
            logger.error(
                "FFmpeg extraction failed",
                extra={"video_path": str(video_path), "error": str(exc)},
            )
            raise AudioExtractionError(f"FFmpeg failed: {exc}") from exc
        except Exception as exc:
            logger.error(
                "Unexpected error during audio extraction",
                extra={"video_path": str(video_path), "error": str(exc)},
            )
            raise AudioExtractionError(f"Extraction failed: {exc}") from exc

        if not output_path.exists():
            raise AudioExtractionError(f"Output file was not created: {output_path}")

        logger.info(
            "Audio extraction completed",
            extra={"output_path": str(output_path), "duration": duration},
        )

        return AudioExtractionResult(
            audio_path=output_path,
            duration_seconds=duration,
            sample_rate=options.sample_rate,
            format=options.output_format,
        )

    def _extract_audio(
        self,
        video_path: Path,
        output_path: Path,
        options: AudioExtractionOptions,
    ) -> None:
        """Выполняет извлечение аудио через ffmpeg."""
        cmd = [
            self._ffmpeg,
            "-i",
            str(video_path),
            "-vn",  # No video
            "-acodec",
            options.codec,
            "-ar",
            str(options.sample_rate),
            "-ac",
            str(options.channels),
            "-y",  # Overwrite output file
            str(output_path),
        ]

        logger.debug("Running ffmpeg command", extra={"cmd": " ".join(cmd)})

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        if result.stderr:
            logger.debug("FFmpeg stderr", extra={"stderr": result.stderr})

    def _get_video_duration(self, video_path: Path) -> Optional[float]:
        """
        Получает длительность видео в секундах.

        Returns:
            Длительность в секундах или None, если не удалось определить
        """
        try:
            cmd = [
                self._ffmpeg,
                "-i",
                str(video_path),
                "-hide_banner",
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,  # ffmpeg возвращает код ошибки при использовании -i без вывода
            )

            # Парсим длительность из stderr
            for line in result.stderr.split("\n"):
                if "Duration:" in line:
                    # Формат: Duration: HH:MM:SS.mmm
                    parts = line.split("Duration:")[1].split(",")[0].strip()
                    time_parts = parts.split(":")
                    if len(time_parts) == 3:
                        hours = float(time_parts[0])
                        minutes = float(time_parts[1])
                        seconds = float(time_parts[2])
                        return hours * 3600 + minutes * 60 + seconds

            logger.warning("Could not parse video duration", extra={"video_path": str(video_path)})
            return None
        except Exception as exc:
            logger.warning(
                "Failed to get video duration",
                extra={"video_path": str(video_path), "error": str(exc)},
            )
            return None

