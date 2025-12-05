"""
@file: audio_chunker.py
@description: Утилита для разбиения аудиофайлов на части под ограничения OpenAI API.
@dependencies: pydub, pathlib, tempfile, logging
@created: 2025-11-17
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List

from pydub import AudioSegment

logger = logging.getLogger(__name__)


class AudioChunkError(Exception):
    """Ошибка при разбиении аудио."""


@dataclass(slots=True)
class AudioChunkConfig:
    """Настройки разбиения аудио."""

    max_chunk_bytes: int = int(24.5 * 1024 * 1024)  # небольшой запас до 25MB
    initial_chunk_duration_ms: int = 10 * 60 * 1000  # 10 минут
    min_chunk_duration_ms: int = 60 * 1000  # 1 минута
    duration_step_ratio: float = 0.8  # во сколько раз уменьшать длину при превышении лимита
    output_format: str = "mp3"
    temp_prefix: str = "nvc-audio-chunk"

    def __post_init__(self) -> None:
        if not (0 < self.duration_step_ratio < 1):
            raise ValueError("duration_step_ratio must be between 0 and 1")
        if self.min_chunk_duration_ms <= 0:
            raise ValueError("min_chunk_duration_ms must be positive")
        if self.initial_chunk_duration_ms < self.min_chunk_duration_ms:
            raise ValueError("initial_chunk_duration_ms must be >= min_chunk_duration_ms")


class AudioChunker:
    """Утилита для генерации аудио-чанков, соответствующих лимитам API."""

    def __init__(self, config: AudioChunkConfig | None = None) -> None:
        self._config = config or AudioChunkConfig()
        self._temp_dir = Path(tempfile.mkdtemp(prefix=self._config.temp_prefix))
        self._produced_files: List[Path] = []
        logger.debug("AudioChunker temp dir created", extra={"temp_dir": str(self._temp_dir)})

    def __enter__(self) -> AudioChunker:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.cleanup()

    def cleanup(self) -> None:
        """Удаляет временные файлы и каталог."""
        for chunk_file in self._produced_files:
            if chunk_file.exists():
                chunk_file.unlink()
        if self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._produced_files.clear()
        logger.debug("AudioChunker temp dir cleaned", extra={"temp_dir": str(self._temp_dir)})

    def chunk(self, audio_path: Path) -> Iterator[Path]:
        """
        Разбивает аудиофайл на части, размер которых не превышает ограничения API.

        Args:
            audio_path: исходный аудиофайл

        Yields:
            Путь к временному файлу чанка
        """
        if not audio_path.exists():
            raise AudioChunkError(f"Audio file not found: {audio_path}")

        audio = AudioSegment.from_file(audio_path)
        chunk_duration_ms = self._config.initial_chunk_duration_ms
        start_ms = 0
        chunk_index = 1

        while start_ms < len(audio):
            chunk = audio[start_ms : start_ms + chunk_duration_ms]
            chunk_name = f"chunk_{chunk_index}.{self._config.output_format}"
            chunk_path = self._temp_dir / chunk_name
            chunk.export(chunk_path, format=self._config.output_format)

            file_size = chunk_path.stat().st_size
            if file_size > self._config.max_chunk_bytes:
                chunk_path.unlink(missing_ok=True)
                next_duration = max(
                    int(chunk_duration_ms * self._config.duration_step_ratio),
                    self._config.min_chunk_duration_ms,
                )
                if next_duration == chunk_duration_ms:
                    raise AudioChunkError(
                        "Audio chunk size exceeds limit and cannot be reduced further"
                    )
                chunk_duration_ms = next_duration
                logger.debug(
                    "Chunk size too large, reducing duration",
                    extra={
                        "audio_path": str(audio_path),
                        "chunk_index": chunk_index,
                        "attempt_duration_ms": chunk_duration_ms,
                    },
                )
                continue

            self._produced_files.append(chunk_path)
            logger.debug(
                "Chunk created",
                extra={
                    "audio_path": str(audio_path),
                    "chunk_index": chunk_index,
                    "chunk_duration_ms": chunk_duration_ms,
                    "chunk_size_bytes": file_size,
                },
            )
            yield chunk_path

            start_ms += chunk_duration_ms
            chunk_index += 1

