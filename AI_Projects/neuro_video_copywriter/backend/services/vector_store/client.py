"""
@file: backend/services/vector_store/client.py
@description: Клиент для взаимодействия с Qdrant (векторное хранилище).
@dependencies: qdrant-client, backend.config
@created: 2025-11-12
"""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse

from config import Settings, get_settings

COLLECTION_NAME = "transcript_chunks"


class VectorStoreClient:
    """Инкапсулирует логику работы с Qdrant."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = QdrantClient(
            url=self._settings.qdrant_url,
            api_key=self._settings.qdrant_api_key,
        )

    def ensure_collection(self, vector_size: int) -> None:
        try:
            exists = self._client.collection_exists(COLLECTION_NAME)
        except UnexpectedResponse as exc:
            if exc.status_code != 404:
                raise
            exists = False
        if exists:
            return
        self._client.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qdrant_models.VectorParams(size=vector_size, distance=qdrant_models.Distance.COSINE),
        )

    def upsert_transcript_chunks(self, video_id: UUID, transcript_id: UUID, chunks: Iterable[dict]) -> None:
        points = []
        for chunk in chunks:
            points.append(
                {
                    "id": chunk["id"],
                    "vector": chunk["vector"],
                    "payload": {
                        "video_id": str(video_id),
                        "transcript_id": str(transcript_id),
                        "text": chunk["text"],
                        "metadata": chunk.get("metadata", {}),
                    },
                }
            )
        if points:
            self._client.upsert(collection_name=COLLECTION_NAME, points=points)

    def delete_transcript_chunks(self, transcript_id: UUID) -> None:
        filter_selector = qdrant_models.FilterSelector(
            filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="transcript_id",
                        match=qdrant_models.MatchValue(value=str(transcript_id)),
                    )
                ]
            )
        )
        self._client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=filter_selector,
        )

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict]:
        results = self._client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
        )
        return [
            {
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results
        ]

