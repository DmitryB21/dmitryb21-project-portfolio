"""
@file: retriever.py
@description: Retriever - semantic search по Qdrant коллекции
@dependencies: qdrant_client, app.ingestion.embedding_service
@created: 2024-12-19
"""

from typing import List, Optional
from dataclasses import dataclass
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
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
        try:
            query_embedding = self.embedding_service.generate_embeddings([query])[0]
        except Exception as e:
            raise ValueError(f"Ошибка при генерации embedding: {str(e)}")
        
        # Выполняем поиск в Qdrant
        # Метод search возвращает список ScoredPoint напрямую
        try:
            # Используем метод search (доступен в qdrant-client >= 1.6.0)
            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=k
            )
        except AttributeError:
            # Если метод search недоступен, используем query_points с явным NearestQuery
            try:
                from qdrant_client.models import NearestQuery
                query_result = self.qdrant_client.query_points(
                    collection_name=self.collection_name,
                    query=NearestQuery(nearest=query_embedding),  # Явно используем NearestQuery с правильным полем
                    limit=k
                )
                # query_points возвращает объект QueryResponse с атрибутом points
                search_results = query_result.points if hasattr(query_result, 'points') else []
            except Exception as e2:
                raise ValueError(
                    f"Ошибка при поиске в Qdrant. Метод 'search' недоступен, и 'query_points' также не работает. "
                    f"Ошибка query_points: {str(e2)}. "
                    f"Проверьте версию qdrant-client (требуется >= 1.6.0)."
                )
        except Exception as e:
            raise ValueError(
                f"Ошибка при поиске в Qdrant: {str(e)}. "
                f"Проверьте, что Qdrant доступен и коллекция '{self.collection_name}' существует. "
                f"Убедитесь, что установлена актуальная версия qdrant-client (>= 1.6.0)."
            )
        
        # Преобразуем результаты в RetrievedChunk объекты
        # Qdrant search возвращает список ScoredPoint напрямую
        # query может возвращать объект с атрибутом points
        if isinstance(search_results, list):
            # Это результат search - список ScoredPoint
            points = search_results
        elif hasattr(search_results, 'points'):
            # Это результат query - объект с атрибутом points
            points = search_results.points
        else:
            # Неизвестный формат - пытаемся итерировать
            points = list(search_results) if search_results else []
        
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

