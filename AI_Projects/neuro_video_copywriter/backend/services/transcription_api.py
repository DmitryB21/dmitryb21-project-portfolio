"""
@file: transcription_api.py
@description: Сервис транскрибации аудио через OpenAI API.
@dependencies: openai, pathlib, logging, dataclasses
@created: 2025-01-XX
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

from .audio_chunker import AudioChunkConfig, AudioChunkError, AudioChunker

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class APITranscriptionOptions:
    """Опции для транскрибации через API."""

    model: str = "whisper-1"
    language: Optional[str] = None
    prompt: Optional[str] = None  # Подсказка для улучшения точности
    response_format: str = "json"  # json, text, srt, verbose_json, vtt
    temperature: float = 0.0


@dataclasses.dataclass(slots=True)
class APITranscriptionResult:
    """Результат транскрибации через API."""

    text: str
    language: Optional[str] = None
    segments: Optional[list[dict]] = None
    model: str = "whisper-1"


class APITranscriptionError(Exception):
    """Ошибка при транскрибации через API."""

    pass


class APITranscriptionService:
    """Сервис транскрибации через OpenAI API."""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
    ) -> None:
        """
        Инициализация сервиса транскрибации.

        Args:
            api_key: API ключ OpenAI
            base_url: Базовый URL API (опционально, для совместимости с другими провайдерами)
        """
        if OpenAI is None:
            raise APITranscriptionError(
                "OpenAI library is not installed. Install it with: pip install openai"
            )

        if not api_key:
            raise APITranscriptionError("OpenAI API key is required")

        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def transcribe(
        self,
        audio_path: Path,
        options: Optional[APITranscriptionOptions] = None,
    ) -> APITranscriptionResult:
        """
        Транскрибирует аудиофайл через OpenAI API.

        Args:
            audio_path: Путь к аудиофайлу
            options: Опции транскрибации

        Returns:
            APITranscriptionResult с текстом транскрипции

        Raises:
            APITranscriptionError: При ошибке транскрибации
        """
        if not audio_path.exists():
            raise APITranscriptionError(f"Audio file not found: {audio_path}")

        options = options or APITranscriptionOptions()

        file_size_mb = audio_path.stat().st_size / (1024 * 1024)

        if file_size_mb <= 25:
            return self._transcribe_file(audio_path, options, file_size_mb)

        return self._transcribe_in_chunks(audio_path, options, file_size_mb)

    def _transcribe_file(
        self,
        audio_path: Path,
        options: APITranscriptionOptions,
        file_size_mb: float,
    ) -> APITranscriptionResult:
        logger.info(
            "Starting API transcription",
            extra={
                "audio_path": str(audio_path),
                "model": options.model,
                "language": options.language,
                "file_size_mb": f"{file_size_mb:.2f}",
            },
        )

        try:
            transcript = self._call_openai(audio_path, options)
        except Exception as exc:
            logger.error(
                "API transcription failed",
                extra={"audio_path": str(audio_path), "error": str(exc)},
            )
            raise APITranscriptionError(f"API transcription failed: {exc}") from exc

        logger.info(
            "API transcription completed",
            extra={
                "audio_path": str(audio_path),
                "text_length": len(transcript.text),
                "language": transcript.language or "unknown",
            },
        )
        return transcript

    def _transcribe_in_chunks(
        self,
        audio_path: Path,
        options: APITranscriptionOptions,
        file_size_mb: float,
    ) -> APITranscriptionResult:
        logger.info(
            "Starting chunked API transcription",
            extra={
                "audio_path": str(audio_path),
                "model": options.model,
                "language": options.language,
                "file_size_mb": f"{file_size_mb:.2f}",
            },
        )

        combined_text: list[str] = []
        detected_language: Optional[str] = None
        chunk_count = 0

        try:
            with AudioChunker(AudioChunkConfig()) as chunker:
                for chunk_path in chunker.chunk(audio_path):
                    chunk_count += 1
                    chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
                    logger.debug(
                        "Sending chunk to OpenAI",
                        extra={
                            "audio_path": str(audio_path),
                            "chunk_index": chunk_count,
                            "chunk_file": str(chunk_path),
                            "chunk_size_mb": f"{chunk_size_mb:.2f}",
                        },
                    )
                    chunk_result = self._call_openai(chunk_path, options)
                    if chunk_result.text:
                        combined_text.append(chunk_result.text.strip())
                    if not detected_language and chunk_result.language:
                        detected_language = chunk_result.language

        except AudioChunkError as exc:
            logger.error(
                "Chunking failed",
                extra={"audio_path": str(audio_path), "error": str(exc)},
            )
            raise APITranscriptionError(f"Chunking failed: {exc}") from exc
        except Exception as exc:
            logger.error(
                "Chunked API transcription failed",
                extra={"audio_path": str(audio_path), "error": str(exc)},
            )
            raise APITranscriptionError(f"API transcription failed: {exc}") from exc

        logger.info(
            "Chunked API transcription completed",
            extra={
                "audio_path": str(audio_path),
                "chunks_processed": chunk_count,
                "text_length": sum(len(part) for part in combined_text),
                "language": detected_language or options.language or "unknown",
            },
        )

        return APITranscriptionResult(
            text="\n".join(part for part in combined_text if part),
            language=detected_language or options.language,
            segments=None,
            model=options.model,
        )

    def _call_openai(
        self,
        audio_path: Path,
        options: APITranscriptionOptions,
    ) -> APITranscriptionResult:
        with open(audio_path, "rb") as audio_file:
            transcript = self._client.audio.transcriptions.create(
                model=options.model,
                file=audio_file,
                language=options.language,
                prompt=options.prompt,
                response_format=options.response_format,
                temperature=options.temperature,
            )

        if isinstance(transcript, str):
            text = transcript
            segments = None
            language = None
        elif hasattr(transcript, "text"):
            text = transcript.text
            segments = getattr(transcript, "segments", None)
            language = getattr(transcript, "language", None)
        else:
            text = str(transcript)
            segments = None
            language = None

        return APITranscriptionResult(
            text=text,
            language=language,
            segments=segments,
            model=options.model,
        )

