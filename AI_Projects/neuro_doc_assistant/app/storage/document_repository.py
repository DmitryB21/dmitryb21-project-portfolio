"""
@file: document_repository.py
@description: Репозиторий для работы с метаданными документов в PostgreSQL
@dependencies: sqlalchemy, psycopg2
@created: 2024-12-19
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

try:
    from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, BigInteger, text
    from sqlalchemy.orm import sessionmaker, Session
    
    # Для совместимости с SQLAlchemy 1.4 и 2.0
    try:
        from sqlalchemy.orm import declarative_base
    except ImportError:
        from sqlalchemy.ext.declarative import declarative_base
    
    SQLALCHEMY_AVAILABLE = True
    Base = declarative_base()
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Base = None
    Column = None
    String = None
    Integer = None
    DateTime = None
    JSON = None
    BigInteger = None
    text = None
    sessionmaker = None
    Session = None


if SQLALCHEMY_AVAILABLE:
    class DocumentModel(Base):
        """SQLAlchemy модель для таблицы documents"""
        __tablename__ = 'documents'
        
        id = Column(String, primary_key=True)
        file_path = Column(String(500), nullable=False)
        s3_key = Column(String(500), unique=True)
        category = Column(String(50))
        filename = Column(String(255), nullable=False)
        file_size = Column(BigInteger)
        mime_type = Column(String(100))
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        indexed_at = Column(DateTime)
        version = Column(Integer, default=1)
        doc_metadata = Column("metadata", JSON)  # Используем doc_metadata как имя атрибута, но колонка называется metadata
        embedding_mode = Column(String(50))
        embedding_dim = Column(Integer)
else:
    # Заглушка для случая, когда SQLAlchemy недоступен
    class DocumentModel:
        pass


@dataclass
class DocumentMetadata:
    """Метаданные документа"""
    id: Optional[str]
    file_path: str
    s3_key: Optional[str]
    category: str
    filename: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None
    version: int = 1
    metadata: Optional[Dict[str, Any]] = None
    embedding_mode: Optional[str] = None
    embedding_dim: Optional[int] = None


class DocumentRepository:
    """
    Репозиторий для работы с метаданными документов в PostgreSQL.
    
    Отвечает за:
    - Сохранение метаданных документов
    - Получение документов по категории, s3_key, id
    - Обновление статуса индексации
    - Поддержка fallback на in-memory хранилище для тестов
    """
    
    def __init__(self, db_url: Optional[str] = None, use_memory: bool = False):
        """
        Инициализация DocumentRepository.
        
        Args:
            db_url: URL PostgreSQL. Если None, загружается из DATABASE_URL.
            use_memory: Если True, используется in-memory хранилище (для тестов)
        """
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError(
                "sqlalchemy is not installed. "
                "Install it with: pip install sqlalchemy psycopg2-binary"
            )
        
        self.use_memory = use_memory
        
        if use_memory:
            # In-memory хранилище для тестов
            self._documents: Dict[str, DocumentMetadata] = {}
            self._session = None
        else:
            if db_url is None:
                db_url = os.getenv("DATABASE_URL")
                # Исправляем 127.0.0.1 на localhost для лучшей совместимости
                if db_url and "127.0.0.1" in db_url:
                    db_url = db_url.replace("127.0.0.1", "localhost")
            
            if not db_url:
                raise ValueError(
                    "DATABASE_URL is not set. "
                    "Set it in environment variables or pass db_url parameter."
                )
            
            try:
                self.engine = create_engine(db_url, pool_pre_ping=True)
                # Создаем таблицы если не существуют
                Base.metadata.create_all(self.engine)
                self.Session = sessionmaker(bind=self.engine)
            except Exception as e:
                raise RuntimeError(f"Failed to connect to PostgreSQL: {e}")
    
    def save_document(self, metadata: DocumentMetadata) -> str:
        """
        Сохраняет метаданные документа в БД.
        
        Args:
            metadata: Метаданные документа
        
        Returns:
            ID сохраненного документа
        """
        if self.use_memory:
            if not metadata.id:
                metadata.id = f"doc_{len(self._documents)}"
            self._documents[metadata.id] = metadata
            return metadata.id
        
        session = self.Session()
        try:
            # Проверяем существование по s3_key
            existing = None
            if metadata.s3_key:
                existing = session.query(DocumentModel).filter_by(s3_key=metadata.s3_key).first()
            
            if existing:
                # Обновляем существующий документ
                existing.file_path = metadata.file_path
                existing.category = metadata.category
                existing.filename = metadata.filename
                if metadata.file_size:
                    existing.file_size = metadata.file_size
                if metadata.mime_type:
                    existing.mime_type = metadata.mime_type
                if metadata.metadata:
                    existing.doc_metadata = metadata.metadata
                existing.updated_at = datetime.utcnow()
                doc_id = existing.id
            else:
                # Создаем новый документ
                doc_id = metadata.id or f"doc_{datetime.utcnow().timestamp()}"
                doc_model = DocumentModel(
                    id=doc_id,
                    file_path=metadata.file_path,
                    s3_key=metadata.s3_key,
                    category=metadata.category,
                    filename=metadata.filename,
                    file_size=metadata.file_size,
                    mime_type=metadata.mime_type,
                    doc_metadata=metadata.metadata,
                    embedding_mode=metadata.embedding_mode,
                    embedding_dim=metadata.embedding_dim
                )
                session.add(doc_model)
            
            session.commit()
            return doc_id
        except Exception as e:
            session.rollback()
            raise RuntimeError(f"Failed to save document: {e}")
        finally:
            session.close()
    
    def get_document_by_s3_key(self, s3_key: str) -> Optional[DocumentMetadata]:
        """
        Получает документ по S3 ключу.
        
        Args:
            s3_key: S3 ключ документа
        
        Returns:
            Метаданные документа или None
        """
        if self.use_memory:
            for doc in self._documents.values():
                if doc.s3_key == s3_key:
                    return doc
            return None
        
        session = self.Session()
        try:
            doc_model = session.query(DocumentModel).filter_by(s3_key=s3_key).first()
            if doc_model:
                return self._model_to_metadata(doc_model)
            return None
        finally:
            session.close()
    
    def get_documents_by_category(self, category: str) -> List[DocumentMetadata]:
        """
        Получает все документы указанной категории.
        
        Args:
            category: Категория документов (hr, it, compliance, etc.)
        
        Returns:
            Список метаданных документов
        """
        if self.use_memory:
            return [doc for doc in self._documents.values() if doc.category == category]
        
        session = self.Session()
        try:
            doc_models = session.query(DocumentModel).filter_by(category=category).all()
            return [self._model_to_metadata(doc) for doc in doc_models]
        finally:
            session.close()
    
    def mark_as_indexed(self, s3_key: str, embedding_mode: str, embedding_dim: int) -> None:
        """
        Отмечает документ как проиндексированный.
        
        Args:
            s3_key: S3 ключ документа
            embedding_mode: Режим embeddings (gigachat_api, mock)
            embedding_dim: Размерность embeddings
        """
        if self.use_memory:
            for doc in self._documents.values():
                if doc.s3_key == s3_key:
                    doc.indexed_at = datetime.utcnow()
                    doc.embedding_mode = embedding_mode
                    doc.embedding_dim = embedding_dim
            return
        
        session = self.Session()
        try:
            doc = session.query(DocumentModel).filter_by(s3_key=s3_key).first()
            if doc:
                doc.indexed_at = datetime.utcnow()
                doc.embedding_mode = embedding_mode
                doc.embedding_dim = embedding_dim
                session.commit()
        except Exception as e:
            session.rollback()
            raise RuntimeError(f"Failed to mark document as indexed: {e}")
        finally:
            session.close()
    
    def get_not_indexed_documents(self, category: Optional[str] = None) -> List[DocumentMetadata]:
        """
        Получает документы, которые еще не проиндексированы.
        
        Args:
            category: Опциональная фильтрация по категории
        
        Returns:
            Список метаданных неиндексированных документов
        """
        if self.use_memory:
            docs = [doc for doc in self._documents.values() if doc.indexed_at is None]
            if category:
                docs = [doc for doc in docs if doc.category == category]
            return docs
        
        session = self.Session()
        try:
            query = session.query(DocumentModel).filter(DocumentModel.indexed_at.is_(None))
            if category:
                query = query.filter_by(category=category)
            doc_models = query.all()
            return [self._model_to_metadata(doc) for doc in doc_models]
        finally:
            session.close()
    
    def _model_to_metadata(self, doc_model: DocumentModel) -> DocumentMetadata:
        """Преобразует SQLAlchemy модель в DocumentMetadata"""
        return DocumentMetadata(
            id=doc_model.id,
            file_path=doc_model.file_path,
            s3_key=doc_model.s3_key,
            category=doc_model.category,
            filename=doc_model.filename,
            file_size=doc_model.file_size,
            mime_type=doc_model.mime_type,
            created_at=doc_model.created_at,
            indexed_at=doc_model.indexed_at,
            version=doc_model.version or 1,
            metadata=doc_model.doc_metadata,
            embedding_mode=doc_model.embedding_mode,
            embedding_dim=doc_model.embedding_dim
        )

