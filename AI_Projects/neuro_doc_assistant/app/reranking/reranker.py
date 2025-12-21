"""
@file: reranker.py
@description: Reranker - переупорядочивание retrieved документов для повышения Precision@3
@dependencies: app.retrieval.retriever
@created: 2024-12-19
"""

from typing import List
from dataclasses import dataclass, field
from app.retrieval.retriever import RetrievedChunk
import re


@dataclass
class RerankedChunk:
    """
    Представление reranked чанка.
    
    Attributes:
        id: Идентификатор чанка
        text: Текст чанка
        score: Оригинальный score от Retriever
        rerank_score: Новый score после reranking
        metadata: Метаданные чанка
    """
    id: str
    text: str
    score: float
    rerank_score: float
    metadata: dict


class Reranker:
    """
    Reranker для переупорядочивания retrieved документов.
    
    Отвечает за:
    - Переупорядочивание retrieved чанков по релевантности к запросу
    - Повышение Precision@3 при большом объёме документов
    - Комбинацию оригинального semantic search score и keyword-based reranking
    """
    
    def __init__(self, keyword_weight: float = 0.3, original_score_weight: float = 0.7):
        """
        Инициализация Reranker.
        
        Args:
            keyword_weight: Вес keyword-based релевантности (0.0-1.0)
            original_score_weight: Вес оригинального semantic search score (0.0-1.0)
        """
        self.keyword_weight = keyword_weight
        self.original_score_weight = original_score_weight
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Извлечение ключевых слов из текста.
        
        Args:
            text: Текст для обработки
        
        Returns:
            Список ключевых слов (в нижнем регистре, без стоп-слов)
        """
        # Простые стоп-слова для русского языка
        stop_words = {
            "и", "в", "на", "с", "по", "для", "от", "до", "из", "к", "о", "об",
            "а", "но", "или", "как", "что", "это", "так", "уже", "еще", "ещё",
            "бы", "был", "была", "было", "были", "есть", "нет", "не", "ни",
            "то", "та", "те", "того", "той", "тем", "тому", "тому", "тому"
        }
        
        # Нормализация текста: нижний регистр, удаление знаков препинания
        text_lower = text.lower()
        words = re.findall(r'\b[а-яёa-z]+\b', text_lower)
        
        # Фильтрация стоп-слов и коротких слов
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords
    
    def _calculate_keyword_relevance(self, query: str, chunk_text: str) -> float:
        """
        Расчёт релевантности на основе ключевых слов.
        
        Args:
            query: Запрос пользователя
            chunk_text: Текст чанка
        
        Returns:
            Релевантность от 0.0 до 1.0
        """
        query_keywords = set(self._extract_keywords(query))
        chunk_keywords = set(self._extract_keywords(chunk_text))
        
        if not query_keywords:
            return 0.0
        
        # Jaccard similarity для ключевых слов
        intersection = query_keywords & chunk_keywords
        union = query_keywords | chunk_keywords
        
        if not union:
            return 0.0
        
        jaccard = len(intersection) / len(union)
        
        # Дополнительный бонус за точные совпадения фраз
        query_lower = query.lower()
        chunk_lower = chunk_text.lower()
        
        # Подсчёт количества слов запроса, найденных в чанке
        query_words = self._extract_keywords(query)
        found_words = sum(1 for word in query_words if word in chunk_lower)
        word_coverage = found_words / len(query_words) if query_words else 0.0
        
        # Комбинация Jaccard и word coverage
        relevance = 0.6 * jaccard + 0.4 * word_coverage
        
        return min(relevance, 1.0)
    
    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int = 3
    ) -> List[RerankedChunk]:
        """
        Переупорядочивание retrieved чанков по релевантности к запросу.
        
        Args:
            query: Запрос пользователя
            chunks: Список retrieved чанков от Retriever
            top_k: Количество чанков для возврата после reranking
        
        Returns:
            Список reranked чанков, отсортированных по rerank_score (убывание)
        """
        if not chunks:
            return []
        
        # Вычисляем rerank_score для каждого чанка
        reranked_chunks = []
        for chunk in chunks:
            keyword_relevance = self._calculate_keyword_relevance(query, chunk.text)
            
            # Комбинируем оригинальный score и keyword relevance
            rerank_score = (
                self.original_score_weight * chunk.score +
                self.keyword_weight * keyword_relevance
            )
            
            reranked_chunk = RerankedChunk(
                id=chunk.id,
                text=chunk.text,
                score=chunk.score,
                rerank_score=rerank_score,
                metadata=chunk.metadata
            )
            reranked_chunks.append(reranked_chunk)
        
        # Сортируем по rerank_score (убывание)
        reranked_chunks.sort(key=lambda x: x.rerank_score, reverse=True)
        
        # Возвращаем top_k
        return reranked_chunks[:top_k]

