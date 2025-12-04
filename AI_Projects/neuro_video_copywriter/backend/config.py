"""
@file: config.py
@description: Конфигурация backend приложения с поддержкой переменных окружения и секретов.
@dependencies: pydantic, functools, pathlib
@created: 2025-11-12
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки backend приложения."""

    environment: str = Field(default="development", description="Текущее окружение")
    log_level: str = Field(default="INFO", description="Уровень логирования")

    data_audio_dir: Path = Field(default=Path("data/audio"), description="Каталог хранения аудио")
    download_workdir: Path = Field(default=Path("data/workdir"), description="Каталог временных файлов")

    database_url: str = Field(
        default="postgresql+psycopg://nvc_user:nvc_password@localhost:5432/nvc_db",
        description="Строка подключения к PostgreSQL",
    )
    qdrant_url: str = Field(default="http://localhost:6333", description="URL сервиса Qdrant")
    qdrant_api_key: Optional[str] = Field(default=None, description="API-ключ Qdrant (если требуется)")

    yt_dlp_path: str = Field(default="yt-dlp", description="Путь до исполняемого файла yt-dlp")
    ffmpeg_path: str = Field(default="ffmpeg", description="Путь до исполняемого файла ffmpeg")
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        description="Разрешённые Origins для CORS",
    )
    cors_allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="Разрешённые HTTP-методы для CORS",
    )
    cors_allow_headers: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Разрешённые заголовки для CORS",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Разрешать ли креденшлы при CORS-запросах",
    )

    openai_api_key: Optional[str] = Field(default=None, description="Ключ OpenAI API")
    whisper_model: str = Field(default="base", description="Модель Whisper для локальной транскрибации")
    vk_access_token: Optional[str] = Field(default=None, description="Токен доступа VK (если требуется)")
    rutube_cookie_path: Optional[Path] = Field(default=None, description="Путь к cookies для RuTube")

    class Config:
        env_prefix = "NVC_"
        env_file = ".env"
        env_file_encoding = "utf-8"

    @field_validator("data_audio_dir", "download_workdir", mode="before")
    @classmethod
    def _ensure_path(cls, value: Path | str) -> Path:
        if isinstance(value, Path):
            return value
        return Path(value)

    @field_validator("rutube_cookie_path", mode="before")
    @classmethod
    def _optional_path(cls, value: str | Path | None) -> Optional[Path]:
        if value in (None, ""):
            return None
        return Path(value)


@lru_cache()
def get_settings() -> Settings:
    """Возвращает singleton настроек приложения."""
    settings = Settings()
    settings.data_audio_dir.mkdir(parents=True, exist_ok=True)
    settings.download_workdir.mkdir(parents=True, exist_ok=True)
    return settings

