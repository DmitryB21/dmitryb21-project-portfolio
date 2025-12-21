"""
@file: chunker.py
@description: Chunker - разбиение документов на чанки с overlap
@dependencies: tiktoken (для GPT-style BPE токенизации)
@created: 2024-12-19
"""

from dataclasses import dataclass, field
from typing import List
import tiktoken


@dataclass
class Chunk:
    """
    Представление чанка документа.
    
    Attributes:
        chunk_id: Уникальный идентификатор чанка
        doc_id: Идентификатор исходного документа
        text: Текст чанка
        text_length: Длина текста в токенах
        metadata: Метаданные чанка (наследуются от документа)
    """
    chunk_id: str
    doc_id: str
    text: str
    text_length: int
    metadata: dict = field(default_factory=dict)


class Chunker:
    """
    Разбиение документов на чанки с overlap.
    
    Использует GPT-style BPE токенизацию для определения размера чанков.
    Поддерживает overlap 20–30% от размера чанка для сохранения контекста.
    """
    
    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        Инициализация Chunker.
        
        Args:
            encoding_name: Имя токенизатора (по умолчанию cl100k_base для GPT-4/GigaChat)
        """
        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except Exception:
            # Fallback на упрощённую токенизацию, если tiktoken недоступен
            self.encoding = None
    
    def chunk_documents(
        self,
        documents: List,
        chunk_size: int = 300,
        overlap_percent: float = 0.25
    ) -> List[Chunk]:
        """
        Разбивает документы на чанки.
        
        Args:
            documents: Список Document объектов
            chunk_size: Размер чанка в токенах (200–400)
            overlap_percent: Процент overlap между чанками (0.2–0.3)
            
        Returns:
            Список Chunk объектов
        """
        all_chunks = []
        
        for doc in documents:
            chunks = self._chunk_single_document(doc, chunk_size, overlap_percent)
            all_chunks.extend(chunks)
        
        return all_chunks
    
    def _chunk_single_document(
        self,
        document,
        chunk_size: int,
        overlap_percent: float
    ) -> List[Chunk]:
        """
        Разбивает один документ на чанки.
        
        Args:
            document: Document объект
            chunk_size: Размер чанка в токенах
            overlap_percent: Процент overlap
            
        Returns:
            Список Chunk объектов
        """
        text = document.text
        
        # Если текст короткий, возвращаем один чанк
        text_length = self._count_tokens(text)
        if text_length <= chunk_size:
            chunk_metadata = document.metadata.copy()
            if "source" not in chunk_metadata:
                chunk_metadata["source"] = chunk_metadata.get("category", "unknown")
            
            return [Chunk(
                chunk_id=f"{document.id}_chunk_000",
                doc_id=document.id,
                text=text,
                text_length=text_length,
                metadata=chunk_metadata
            )]
        
        # Вычисляем overlap в токенах
        overlap_tokens = int(chunk_size * overlap_percent)
        step_size = chunk_size - overlap_tokens
        
        chunks = []
        start = 0
        chunk_index = 0
        
        # Используем более простой подход: разбиваем по символам с учётом приблизительного размера токенов
        # Приблизительно: 1 токен ≈ 3 символа для русского текста
        chars_per_token = 3
        chunk_size_chars = chunk_size * chars_per_token
        overlap_chars = overlap_tokens * chars_per_token
        
        while start < len(text):
            # Определяем конец текущего чанка в символах
            end = min(start + chunk_size_chars, len(text))
            
            # Ищем границу предложения или слова около конца
            search_start = max(start, end - 100)
            for i in range(end, search_start, -1):
                if i < len(text) and text[i] in '.!\n':
                    end = i + 1
                    break
            
            # Извлекаем текст чанка
            chunk_text = text[start:end].strip()
            
            if chunk_text:  # Пропускаем пустые чанки
                chunk_tokens = self._count_tokens(chunk_text)
                
                # Копируем метаданные и добавляем source для совместимости с Qdrant
                chunk_metadata = document.metadata.copy()
                if "source" not in chunk_metadata:
                    chunk_metadata["source"] = chunk_metadata.get("category", "unknown")
                
                chunk = Chunk(
                    chunk_id=f"{document.id}_chunk_{chunk_index:03d}",
                    doc_id=document.id,
                    text=chunk_text,
                    text_length=chunk_tokens,
                    metadata=chunk_metadata
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # Перемещаемся на следующий чанк с учётом overlap
            if end >= len(text):
                break
            
            # Находим новую начальную позицию с учётом overlap
            new_start = max(start + 1, end - overlap_chars)
            # Ищем границу предложения или слова для более чистого разрыва
            for i in range(new_start, min(new_start + 50, end)):
                if i < len(text) and text[i] in '.!\n':
                    start = i + 1
                    break
            else:
                start = new_start
        
        return chunks
    
    def _count_tokens(self, text: str) -> int:
        """
        Подсчитывает количество токенов в тексте.
        
        Args:
            text: Текст для подсчёта
            
        Returns:
            Количество токенов
        """
        if self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception:
                pass
        
        # Fallback: более точный приблизительный подсчёт для русского текста
        # Для русского текста: примерно 1 токен на 2-3 символа
        # Учитываем пробелы и знаки препинания
        char_count = len(text)
        # Приблизительно: русские слова короче, чем английские в токенах
        return max(1, char_count // 3)
    
    def _find_chunk_end(self, text: str, start: int, chunk_size: int) -> int:
        """
        Находит конец чанка, стараясь не разрывать слова и предложения.
        
        Args:
            text: Текст
            start: Начальная позиция
            chunk_size: Размер чанка в токенах
            
        Returns:
            Позиция конца чанка
        """
        # Используем бинарный поиск для более точного определения конца чанка
        left = start
        right = len(text)
        best_end = start
        
        # Ищем позицию, где количество токенов примерно равно chunk_size
        while left < right:
            mid = (left + right) // 2
            segment = text[start:mid]
            tokens_count = self._count_tokens(segment)
            
            if tokens_count < chunk_size:
                best_end = mid
                left = mid + 1
            else:
                right = mid
        
        # Ищем границу предложения или слова около найденной позиции
        search_start = max(start, best_end - 200)  # Ищем в пределах 200 символов
        search_end = min(len(text), best_end + 200)
        
        # Ищем ближайшую границу предложения или слова
        for i in range(best_end, search_start, -1):
            if i < len(text) and text[i] in '.!\n':
                return i + 1
        
        for i in range(best_end, search_end):
            if i < len(text) and text[i] in '.!\n':
                return i + 1
        
        # Если граница не найдена, возвращаем найденную позицию
        return min(best_end, len(text))
    
    def _find_chunk_start(self, text: str, end: int, overlap_tokens: int) -> int:
        """
        Находит начальную позицию следующего чанка с учётом overlap.
        
        Args:
            text: Текст
            end: Конец предыдущего чанка
            overlap_tokens: Количество токенов для overlap
            
        Returns:
            Новая начальная позиция
        """
        # Идём назад от конца, чтобы найти начало overlap
        start = max(0, end - overlap_tokens * 4)  # Приблизительно
        
        # Ищем границу предложения или слова для более чистого разрыва
        for i in range(start, end):
            if text[i] in '.!\n':
                return i + 1
        
        return start

