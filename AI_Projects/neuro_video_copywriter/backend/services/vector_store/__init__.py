"""
@file: backend/services/vector_store/__init__.py
@description: Пакет для работы с Qdrant и векторным поиском.
@dependencies: backend.services.vector_store.client
@created: 2025-11-12
"""

from .client import VectorStoreClient, COLLECTION_NAME

__all__ = ["VectorStoreClient", "COLLECTION_NAME"]

