"""
@file: app.py
@description: Точка входа FastAPI-приложения neuro_video_copywriter.
@dependencies: backend.services, backend.models.schema, fastapi
@created: 2025-11-12
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Iterable, Mapping, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session, sessionmaker

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from config import Settings, get_settings
from database import models as db_models
from database.session import get_db_session, get_session_factory
from models.schema import (
    ChatRequest,
    ChatResponse,
    ProviderLiteral,
    SummaryOptions,
    SummaryQuote,
    SummaryRequest,
    SummaryResponse,
    SummaryStructure,
    VideoDetailResponse,
    VideoListItem,
    VideoListResponse,
    TranscriptionMode,
    TranscriptionSegment,
    TranscribeRequest,
    TranscribeResponse,
    VideoExtractRequest,
    VideoExtractResponse,
    StoredSummary,
    StoredTranscript,
)
from services.audio_extractor import AudioExtractor, AudioExtractionError, AudioExtractionOptions
from services.storage import LocalFileStorage, MediaLocation, MediaStorage, StorageError
from services.transcription_api import (
    APITranscriptionError,
    APITranscriptionOptions,
    APITranscriptionService,
)
from services.consultant_agent import ConsultantAgent, ConsultantError
from services.embedding_service import EmbeddingError, EmbeddingService
from services.summary_generator import (
    SummaryGenerationError,
    SummaryGenerator,
    SummaryOptions as ServiceSummaryOptions,
)
from services.transcription_local import (
    LocalTranscriptionService,
    TranscriptionError,
    TranscriptionOptions,
)
from services.vector_store import VectorStoreClient
from services.transcript_indexer import TranscriptIndexer, IndexingError
from repositories.video_repository import VideoRepository
from repositories.transcript_repository import TranscriptRepository
from repositories.summary_repository import SummaryRepository

logger = logging.getLogger(__name__)

from services.video_downloader import (
    ProviderError,
    VideoDownloadRequest,
    VideoDownloadResponse,
    VideoDownloadService,
)


def create_app() -> FastAPI:
    """
    Фабрика приложения для инициализации FastAPI со стандартными зависимостями.
    Возвращает готовый экземпляр приложения для запуска и тестирования.
    """
    app = FastAPI(
        title="Neuro Video Copywriter API",
        version="0.1.0",
        description="API для обработки видео, транскрибации и AI-функционала.",
    )

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        allow_credentials=settings.cors_allow_credentials,
    )

    register_routes(app)

    return app


def register_routes(app: FastAPI) -> None:
    @app.post(
        "/api/video/extract",
        response_model=VideoExtractResponse,
        status_code=status.HTTP_200_OK,
        summary="Загрузка видео и извлечение аудио",
    )
    async def extract_video_endpoint(
        payload: VideoExtractRequest,
        service: VideoDownloadService = Depends(get_video_download_service),
        db: Session = Depends(get_db_session_dependency),
    ) -> VideoExtractResponse:
        request = VideoDownloadRequest(
            url=str(payload.video_url),
            provider_hint=None if payload.provider is ProviderLiteral.AUTO else payload.provider.value,
            request_id=payload.request_id,
            context_metadata=payload.metadata,
        )
        try:
            result: VideoDownloadResponse = await run_in_threadpool(
                service.handle,
                request,
            )
        except ProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except StorageError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store media file",
            ) from exc

        video = _upsert_video_record(
            db,
            source_url=str(payload.video_url),
            provider=result.provider,
            audio_path=result.audio_location.uri,
            metadata=result.metadata,
        )

        return VideoExtractResponse(
            video_id=str(video.id),
            audio_path=result.audio_location.uri,
            provider=result.provider,
            metadata=result.metadata,
        )

    @app.get(
        "/api/videos",
        response_model=VideoListResponse,
        status_code=status.HTTP_200_OK,
        summary="Список загруженных видео",
    )
    async def list_videos_endpoint(
        limit: int = 50,
        db: Session = Depends(get_db_session_dependency),
    ) -> VideoListResponse:
        repo = VideoRepository(db)
        videos = repo.list(limit=limit)
        items = [
            VideoListItem(
                id=str(video.id),
                title=video.title,
                source_url=video.source_url,
                provider=video.provider,
                status=video.status,
                audio_path=video.audio_path,
                created_at=video.created_at,
                has_transcript=bool(video.transcripts),
                has_summary=bool(video.summaries),
            )
            for video in videos
        ]
        return VideoListResponse(items=items)

    @app.get(
        "/api/videos/{video_id}",
        response_model=VideoDetailResponse,
        status_code=status.HTTP_200_OK,
        summary="Детальная информация о видео",
    )
    async def video_detail_endpoint(
        video_id: str,
        db: Session = Depends(get_db_session_dependency),
    ) -> VideoDetailResponse:
        video_uuid = _require_video_uuid(video_id)
        repo = VideoRepository(db)
        video = repo.get_by_id(video_uuid)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found",
            )

        transcript_repo = TranscriptRepository(db, get_vector_store_client())
        summary_repo = SummaryRepository(db)
        latest_transcript = transcript_repo.get_latest_by_video(video_uuid)
        latest_summary = summary_repo.get_by_video(video_uuid)

        return _build_video_detail_response(
            video=video,
            transcript=latest_transcript,
            summary=latest_summary,
        )

    @app.delete(
        "/api/videos/{video_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Удаление видео и связанных данных",
    )
    async def delete_video_endpoint(
        video_id: str,
        db: Session = Depends(get_db_session_dependency),
    ) -> Response:
        video_uuid = _require_video_uuid(video_id)
        repo = VideoRepository(db)
        video = repo.get_by_id(video_uuid)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found",
            )

        _delete_video(
            db=db,
            video=video,
            transcript_repo=TranscriptRepository(db, get_vector_store_client()),
            summary_repo=SummaryRepository(db),
            storage=get_media_storage(),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/api/transcribe/local",
        response_model=TranscribeResponse,
        status_code=status.HTTP_200_OK,
        summary="Локальная транскрибация аудио через Whisper",
    )
    async def transcribe_local_endpoint(
        payload: TranscribeRequest,
        service: LocalTranscriptionService = Depends(get_local_transcription_service),
        indexer: TranscriptIndexer = Depends(get_transcript_indexer),
        db: Session = Depends(get_db_session_dependency),
    ) -> TranscribeResponse:
        audio_path = _resolve_audio_path(payload.audio_path)
        if not audio_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio file not found: {payload.audio_path}",
            )

        options = TranscriptionOptions(
            model=payload.local_options.model if payload.local_options else "base",
            language=payload.local_options.language if payload.local_options else None,
            task=payload.local_options.task if payload.local_options else "transcribe",
            temperature=payload.local_options.temperature if payload.local_options else 0.0,
        )

        video_uuid = _parse_video_id(payload.video_id)
        segments_raw: Iterable[dict] | None = None
        try:
            result = await run_in_threadpool(service.transcribe, audio_path, options)
        except TranscriptionError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

        segments_raw = result.segments
        segments = [
            TranscriptionSegment(
                start=seg.get("start", 0.0),
                end=seg.get("end", 0.0),
                text=seg.get("text", ""),
            )
            for seg in result.segments
        ]

        transcript_id: Optional[str] = None
        if video_uuid:
            try:
                transcript = _save_transcript_record(
                    db=db,
                    video_id=video_uuid,
                    response_text=result.text,
                    language=result.language,
                    model=result.model,
                    mode="local",
                    duration=result.duration_seconds,
                    segments=segments,
                )
                transcript_id = str(transcript.id)
                await _maybe_index_transcript(
                    video_uuid=video_uuid,
                    transcript_uuid=transcript.id,
                    text=result.text,
                    segments_raw=segments_raw,
                    indexer=indexer,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to persist local transcript",
                    extra={"video_id": payload.video_id, "error": str(exc)},
                )

        response = TranscribeResponse(
            text=result.text,
            language=result.language,
            segments=segments,
            model=result.model,
            duration_seconds=None,
            transcript_id=transcript_id,
        )

        return response

    @app.post(
        "/api/transcribe/online",
        response_model=TranscribeResponse,
        status_code=status.HTTP_200_OK,
        summary="Транскрибация аудио через OpenAI API",
    )
    async def transcribe_online_endpoint(
        payload: TranscribeRequest,
        service: APITranscriptionService = Depends(get_api_transcription_service),
        indexer: TranscriptIndexer = Depends(get_transcript_indexer),
        db: Session = Depends(get_db_session_dependency),
    ) -> TranscribeResponse:
        audio_path = _resolve_audio_path(payload.audio_path)
        if not audio_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio file not found: {payload.audio_path}",
            )

        options = APITranscriptionOptions(
            model=payload.api_options.model if payload.api_options else "whisper-1",
            language=payload.api_options.language if payload.api_options else None,
            prompt=payload.api_options.prompt if payload.api_options else None,
            response_format=payload.api_options.response_format if payload.api_options else "json",
            temperature=payload.api_options.temperature if payload.api_options else 0.0,
        )

        video_uuid = _parse_video_id(payload.video_id)
        segments_raw: Iterable[dict] | None = None

        duration = None
        try:
            # Получаем длительность аудио
            extractor = get_audio_extractor()
            try:
                duration = await run_in_threadpool(extractor._get_video_duration, audio_path)
            except Exception:
                pass

            result = await run_in_threadpool(service.transcribe, audio_path, options)
        except APITranscriptionError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

        segments_raw = result.segments
        segments: list[TranscriptionSegment] = []
        if segments_raw:
            segments = [
                TranscriptionSegment(
                    start=seg.get("start", 0.0),
                    end=seg.get("end", 0.0),
                    text=seg.get("text", ""),
                )
                for seg in segments_raw
            ]

        transcript_id: Optional[str] = None
        if video_uuid:
            try:
                transcript = _save_transcript_record(
                    db=db,
                    video_id=video_uuid,
                    response_text=result.text,
                    language=result.language or "unknown",
                    model=result.model,
                    mode="online",
                    duration=duration,
                    segments=segments,
                )
                transcript_id = str(transcript.id)
                await _maybe_index_transcript(
                    video_uuid=video_uuid,
                    transcript_uuid=transcript.id,
                    text=result.text,
                    segments_raw=segments_raw,
                    indexer=indexer,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to persist online transcript",
                    extra={"video_id": payload.video_id, "error": str(exc)},
                )

        response = TranscribeResponse(
            text=result.text,
            language=result.language or "unknown",
            segments=segments,
            model=result.model,
            duration_seconds=duration,
             transcript_id=transcript_id,
        )

        return response

    @app.post(
        "/api/summary",
        response_model=SummaryResponse,
        status_code=status.HTTP_200_OK,
        summary="Генерация методички из транскрипта",
    )
    async def generate_summary_endpoint(
        payload: SummaryRequest,
        service: SummaryGenerator = Depends(get_summary_generator),
        db: Session = Depends(get_db_session_dependency),
    ) -> SummaryResponse:
        if not payload.transcript_text or not payload.transcript_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transcript text is required and cannot be empty",
            )

        options = ServiceSummaryOptions(
            model=payload.options.model if payload.options else "gpt-4o-mini",
            temperature=payload.options.temperature if payload.options else 0.7,
            max_tokens=payload.options.max_tokens if payload.options else 2000,
            language=payload.options.language if payload.options else "ru",
        )

        try:
            result = await run_in_threadpool(
                service.generate,
                payload.transcript_text,
                payload.video_title,
                options,
            )
        except SummaryGenerationError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

        quotes = []
        for quote in result.structure.quotes:
            if isinstance(quote, dict):
                quotes.append(SummaryQuote(text=quote.get("text", ""), timestamp=quote.get("timestamp")))
            else:
                quotes.append(SummaryQuote(text=quote.text, timestamp=quote.timestamp))

        structure = SummaryStructure(
            title=result.structure.title,
            overview=result.structure.overview,
            key_points=result.structure.key_points,
            quotes=quotes,
            recommendations=result.structure.recommendations,
            tags=result.structure.tags,
        )

        summary_id = None
        video_uuid = _parse_video_id(payload.video_id)
        if video_uuid:
            try:
                summary = _save_summary_record(
                    db=db,
                    video_id=video_uuid,
                    structure=structure,
                    model=result.model,
                )
                summary_id = str(summary.id)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to persist summary",
                    extra={"video_id": payload.video_id, "error": str(exc)},
                )

        return SummaryResponse(
            structure=structure,
            model=result.model,
            summary_id=summary_id,
        )

    @app.post(
        "/api/chat",
        response_model=ChatResponse,
        status_code=status.HTTP_200_OK,
        summary="Чат-консультант с контекстом лекции",
    )
    async def chat_endpoint(
        payload: ChatRequest,
        agent: ConsultantAgent = Depends(get_consultant_agent),
    ) -> ChatResponse:
        if not payload.question or not payload.question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question is required and cannot be empty",
            )

        try:
            answer, sources = await run_in_threadpool(
                agent.answer,
                payload.question,
                payload.video_id,
                payload.top_k,
                payload.language,
            )
        except ConsultantError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

        return ChatResponse(
            answer=answer,
            sources=sources,
            model=agent._llm_model,
        )


@lru_cache()
def get_media_storage() -> MediaStorage:
    settings: Settings = get_settings()
    return LocalFileStorage(root_dir=settings.data_audio_dir)


@lru_cache()
def get_video_download_service() -> VideoDownloadService:
    settings: Settings = get_settings()
    storage = get_media_storage()
    return VideoDownloadService(
        storage=storage,
        workdir=settings.download_workdir,
        yt_dlp_executable=settings.yt_dlp_path,
    )


@lru_cache()
def get_sessionmaker() -> sessionmaker[Session]:
    return get_session_factory()


def get_db_session_dependency(
    session_factory: Annotated[sessionmaker[Session], Depends(get_sessionmaker)]
):
    yield from get_db_session(session_factory)


@lru_cache()
def get_vector_store_client() -> VectorStoreClient:
    return VectorStoreClient()


@lru_cache()
def get_audio_extractor() -> AudioExtractor:
    settings: Settings = get_settings()
    return AudioExtractor(
        ffmpeg_executable=settings.ffmpeg_path,
        workdir=settings.download_workdir,
    )


@lru_cache()
def get_local_transcription_service() -> LocalTranscriptionService:
    settings: Settings = get_settings()
    return LocalTranscriptionService(model_name=settings.whisper_model)


@lru_cache()
def get_api_transcription_service() -> APITranscriptionService:
    settings: Settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key is required for API transcription")
    return APITranscriptionService(api_key=settings.openai_api_key)


@lru_cache()
def get_summary_generator() -> SummaryGenerator:
    settings: Settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key is required for summary generation")
    return SummaryGenerator(api_key=settings.openai_api_key)


@lru_cache()
def get_embedding_service() -> EmbeddingService:
    settings: Settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key is required for embedding generation")
    return EmbeddingService(api_key=settings.openai_api_key)


@lru_cache()
def get_transcript_indexer() -> TranscriptIndexer:
    return TranscriptIndexer(
        embedding_service=get_embedding_service(),
        vector_store=get_vector_store_client(),
    )


def _resolve_audio_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    settings: Settings = get_settings()
    return settings.data_audio_dir / path


def _upsert_video_record(
    db: Session,
    *,
    source_url: str,
    provider: str,
    audio_path: str,
    metadata: Mapping[str, object],
) -> db_models.Video:
    repo = VideoRepository(db)
    title = metadata.get("title") if isinstance(metadata, Mapping) else None
    if isinstance(title, str):
        normalized_title = title.strip()
        title_value = normalized_title or None
    else:
        title_value = None

    video = repo.upsert_downloaded_video(
        source_url=source_url,
        provider=provider,
        audio_path=audio_path,
        title=title_value,
        status="downloaded",
    )
    return video


def _save_transcript_record(
    *,
    db: Session,
    video_id: UUID,
    response_text: str,
    language: str,
    model: str,
    mode: str,
    duration: Optional[float],
    segments: list[TranscriptionSegment],
) -> db_models.Transcript:
    repo = TranscriptRepository(db, get_vector_store_client())
    extra = {
        "model": model,
        "mode": mode,
        "duration_seconds": duration,
        "segments": [segment.dict() for segment in segments],
    }
    return repo.create(
        video_id=video_id,
        language=language,
        content=response_text,
        extra=extra,
    )


def _save_summary_record(
    *,
    db: Session,
    video_id: UUID,
    structure: SummaryStructure,
    model: str,
) -> db_models.Summary:
    repo = SummaryRepository(db)
    data = structure.dict()
    data["_meta"] = {"model": model}
    return repo.upsert_for_video(
        video_id=video_id,
        title=structure.title,
        data=data,
    )


def _build_video_detail_response(
    *,
    video: db_models.Video,
    transcript: Optional[db_models.Transcript],
    summary: Optional[db_models.Summary],
) -> VideoDetailResponse:
    return VideoDetailResponse(
        id=str(video.id),
        title=video.title,
        source_url=video.source_url,
        provider=video.provider,
        status=video.status,
        audio_path=video.audio_path,
        created_at=video.created_at,
        transcript=_build_stored_transcript(transcript) if transcript else None,
        summary=_build_stored_summary(summary) if summary else None,
    )


def _build_stored_transcript(transcript: db_models.Transcript) -> StoredTranscript:
    extra = transcript.extra or {}
    segments_data = extra.get("segments", [])
    segments: list[TranscriptionSegment] = []
    for seg in segments_data:
        try:
            segments.append(
                TranscriptionSegment(
                    start=float(seg.get("start", 0.0)),
                    end=float(seg.get("end", 0.0)),
                    text=str(seg.get("text", "")),
                )
            )
        except (TypeError, ValueError):
            continue

    return StoredTranscript(
        id=str(transcript.id),
        language=transcript.language,
        text=transcript.content,
        model=extra.get("model"),
        created_at=transcript.created_at,
        segments=segments,
    )


def _build_stored_summary(summary: db_models.Summary) -> StoredSummary:
    data = dict(summary.data or {})
    meta = data.pop("_meta", {}) if isinstance(data, dict) else {}
    try:
        structure = SummaryStructure(**data)
    except Exception:  # noqa: BLE001
        structure = SummaryStructure(
            title=summary.title,
            overview="",
            key_points=[],
            quotes=[],
            recommendations=[],
            tags=[],
        )

    return StoredSummary(
        id=str(summary.id),
        title=structure.title,
        structure=structure,
        model=meta.get("model"),
        created_at=summary.created_at,
    )


def _delete_video(
    *,
    db: Session,
    video: db_models.Video,
    transcript_repo: TranscriptRepository,
    summary_repo: SummaryRepository,
    storage: MediaStorage,
) -> None:
    video_uuid = video.id
    transcript_repo.delete_by_video(video_uuid)
    summary_repo.delete_by_video(video_uuid)

    if video.audio_path:
        settings = get_settings()
        media_location = MediaLocation(
            uri=video.audio_path,
            path=settings.data_audio_dir / video.audio_path,
        )
        try:
            storage.delete(media_location)
        except StorageError as exc:
            logger.warning(
                "Failed to delete media file for video",
                extra={"video_id": str(video_uuid), "error": str(exc)},
            )

    db.delete(video)


def _parse_video_id(raw_video_id: Optional[str]) -> Optional[UUID]:
    if not raw_video_id:
        return None
    try:
        return UUID(raw_video_id)
    except ValueError:
        logger.warning("Invalid video_id provided, skipping persistence", extra={"video_id": raw_video_id})
        return None


def _require_video_uuid(video_id: str) -> UUID:
    try:
        return UUID(video_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        ) from exc


async def _maybe_index_transcript(
    *,
    video_uuid: UUID,
    transcript_uuid: UUID,
    text: str,
    segments_raw: Iterable[dict] | None,
    indexer: TranscriptIndexer,
) -> None:
    if not text:
        return

    segments_payload = []
    if segments_raw:
        for seg in segments_raw:
            segments_payload.append(
                {
                    "text": seg.get("text", ""),
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                }
            )

    try:
        await run_in_threadpool(
            indexer.index_transcript,
            text,
            video_uuid,
            transcript_uuid,
            segments_payload if segments_payload else None,
        )
    except IndexingError as exc:
        logger.error(
            "Failed to index transcript",
            extra={"video_id": str(video_uuid), "error": str(exc)},
        )


@lru_cache()
def get_consultant_agent() -> ConsultantAgent:
    settings: Settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key is required for consultant agent")
    
    embedding_service = get_embedding_service()
    vector_store = get_vector_store_client()
    
    return ConsultantAgent(
        embedding_service=embedding_service,
        vector_store=vector_store,
        llm_api_key=settings.openai_api_key,
    )


app = create_app()

