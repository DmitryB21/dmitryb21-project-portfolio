"""
@file: metadata_filter.py
@description: MetadataFilter - фильтрация retrieved чанков по метаданным
@dependencies: app.retrieval.retriever
@created: 2024-12-19
"""

from typing import List, Optional
from app.retrieval.retriever import RetrievedChunk


class MetadataFilter:
    """
    Фильтр для retrieved чанков по метаданным.
    
    Отвечает за:
    - Фильтрацию по source (hr, it, compliance)
    - Фильтрацию по category
    - Фильтрацию по file_path
    - Фильтрацию по metadata_tags
    - Комбинированную фильтрацию по нескольким критериям
    """
    
    def __init__(self):
        """Инициализация MetadataFilter"""
        pass
    
    def filter(
        self,
        chunks: List[RetrievedChunk],
        source: Optional[str] = None,
        category: Optional[str] = None,
        file_path: Optional[str] = None,
        metadata_tag: Optional[str] = None
    ) -> List[RetrievedChunk]:
        """
        Фильтрует чанки по метаданным.
        
        Args:
            chunks: Список RetrievedChunk объектов для фильтрации
            source: Фильтр по source (hr, it, compliance)
            category: Фильтр по category
            file_path: Фильтр по file_path (частичное совпадение)
            metadata_tag: Фильтр по metadata_tags (должен содержать указанный тег)
            
        Returns:
            Отфильтрованный список RetrievedChunk объектов (порядок сохраняется)
        """
        if not chunks:
            return []
        
        filtered = chunks
        
        # Фильтрация по source
        if source is not None:
            filtered = [chunk for chunk in filtered if chunk.metadata.get("source") == source]
        
        # Фильтрация по category
        if category is not None:
            filtered = [chunk for chunk in filtered if chunk.metadata.get("category") == category]
        
        # Фильтрация по file_path (частичное совпадение)
        if file_path is not None:
            filtered = [
                chunk for chunk in filtered
                if file_path in chunk.metadata.get("file_path", "")
            ]
        
        # Фильтрация по metadata_tag
        if metadata_tag is not None:
            filtered = [
                chunk for chunk in filtered
                if metadata_tag in chunk.metadata.get("metadata_tags", [])
            ]
        
        return filtered

