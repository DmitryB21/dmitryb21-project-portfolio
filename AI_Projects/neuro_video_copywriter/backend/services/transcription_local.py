"""
@file: transcription_local.py
@description: Сервис локальной транскрибации аудио с использованием OpenAI Whisper.
@dependencies: whisper, pathlib, logging, dataclasses
@created: 2025-01-XX
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Optional

try:
    import whisper
except ImportError:
    whisper = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class TranscriptionOptions:
    """Опции для транскрибации."""

    model: str = "base"  # tiny, base, small, medium, large
    language: Optional[str] = None  # Автоопределение, если None
    task: str = "transcribe"  # transcribe или translate
    temperature: float = 0.0
    verbose: bool = False


@dataclasses.dataclass(slots=True)
class TranscriptionResult:
    """Результат транскрибации."""

    text: str
    language: str
    segments: list[dict] = dataclasses.field(default_factory=list)
    model: str = "base"


class TranscriptionError(Exception):
    """Ошибка при транскрибации."""

    pass


class LocalTranscriptionService:
    """Сервис локальной транскрибации через Whisper."""

    def __init__(
        self,
        model_name: str = "base",
        device: Optional[str] = None,
    ) -> None:
        """
        Инициализация сервиса транскрибации.

        Args:
            model_name: Название модели Whisper (tiny, base, small, medium, large)
            device: Устройство для выполнения (cuda, cpu, или None для автоопределения)
        """
        if whisper is None:
            raise TranscriptionError(
                "OpenAI Whisper is not installed. Install it with: pip install openai-whisper"
            )

        self._model_name = model_name
        self._device = device
        self._model: Optional[whisper.Whisper] = None

    def transcribe(
        self,
        audio_path: Path,
        options: Optional[TranscriptionOptions] = None,
    ) -> TranscriptionResult:
        """
        Транскрибирует аудиофайл.

        Args:
            audio_path: Путь к аудиофайлу
            options: Опции транскрибации

        Returns:
            TranscriptionResult с текстом транскрипции

        Raises:
            TranscriptionError: При ошибке транскрибации
        """
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        options = options or TranscriptionOptions()

        logger.info(
            "Starting local transcription",
            extra={
                "audio_path": str(audio_path),
                "model": options.model,
                "language": options.language,
            },
        )

        try:
            model = self._get_model(options.model)
            result = model.transcribe(
                str(audio_path),
                language=options.language,
                task=options.task,
                temperature=options.temperature,
                verbose=options.verbose,
            )

            logger.info(
                "Transcription completed",
                extra={
                    "audio_path": str(audio_path),
                    "text_length": len(result.get("text", "")),
                    "language": result.get("language", "unknown"),
                },
            )

            return TranscriptionResult(
                text=result.get("text", ""),
                language=result.get("language", "unknown"),
                segments=result.get("segments", []),
                model=options.model,
            )
        except Exception as exc:
            logger.error(
                "Transcription failed",
                extra={"audio_path": str(audio_path), "error": str(exc)},
            )
            raise TranscriptionError(f"Transcription failed: {exc}") from exc

    def _get_model(self, model_name: str) -> whisper.Whisper:
        """
        Получает загруженную модель Whisper (с кэшированием).

        Args:
            model_name: Название модели

        Returns:
            Загруженная модель Whisper
        """
        if self._model is None or self._model_name != model_name:
            logger.info("Loading Whisper model", extra={"model": model_name})
            self._model = whisper.load_model(model_name, device=self._device)
            self._model_name = model_name

        return self._model

