"""
@file: schema.py
@description: Pydantic-схемы для API видеозагрузки и связанных операций.
@dependencies: pydantic, typing, enum
@created: 2025-11-12
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, validator


class ProviderLiteral(str, Enum):
    AUTO = "auto"
    YOUTUBE = "youtube"
    VK = "vk"
    RUTUBE = "rutube"


class VideoExtractOptions(BaseModel):
    audio_format: str = Field(default="wav", description="Целевой аудиоформат")
    sample_rate: Optional[int] = Field(
        default=None,
        ge=8000,
        le=96000,
        description="Частота дискретизации выходного аудио",
    )


class VideoExtractRequest(BaseModel):
    video_url: HttpUrl = Field(..., description="Ссылка на видео источник")
    provider: ProviderLiteral = Field(
        default=ProviderLiteral.AUTO,
        description="Явная подсказка провайдера; auto — определить автоматически",
    )
    request_id: Optional[str] = Field(
        default=None, description="Идентификатор запроса, если требуется отслеживание"
    )
    options: VideoExtractOptions = Field(
        default_factory=VideoExtractOptions, description="Настройки извлечения"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Дополнительные метаданные контекста"
    )

    @validator("request_id", pre=True, always=True)
    def default_request_id(cls, value: Optional[str]) -> str:
        return value or uuid4().hex


class VideoExtractResponse(BaseModel):
    video_id: Optional[str] = Field(default=None, description="ID записи видео")
    audio_path: str = Field(..., description="URI сохраненного аудиофайла")
    provider: str = Field(..., description="Определенный провайдер видео")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VideoListItem(BaseModel):
    id: str = Field(..., description="ID видео")
    title: Optional[str] = Field(default=None, description="Заголовок видео")
    source_url: HttpUrl = Field(..., description="Оригинальный URL видео")
    provider: str = Field(..., description="Провайдер медиа")
    status: str = Field(..., description="Статус обработки")
    audio_path: Optional[str] = Field(default=None, description="Путь к сохраненному аудио")
    created_at: datetime = Field(..., description="Дата создания записи")
    has_transcript: bool = Field(default=False, description="Есть ли сохранённый транскрипт")
    has_summary: bool = Field(default=False, description="Есть ли сохранённая методичка")


class VideoListResponse(BaseModel):
    items: list[VideoListItem] = Field(default_factory=list, description="Список видео в истории")


class TranscriptionMode(str, Enum):
    LOCAL = "local"
    ONLINE = "online"


class LocalTranscriptionOptions(BaseModel):
    model: str = Field(default="base", description="Модель Whisper (tiny, base, small, medium, large)")
    language: Optional[str] = Field(default=None, description="Язык аудио (None для автоопределения)")
    task: str = Field(default="transcribe", description="Задача: transcribe или translate")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0, description="Температура для генерации")


class APITranscriptionOptions(BaseModel):
    model: str = Field(default="whisper-1", description="Модель OpenAI")
    language: Optional[str] = Field(default=None, description="Язык аудио")
    prompt: Optional[str] = Field(default=None, description="Подсказка для улучшения точности")
    response_format: str = Field(default="json", description="Формат ответа (json, text, srt, verbose_json, vtt)")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0, description="Температура для генерации")


class TranscribeRequest(BaseModel):
    audio_path: str = Field(..., description="Путь к аудиофайлу")
    mode: TranscriptionMode = Field(default=TranscriptionMode.LOCAL, description="Режим транскрибации")
    local_options: Optional[LocalTranscriptionOptions] = Field(
        default=None, description="Опции для локальной транскрибации"
    )
    api_options: Optional[APITranscriptionOptions] = Field(
        default=None, description="Опции для API транскрибации"
    )
    video_id: Optional[str] = Field(default=None, description="ID видео для связи с БД")


class TranscriptionSegment(BaseModel):
    start: float = Field(..., description="Время начала сегмента в секундах")
    end: float = Field(..., description="Время окончания сегмента в секундах")
    text: str = Field(..., description="Текст сегмента")


class TranscribeResponse(BaseModel):
    text: str = Field(..., description="Полный текст транскрипции")
    language: str = Field(..., description="Определенный язык")
    segments: list[TranscriptionSegment] = Field(default_factory=list, description="Сегменты транскрипции")
    model: str = Field(..., description="Использованная модель")
    duration_seconds: Optional[float] = Field(default=None, description="Длительность аудио в секундах")
    transcript_id: Optional[str] = Field(default=None, description="ID сохранённого транскрипта")


class SummaryQuote(BaseModel):
    text: str = Field(..., description="Текст цитаты")
    timestamp: Optional[str] = Field(default=None, description="Таймкод цитаты (формат HH:MM:SS)")


class SummaryStructure(BaseModel):
    title: str = Field(..., description="Название методички")
    overview: str = Field(..., description="Краткое описание содержания")
    key_points: list[str] = Field(default_factory=list, description="Ключевые тезисы")
    quotes: list[SummaryQuote] = Field(default_factory=list, description="Важные цитаты")
    recommendations: list[str] = Field(default_factory=list, description="Практические рекомендации")
    tags: list[str] = Field(default_factory=list, description="Теги/категории")


class SummaryOptions(BaseModel):
    model: str = Field(default="gpt-4o-mini", description="Модель LLM для генерации")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Температура генерации")
    max_tokens: int = Field(default=2000, ge=100, le=4000, description="Максимальное количество токенов")
    language: str = Field(default="ru", description="Язык методички")


class SummaryRequest(BaseModel):
    transcript_text: str = Field(..., description="Текст транскрипции для генерации методички")
    video_title: Optional[str] = Field(default=None, description="Название видео")
    video_id: Optional[str] = Field(default=None, description="ID видео для связи с БД")
    options: Optional[SummaryOptions] = Field(default=None, description="Опции генерации")


class SummaryResponse(BaseModel):
    structure: SummaryStructure = Field(..., description="Структура методички")
    model: str = Field(..., description="Использованная модель")
    summary_id: Optional[str] = Field(default=None, description="ID сохраненной методички в БД")


class StoredTranscript(BaseModel):
    id: str = Field(..., description="ID сохранённого транскрипта")
    language: str = Field(..., description="Язык транскрипта")
    text: str = Field(..., description="Текст транскрипта")
    model: Optional[str] = Field(default=None, description="Модель, использованная для транскрибации")
    created_at: datetime = Field(..., description="Дата создания транскрипта")
    segments: list[TranscriptionSegment] = Field(default_factory=list, description="Сегменты транскрипции")


class StoredSummary(BaseModel):
    id: str = Field(..., description="ID сохранённой методички")
    title: str = Field(..., description="Название методички")
    structure: SummaryStructure = Field(..., description="Структура методички")
    model: Optional[str] = Field(default=None, description="Модель LLM")
    created_at: datetime = Field(..., description="Дата создания методички")


class VideoDetailResponse(BaseModel):
    id: str = Field(..., description="ID видео")
    title: Optional[str] = Field(default=None, description="Заголовок видео")
    source_url: HttpUrl = Field(..., description="Источник видео")
    provider: str = Field(..., description="Провайдер")
    status: str = Field(..., description="Статус обработки")
    audio_path: Optional[str] = Field(default=None, description="Путь к аудио")
    created_at: datetime = Field(..., description="Дата создания")
    transcript: Optional[StoredTranscript] = Field(default=None, description="Последний сохранённый транскрипт")
    summary: Optional[StoredSummary] = Field(default=None, description="Последняя сохранённая методичка")


class ChatRequest(BaseModel):
    question: str = Field(..., description="Вопрос пользователя")
    video_id: Optional[str] = Field(default=None, description="ID видео для фильтрации контекста")
    top_k: int = Field(default=5, ge=1, le=20, description="Количество релевантных фрагментов для извлечения")
    language: str = Field(default="ru", description="Язык ответа (ru/en)")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Ответ консультанта")
    sources: list[dict] = Field(default_factory=list, description="Источники информации (фрагменты транскрипта)")
    model: str = Field(..., description="Использованная модель LLM")

