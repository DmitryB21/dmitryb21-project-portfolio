"""
@file: loader.py
@description: DocumentLoader - загрузка и нормализация документов из файловой системы
@dependencies: pathlib
@created: 2024-12-19
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import uuid


@dataclass
class Document:
    """
    Представление документа после загрузки.
    
    Attributes:
        id: Уникальный идентификатор документа
        text: Нормализованный текст документа
        metadata: Метаданные документа (category, file_path и др.)
    """
    id: str
    text: str
    metadata: dict


class DocumentLoader:
    """
    Загрузчик документов из файловой системы.
    
    Поддерживает:
    - Загрузку MD файлов
    - Нормализацию текста (удаление лишних пробелов, нормализация кодировок)
    - Извлечение метаданных (путь к файлу, категория: hr/it/compliance)
    """
    
    def __init__(self):
        """Инициализация DocumentLoader"""
        pass
    
    def load_documents(self, path: str) -> List[Document]:
        """
        Загружает документы из указанного пути.
        
        Args:
            path: Путь к файлу или директории с MD файлами
            
        Returns:
            Список Document объектов
            
        Raises:
            FileNotFoundError: Если путь не существует
            ValueError: Если путь невалиден
        """
        path_obj = Path(path)
        
        if not path_obj.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        
        documents = []
        
        if path_obj.is_file():
            # Загрузка одного файла
            if path_obj.suffix.lower() == '.md':
                doc = self._load_single_file(path_obj)
                if doc:
                    documents.append(doc)
        elif path_obj.is_dir():
            # Загрузка всех MD файлов из директории
            md_files = list(path_obj.glob("*.md"))
            for md_file in md_files:
                doc = self._load_single_file(md_file)
                if doc:
                    documents.append(doc)
        else:
            raise ValueError(f"Path is neither file nor directory: {path}")
        
        return documents
    
    def _load_single_file(self, file_path: Path) -> Optional[Document]:
        """
        Загружает один MD файл.
        
        Args:
            file_path: Путь к MD файлу
            
        Returns:
            Document объект или None, если файл не удалось загрузить
        """
        try:
            # Читаем файл с правильной кодировкой
            text = file_path.read_text(encoding='utf-8')
            
            # Нормализация текста
            normalized_text = self._normalize_text(text)
            
            # Извлечение метаданных
            metadata = self._extract_metadata(file_path)
            
            # Генерация уникального ID
            doc_id = self._generate_document_id(file_path)
            
            return Document(
                id=doc_id,
                text=normalized_text,
                metadata=metadata
            )
        except Exception as e:
            # Логируем ошибку, но не прерываем процесс
            print(f"Error loading file {file_path}: {e}")
            return None
    
    def _normalize_text(self, text: str) -> str:
        """
        Нормализует текст: удаляет лишние пробелы, нормализует кодировки.
        
        Args:
            text: Исходный текст
            
        Returns:
            Нормализованный текст
        """
        # Удаляем лишние пробелы (заменяем множественные пробелы на одинарные)
        text = re.sub(r' +', ' ', text)
        
        # Удаляем пробелы в начале и конце строк
        lines = [line.strip() for line in text.split('\n')]
        
        # Удаляем пустые строки в начале и конце
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        
        # Объединяем строки обратно
        normalized = '\n'.join(lines)
        
        # Удаляем пробелы в начале и конце всего текста
        normalized = normalized.strip()
        
        return normalized
    
    def _extract_metadata(self, file_path: Path) -> dict:
        """
        Извлекает метаданные из пути к файлу.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Словарь с метаданными
        """
        # Определяем категорию на основе пути
        category = self._determine_category(file_path)
        
        metadata = {
            "file_path": str(file_path),
            "category": category,
            "filename": file_path.name,
        }
        
        return metadata
    
    def _determine_category(self, file_path: Path) -> str:
        """
        Определяет категорию документа на основе пути и имени файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Категория: "hr", "it", "compliance" или "unknown"
        """
        path_str = str(file_path).lower()
        filename = file_path.name.lower()
        
        # Проверяем путь
        if '/hr/' in path_str or '\\hr\\' in path_str:
            return "hr"
        elif '/it/' in path_str or '\\it\\' in path_str:
            return "it"
        elif '/compliance/' in path_str or '\\compliance\\' in path_str:
            return "compliance"
        
        # Проверяем имя файла (префиксы)
        if filename.startswith('hr_') or 'hr_test' in filename or 'hr-' in filename:
            return "hr"
        elif filename.startswith('it_') or 'it_test' in filename or 'it-' in filename:
            return "it"
        elif filename.startswith('compliance_') or 'compliance-' in filename:
            return "compliance"
        
        return "unknown"
    
    def _generate_document_id(self, file_path: Path) -> str:
        """
        Генерирует уникальный идентификатор документа.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Уникальный ID документа
        """
        # Используем имя файла и UUID для уникальности
        filename = file_path.stem
        unique_id = str(uuid.uuid4())[:8]
        return f"{filename}_{unique_id}"

