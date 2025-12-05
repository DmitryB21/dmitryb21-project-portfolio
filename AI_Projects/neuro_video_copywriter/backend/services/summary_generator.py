"""
@file: summary_generator.py
@description: Сервис генерации методички из транскрипта с использованием LLM.
@dependencies: openai, logging, dataclasses
@created: 2025-01-XX
"""

from __future__ import annotations

import dataclasses
import json
import logging
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class SummaryOptions:
    """Опции для генерации методички."""

    model: str = "gpt-4o-mini"  # или gpt-4, gpt-3.5-turbo
    temperature: float = 0.7
    max_tokens: int = 2000
    language: str = "ru"  # Язык методички


@dataclasses.dataclass(slots=True)
class SummaryStructure:
    """Структура методички."""

    title: str
    overview: str  # Краткое описание
    key_points: list[str]  # Ключевые тезисы
    quotes: list[dict[str, str]]  # Цитаты с таймкодами: [{"text": "...", "timestamp": "00:05:23"}]
    recommendations: list[str]  # Рекомендации
    tags: list[str] = dataclasses.field(default_factory=list)  # Теги/категории


@dataclasses.dataclass(slots=True)
class SummaryResult:
    """Результат генерации методички."""

    structure: SummaryStructure
    raw_response: Optional[str] = None
    model: str = "gpt-4o-mini"


class SummaryGenerationError(Exception):
    """Ошибка при генерации методички."""

    pass


class SummaryGenerator:
    """Сервис генерации методички из транскрипта."""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
    ) -> None:
        """
        Инициализация сервиса генерации методички.

        Args:
            api_key: API ключ OpenAI
            base_url: Базовый URL API (опционально)
        """
        if OpenAI is None:
            raise SummaryGenerationError(
                "OpenAI library is not installed. Install it with: pip install openai"
            )

        if not api_key:
            raise SummaryGenerationError("OpenAI API key is required")

        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(
        self,
        transcript_text: str,
        video_title: Optional[str] = None,
        options: Optional[SummaryOptions] = None,
    ) -> SummaryResult:
        """
        Генерирует методичку из транскрипта.

        Args:
            transcript_text: Текст транскрипции
            video_title: Название видео (опционально)
            options: Опции генерации

        Returns:
            SummaryResult со структурой методички

        Raises:
            SummaryGenerationError: При ошибке генерации
        """
        if not transcript_text or not transcript_text.strip():
            raise SummaryGenerationError("Transcript text is empty")

        options = options or SummaryOptions()

        logger.info(
            "Generating summary",
            extra={
                "transcript_length": len(transcript_text),
                "model": options.model,
                "video_title": video_title,
            },
        )

        try:
            prompt = self._build_prompt(transcript_text, video_title, options.language)
            response = self._client.chat.completions.create(
                model=options.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(options.language),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=options.temperature,
                max_tokens=options.max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise SummaryGenerationError("Empty response from LLM")

            logger.debug("LLM response received", extra={"response_length": len(content)})

            # Парсим JSON ответ
            try:
                summary_data = json.loads(content)
            except json.JSONDecodeError as exc:
                logger.error("Failed to parse LLM response as JSON", extra={"error": str(exc)})
                raise SummaryGenerationError(f"Invalid JSON response: {exc}") from exc

            structure = self._parse_summary_structure(summary_data)
            logger.info("Summary generated successfully", extra={"title": structure.title})

            return SummaryResult(
                structure=structure,
                raw_response=content,
                model=options.model,
            )
        except Exception as exc:
            if isinstance(exc, SummaryGenerationError):
                raise
            logger.error(
                "Summary generation failed",
                extra={"error": str(exc), "transcript_length": len(transcript_text)},
            )
            raise SummaryGenerationError(f"Generation failed: {exc}") from exc

    def _get_system_prompt(self, language: str) -> str:
        """Возвращает системный промпт для LLM."""
        if language == "ru":
            return """Ты - эксперт по созданию методических материалов для образовательных целей.
Твоя задача - создать структурированную методичку на основе транскрипта лекции или видео.

Методичка должна быть:
- Понятной и структурированной
- Содержать ключевые тезисы
- Включать важные цитаты
- Содержать практические рекомендации

Верни результат в формате JSON со следующей структурой:
{
  "title": "Название методички",
  "overview": "Краткое описание содержания",
  "key_points": ["Тезис 1", "Тезис 2", ...],
  "quotes": [{"text": "Цитата", "timestamp": "00:05:23"}, ...],
  "recommendations": ["Рекомендация 1", ...],
  "tags": ["тег1", "тег2", ...]
}"""
        else:
            return """You are an expert in creating educational materials.
Your task is to create a structured summary based on a lecture or video transcript.

The summary should be:
- Clear and structured
- Contain key points
- Include important quotes
- Contain practical recommendations

Return the result in JSON format with the following structure:
{
  "title": "Summary title",
  "overview": "Brief description",
  "key_points": ["Point 1", "Point 2", ...],
  "quotes": [{"text": "Quote", "timestamp": "00:05:23"}, ...],
  "recommendations": ["Recommendation 1", ...],
  "tags": ["tag1", "tag2", ...]
}"""

    def _build_prompt(self, transcript_text: str, video_title: Optional[str], language: str) -> str:
        """Строит промпт для генерации методички."""
        if language == "ru":
            title_part = f"\nНазвание видео: {video_title}\n" if video_title else ""
            return f"""Создай методичку на основе следующего транскрипта:{title_part}

Транскрипт:
{transcript_text}

Создай структурированную методичку с ключевыми тезисами, важными цитатами и практическими рекомендациями.
Если в транскрипте есть таймкоды, используй их для цитат. Если нет - оставь timestamp пустым."""
        else:
            title_part = f"\nVideo title: {video_title}\n" if video_title else ""
            return f"""Create a summary based on the following transcript:{title_part}

Transcript:
{transcript_text}

Create a structured summary with key points, important quotes, and practical recommendations.
If the transcript has timestamps, use them for quotes. If not - leave timestamp empty."""

    def _parse_summary_structure(self, data: dict) -> SummaryStructure:
        """Парсит JSON данные в структуру SummaryStructure."""
        try:
            return SummaryStructure(
                title=data.get("title", "Методичка"),
                overview=data.get("overview", ""),
                key_points=data.get("key_points", []),
                quotes=data.get("quotes", []),
                recommendations=data.get("recommendations", []),
                tags=data.get("tags", []),
            )
        except Exception as exc:
            logger.error("Failed to parse summary structure", extra={"error": str(exc), "data": data})
            raise SummaryGenerationError(f"Failed to parse summary structure: {exc}") from exc

