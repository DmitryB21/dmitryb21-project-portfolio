"""
@file: loader.py
@description: DocumentLoader - загрузка и нормализация документов из файловой системы и S3
@dependencies: pathlib, app.storage.s3_storage
@created: 2024-12-19
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import uuid
from dotenv import load_dotenv

# Загружаем переменные окружения при импорте модуля
load_dotenv()


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
    Загрузчик документов из файловой системы и S3-хранилища.
    
    Поддерживает:
    - Загрузку MD файлов из локальной файловой системы
    - Загрузку документов из S3-совместимого хранилища (MinIO, SberCloud Object Storage)
    - Нормализацию текста (удаление лишних пробелов, нормализация кодировок)
    - Извлечение метаданных (путь к файлу, категория: hr/it/compliance)
    """
    
    def __init__(self, storage_backend: str = "auto"):
        """
        Инициализация DocumentLoader.
        
        Args:
            storage_backend: Источник данных:
                - "local" - только локальная файловая система
                - "s3" - только S3 хранилище
                - "auto" - автоматический выбор (S3 если доступен, иначе local)
        """
        self.storage_backend = storage_backend
        self.s3_storage = None
        
        if storage_backend in ("s3", "auto"):
            try:
                from app.storage.s3_storage import S3DocumentStorage
                # Убеждаемся, что переменные окружения загружены
                load_dotenv()
                
                # Проверяем наличие всех необходимых переменных перед инициализацией
                required_vars = ["S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_BUCKET"]
                missing_vars = [var for var in required_vars if not os.getenv(var)]
                
                if missing_vars:
                    if storage_backend == "s3":
                        raise ValueError(f"Missing required S3 environment variables: {', '.join(missing_vars)}")
                    # В режиме auto просто переключаемся на local
                    self.storage_backend = "local"
                    self.s3_storage = None
                else:
                    # Пытаемся инициализировать S3 storage
                    try:
                        self.s3_storage = S3DocumentStorage()
                    except Exception as init_error:
                        # Логируем ошибку инициализации для отладки
                        if storage_backend == "s3":
                            raise
                        # В режиме auto переключаемся на local
                        self.storage_backend = "local"
                        self.s3_storage = None
                        # Сохраняем информацию об ошибке для диагностики
                        self._s3_init_error = str(init_error)
                        return
                    
                    if storage_backend == "auto":
                        # Проверяем доступность S3
                        try:
                            self.s3_storage.list_documents()
                            self.storage_backend = "s3"
                        except Exception as list_error:
                            # В режиме auto просто переключаемся на local без ошибки
                            self.storage_backend = "local"
                            self.s3_storage = None
                            # Сохраняем информацию об ошибке для диагностики
                            self._s3_list_error = str(list_error)
            except Exception as e:
                if storage_backend == "s3":
                    raise
                self.s3_storage = None
                if storage_backend == "auto":
                    self.storage_backend = "local"
                    # Сохраняем информацию об ошибке для диагностики
                    self._s3_init_error = str(e)
    
    def load_documents(self, path: str, category: Optional[str] = None) -> List[Document]:
        """
        Загружает документы из указанного пути (локального или S3).
        
        Args:
            path: Путь к файлу, директории или S3 префикс (например, "hr/" или "it/")
            category: Категория документов (hr, it, compliance, onboarding). 
                     Если None, определяется автоматически из path.
            
        Returns:
            Список Document объектов
            
        Raises:
            FileNotFoundError: Если путь не существует (для local)
            ValueError: Если путь невалиден или storage_backend не поддерживает операцию
        """
        if self.storage_backend == "s3" and self.s3_storage:
            return self._load_from_s3(path, category)
        else:
            return self._load_from_local(path, category)
    
    def _load_from_s3(self, prefix: str, category: Optional[str] = None) -> List[Document]:
        """
        Загружает документы из S3 хранилища.
        
        Args:
            prefix: S3 префикс (например, "hr/" или "it/")
            category: Категория документов. Если None, определяется из prefix.
        
        Returns:
            Список Document объектов
        """
        if not self.s3_storage:
            raise ValueError("S3 storage is not initialized")
        
        # Определяем категорию из prefix если не указана
        if category is None:
            category = self._determine_category_from_path(prefix)
        
        # Получаем список документов по префиксу
        s3_keys = self.s3_storage.list_documents(prefix=prefix)
        
        documents = []
        for s3_key in s3_keys:
            # Фильтруем только .md файлы
            if not s3_key.endswith('.md'):
                continue
            
            try:
                # Получаем содержимое из S3
                content_bytes = self.s3_storage.get_document_content(s3_key)
                text = content_bytes.decode('utf-8')
                
                # Нормализация текста
                normalized_text = self._normalize_text(text)
                
                # Извлечение метаданных
                filename = Path(s3_key).name
                metadata = {
                    "file_path": s3_key,
                    "s3_key": s3_key,
                    "category": category,
                    "filename": filename,
                    "source": "s3"
                }
                
                # Генерация уникального ID
                doc_id = self._generate_document_id_from_s3_key(s3_key)
                
                documents.append(Document(
                    id=doc_id,
                    text=normalized_text,
                    metadata=metadata
                ))
            except Exception as e:
                print(f"Error loading document {s3_key} from S3: {e}")
                continue
        
        return documents
    
    def _load_from_local(self, path: str, category: Optional[str] = None) -> List[Document]:
        """
        Загружает документы из локальной файловой системы.
        
        Args:
            path: Путь к файлу или директории
            category: Категория документов. Если None, определяется из path.
        
        Returns:
            Список Document объектов
        """
        path_obj = Path(path)
        
        if not path_obj.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        
        documents = []
        
        if path_obj.is_file():
            # Загрузка одного файла
            if path_obj.suffix.lower() == '.md':
                doc = self._load_single_file(path_obj, category)
                if doc:
                    documents.append(doc)
        elif path_obj.is_dir():
            # Загрузка всех MD файлов из директории
            md_files = list(path_obj.glob("*.md"))
            for md_file in md_files:
                doc = self._load_single_file(md_file, category)
                if doc:
                    documents.append(doc)
        else:
            raise ValueError(f"Path is neither file nor directory: {path}")
        
        return documents
    
    def _load_single_file(self, file_path: Path, category: Optional[str] = None) -> Optional[Document]:
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
            metadata = self._extract_metadata(file_path, category)
            
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
    
    def _extract_metadata(self, file_path: Path, category: Optional[str] = None) -> dict:
        """
        Извлекает метаданные из пути к файлу.
        
        Args:
            file_path: Путь к файлу
            category: Категория документа. Если None, определяется автоматически.
            
        Returns:
            Словарь с метаданными
        """
        # Определяем категорию на основе пути если не указана
        if category is None:
            category = self._determine_category(file_path)
        
        metadata = {
            "file_path": str(file_path),
            "category": category,
            "filename": file_path.name,
            "source": "local"
        }
        
        return metadata
    
    def _determine_category_from_path(self, path: str) -> str:
        """
        Определяет категорию документа из пути (для S3).
        
        Args:
            path: Путь или S3 ключ
            
        Returns:
            Категория: "hr", "it", "compliance", "onboarding" или "unknown"
        """
        path_lower = path.lower()
        
        if path_lower.startswith('hr/') or '/hr/' in path_lower:
            return "hr"
        elif path_lower.startswith('it/') or '/it/' in path_lower:
            return "it"
        elif path_lower.startswith('compliance/') or '/compliance/' in path_lower:
            return "compliance"
        elif path_lower.startswith('onboarding/') or '/onboarding/' in path_lower:
            return "onboarding"
        
        return "unknown"
    
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
    
    def _generate_document_id_from_s3_key(self, s3_key: str) -> str:
        """
        Генерирует уникальный идентификатор документа из S3 ключа.
        
        Args:
            s3_key: S3 ключ документа
        
        Returns:
            Уникальный ID документа
        """
        filename = Path(s3_key).stem
        unique_id = str(uuid.uuid4())[:8]
        return f"{filename}_{unique_id}"

