"""
@file: backend/services/__init__.py
@description: Общий пакет сервисов backend для обработки видео и аудио.
@dependencies: backend.utils, backend.models
@created: 2025-11-12
"""

from .audio_chunker import AudioChunkConfig, AudioChunkError, AudioChunker
from .audio_extractor import AudioExtractor, AudioExtractionError, AudioExtractionOptions, AudioExtractionResult
from .transcription_api import (
    APITranscriptionError,
    APITranscriptionOptions,
    APITranscriptionResult,
    APITranscriptionService,
)
from .transcription_local import (
    LocalTranscriptionService,
    TranscriptionError,
    TranscriptionOptions,
    TranscriptionResult,
)
from .consultant_agent import ConsultantAgent, ConsultantError
from .embedding_service import EmbeddingError, EmbeddingService
from .transcript_indexer import IndexingError, TranscriptIndexer
from .summary_generator import (
    SummaryGenerationError,
    SummaryGenerator,
    SummaryOptions,
    SummaryResult,
    SummaryStructure,
)
from .video_downloader import (
    ProviderError,
    StorageError,
    VideoDownloadRequest,
    VideoDownloadResponse,
    VideoDownloadService,
)

__all__ = [
    # Video downloader
    "VideoDownloadService",
    "VideoDownloadRequest",
    "VideoDownloadResponse",
    "ProviderError",
    "StorageError",
    # Audio chunker
    "AudioChunker",
    "AudioChunkConfig",
    "AudioChunkError",
    # Audio extractor
    "AudioExtractor",
    "AudioExtractionOptions",
    "AudioExtractionResult",
    "AudioExtractionError",
    # Local transcription
    "LocalTranscriptionService",
    "TranscriptionOptions",
    "TranscriptionResult",
    "TranscriptionError",
    # API transcription
    "APITranscriptionService",
    "APITranscriptionOptions",
    "APITranscriptionResult",
    "APITranscriptionError",
    # Summary generator
    "SummaryGenerator",
    "SummaryOptions",
    "SummaryResult",
    "SummaryStructure",
    "SummaryGenerationError",
    # Embedding service
    "EmbeddingService",
    "EmbeddingError",
    # Consultant agent
    "ConsultantAgent",
    "ConsultantError",
    # Transcript indexer
    "TranscriptIndexer",
    "IndexingError",
]

