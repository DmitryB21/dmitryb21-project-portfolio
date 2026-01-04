"""
@file: indexer.py
@description: QdrantIndexer - индексация чанков в Qdrant
@dependencies: qdrant_client
@created: 2024-12-19
"""

from datetime import datetime
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct


class QdrantIndexer:
    """
    Индексатор для загрузки чанков в Qdrant.
    
    Отвечает за:
    - Создание коллекции neuro_docs (если не существует)
    - Загрузку чанков с векторами и метаданными в Qdrant
    - Структуру метаданных payload (7 обязательных полей + опциональный experiment_id)
    """
    
    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str = "neuro_docs",
        embedding_dim: int = 1536
    ):
        """
        Инициализация QdrantIndexer.
        
        Args:
            qdrant_client: Клиент Qdrant
            collection_name: Имя коллекции (по умолчанию "neuro_docs")
            embedding_dim: Размерность векторов (1536 или 1024)
        """
        self.client = qdrant_client
        self.qdrant_client = qdrant_client  # Для совместимости с тестами
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
    
    def index_chunks(
        self,
        chunks: List,
        embeddings: List[List[float]],
        collection_name: Optional[str] = None
    ) -> None:
        """
        Индексирует чанки в Qdrant.
        
        Args:
            chunks: Список Chunk объектов
            embeddings: Список векторов embeddings (соответствует chunks)
            collection_name: Имя коллекции (если None, используется self.collection_name)
            
        Raises:
            ValueError: Если количество chunks и embeddings не совпадает
            Exception: При ошибках Qdrant
        """
        if len(chunks) != len(embeddings):
            raise ValueError(f"Chunks count ({len(chunks)}) != embeddings count ({len(embeddings)})")
        
        if not chunks:
            return  # Нет чанков для индексации
        
        collection = collection_name or self.collection_name
        
        # Создаём коллекцию, если не существует
        self._ensure_collection_exists(collection)
        
        # Подготавливаем точки для загрузки
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point = self._create_point(chunk, embedding)
            points.append(point)
        
        # Загружаем точки в Qdrant
        try:
            self.client.upsert(
                collection_name=collection,
                points=points
            )
        except Exception as e:
            raise Exception(f"Error indexing chunks to Qdrant: {e}")
    
    def _ensure_collection_exists(self, collection_name: str) -> None:
        """
        Создаёт коллекцию в Qdrant, если она не существует.
        
        Args:
            collection_name: Имя коллекции
        """
        try:
            # Проверяем, существует ли коллекция
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if collection_name not in collection_names:
                # Создаём коллекцию с нужными параметрами
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dim,
                        distance=Distance.COSINE
                    )
                )
        except Exception as e:
            # Если коллекция уже существует или другая ошибка
            # Пытаемся продолжить (может быть race condition)
            pass
    
    def _create_point(self, chunk, embedding: List[float]) -> PointStruct:
        """
        Создаёт точку PointStruct для Qdrant из чанка и embedding.
        
        Args:
            chunk: Chunk объект
            embedding: Вектор embedding
            
        Returns:
            PointStruct для загрузки в Qdrant
        """
        # Формируем payload с полными метаданными
        payload = {
            "text": chunk.text,
            "doc_id": chunk.doc_id,
            "chunk_id": chunk.chunk_id,
            "source": chunk.metadata.get("source", chunk.metadata.get("category", "unknown")),
            "created_at": datetime.now().isoformat(),
            "text_length": chunk.text_length,
            "embedding_version": "GigaChat",  # Версия модели embeddings
            "metadata_tags": chunk.metadata.get("metadata_tags", []),
        }
        
        # Добавляем опциональные поля из метаданных
        if "file_path" in chunk.metadata:
            payload["file_path"] = chunk.metadata["file_path"]
        if "category" in chunk.metadata:
            payload["category"] = chunk.metadata["category"]
        if "experiment_id" in chunk.metadata:
            payload["experiment_id"] = chunk.metadata["experiment_id"]
        
        # Qdrant требует числовые ID или UUID
        # Преобразуем строковый chunk_id в числовой ID используя hash
        import hashlib
        point_id = int(hashlib.md5(chunk.chunk_id.encode('utf-8')).hexdigest()[:15], 16)
        # Ограничиваем до unsigned 64-bit integer (Qdrant поддерживает до 2^63-1)
        point_id = point_id % (2**63 - 1)
        
        # Создаём точку
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload=payload
        )
        
        return point

