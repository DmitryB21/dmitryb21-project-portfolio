"""
@file: retriever.py
@description: Retriever - semantic search по Qdrant коллекции
@dependencies: qdrant_client, app.ingestion.embedding_service
@created: 2024-12-19
"""

from typing import List, Optional
from dataclasses import dataclass
from qdrant_client import QdrantClient
from app.ingestion.embedding_service import EmbeddingService


@dataclass
class RetrievedChunk:
    """
    Представление retrieved чанка из Qdrant.
    
    Attributes:
        id: Идентификатор чанка (chunk_id)
        text: Текст чанка
        score: Релевантность (0.0-1.0)
        metadata: Метаданные чанка (doc_id, source, category, file_path и др.)
    """
    id: str
    text: str
    score: float
    metadata: dict


class Retriever:
    """
    Retriever для semantic search по Qdrant.
    
    Отвечает за:
    - Semantic search по коллекции neuro_docs
    - Параметризацию K (количество retrieved чанков: 3, 5, 8)
    - Возврат релевантных чанков с метаданными и scores
    """
    
    def __init__(
        self,
        qdrant_client: QdrantClient,
        embedding_service: EmbeddingService,
        collection_name: str = "neuro_docs"
    ):
        """
        Инициализация Retriever.
        
        Args:
            qdrant_client: Клиент Qdrant
            embedding_service: Сервис для генерации embeddings запросов
            collection_name: Имя коллекции (по умолчанию "neuro_docs")
        """
        self.qdrant_client = qdrant_client
        self.embedding_service = embedding_service
        self.collection_name = collection_name
    
    def retrieve(
        self,
        query: str,
        k: int = 3,
        score_threshold: Optional[float] = None
    ) -> List[RetrievedChunk]:
        """
        Выполняет semantic search по Qdrant.
        
        Args:
            query: Текстовый запрос пользователя
            k: Количество retrieved чанков (3, 5, 8)
            score_threshold: Минимальный score для фильтрации (опционально)
            
        Returns:
            Список RetrievedChunk объектов, отсортированных по score (от большего к меньшему)
        """
        # Генерируем embedding для запроса
        query_embedding = self.embedding_service.generate_embeddings([query])[0]
        
        # Выполняем поиск в Qdrant
        search_results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=k
        )
        
        # Преобразуем результаты в RetrievedChunk объекты
        # Qdrant search возвращает объект с атрибутом points или список напрямую
        if hasattr(search_results, 'points'):
            points = search_results.points
        else:
            points = search_results
        
        retrieved_chunks = []
        for point in points:
            # Фильтруем по score_threshold, если указан
            if score_threshold is not None and point.score < score_threshold:
                continue
            
            # Извлекаем метаданные из payload
            payload = point.payload
            metadata = {
                "doc_id": payload.get("doc_id"),
                "chunk_id": payload.get("chunk_id", point.id),
                "source": payload.get("source"),
                "category": payload.get("category"),
                "file_path": payload.get("file_path"),
                "created_at": payload.get("created_at"),
                "text_length": payload.get("text_length"),
                "embedding_version": payload.get("embedding_version"),
                "metadata_tags": payload.get("metadata_tags", []),
            }
            
            # Добавляем опциональные поля
            if "experiment_id" in payload:
                metadata["experiment_id"] = payload["experiment_id"]
            
            chunk = RetrievedChunk(
                id=payload.get("chunk_id", point.id),
                text=payload.get("text", ""),
                score=point.score,
                metadata=metadata
            )
            
            retrieved_chunks.append(chunk)
        
        # Сортируем по score (от большего к меньшему)
        retrieved_chunks.sort(key=lambda x: x.score, reverse=True)
        
        return retrieved_chunks

