"""
@file: s3_storage.py
@description: S3-совместимое хранилище документов (MinIO / SberCloud Object Storage)
@dependencies: boto3
@created: 2024-12-19
"""

import os
from pathlib import Path
from typing import List, Optional, BinaryIO
from dataclasses import dataclass
from dotenv import load_dotenv

# Загружаем переменные окружения при импорте модуля
load_dotenv()

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
    BOTO3_IMPORT_ERROR = None
except ImportError as e:
    BOTO3_AVAILABLE = False
    BOTO3_IMPORT_ERROR = str(e)


@dataclass
class S3Config:
    """Конфигурация S3-хранилища"""
    endpoint_url: str
    access_key: str
    secret_key: str
    bucket_name: str
    region: Optional[str] = None


class S3DocumentStorage:
    """
    Хранилище документов в S3-совместимом хранилище.
    
    Поддерживает:
    - MinIO (для локальной разработки)
    - SberCloud Object Storage (для production)
    - Любое S3-совместимое хранилище
    """
    
    def __init__(self, config: Optional[S3Config] = None):
        """
        Инициализация S3 хранилища.
        
        Args:
            config: Конфигурация S3. Если None, загружается из переменных окружения.
        
        Raises:
            ImportError: Если boto3 не установлен
            ValueError: Если конфигурация неполная
        """
        if not BOTO3_AVAILABLE:
            error_msg = "boto3 is not installed. Install it with: pip install boto3"
            if BOTO3_IMPORT_ERROR:
                error_msg += f"\nOriginal error: {BOTO3_IMPORT_ERROR}"
            raise ImportError(error_msg)
        
        if config is None:
            config = self._load_config_from_env()
        
        self.config = config
        self._client = None
        self._ensure_bucket_exists()
    
    def _load_config_from_env(self) -> S3Config:
        """Загружает конфигурацию из переменных окружения"""
        endpoint_url = os.getenv("S3_ENDPOINT") or os.getenv("SBERCLOUD_STORAGE_ENDPOINT")
        access_key = os.getenv("S3_ACCESS_KEY") or os.getenv("SBERCLOUD_STORAGE_ACCESS_KEY")
        secret_key = os.getenv("S3_SECRET_KEY") or os.getenv("SBERCLOUD_STORAGE_SECRET_KEY")
        bucket_name = os.getenv("S3_BUCKET") or os.getenv("SBERCLOUD_STORAGE_BUCKET")
        region = os.getenv("S3_REGION")
        
        if not all([endpoint_url, access_key, secret_key, bucket_name]):
            raise ValueError(
                "S3 configuration is incomplete. "
                "Set S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET environment variables."
            )
        
        return S3Config(
            endpoint_url=endpoint_url,
            access_key=access_key,
            secret_key=secret_key,
            bucket_name=bucket_name,
            region=region
        )
    
    @property
    def client(self):
        """Lazy initialization S3 клиента"""
        if self._client is None:
            self._client = boto3.client(
                's3',
                endpoint_url=self.config.endpoint_url,
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                region_name=self.config.region
            )
        return self._client
    
    def _ensure_bucket_exists(self) -> None:
        """Создает bucket, если он не существует"""
        try:
            self.client.head_bucket(Bucket=self.config.bucket_name)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                # Bucket не существует, создаем
                try:
                    if self.config.region:
                        self.client.create_bucket(
                            Bucket=self.config.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.config.region}
                        )
                    else:
                        self.client.create_bucket(Bucket=self.config.bucket_name)
                except ClientError as create_error:
                    raise ValueError(
                        f"Failed to create bucket {self.config.bucket_name}: {create_error}"
                    )
            else:
                raise
    
    def upload_document(self, file_path: Path, object_key: Optional[str] = None) -> str:
        """
        Загружает документ в S3 хранилище.
        
        Args:
            file_path: Путь к локальному файлу
            object_key: Ключ объекта в S3 (если None, генерируется из file_path)
        
        Returns:
            S3 URI документа (s3://bucket/key)
        
        Raises:
            FileNotFoundError: Если файл не существует
            ClientError: Если загрузка не удалась
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if object_key is None:
            # Генерируем ключ на основе структуры директорий
            object_key = str(file_path).replace('\\', '/')
            # Убираем префикс data/NeuroDoc_Data/ если есть
            if 'NeuroDoc_Data/' in object_key:
                object_key = object_key.split('NeuroDoc_Data/')[-1]
        
        try:
            self.client.upload_file(
                str(file_path),
                self.config.bucket_name,
                object_key
            )
            return f"s3://{self.config.bucket_name}/{object_key}"
        except (ClientError, BotoCoreError) as e:
            raise RuntimeError(f"Failed to upload {file_path} to S3: {e}")
    
    def download_document(self, object_key: str, local_path: Path) -> None:
        """
        Скачивает документ из S3 хранилища.
        
        Args:
            object_key: Ключ объекта в S3
            local_path: Локальный путь для сохранения
        
        Raises:
            ClientError: Если скачивание не удалось
        """
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            self.client.download_file(
                self.config.bucket_name,
                object_key,
                str(local_path)
            )
        except (ClientError, BotoCoreError) as e:
            raise RuntimeError(f"Failed to download {object_key} from S3: {e}")
    
    def get_document_content(self, object_key: str) -> bytes:
        """
        Получает содержимое документа из S3 как bytes.
        
        Args:
            object_key: Ключ объекта в S3
        
        Returns:
            Содержимое файла в виде bytes
        
        Raises:
            ClientError: Если получение не удалось
        """
        try:
            response = self.client.get_object(
                Bucket=self.config.bucket_name,
                Key=object_key
            )
            return response['Body'].read()
        except (ClientError, BotoCoreError) as e:
            raise RuntimeError(f"Failed to get {object_key} from S3: {e}")
    
    def list_documents(self, prefix: str = "") -> List[str]:
        """
        Получает список документов по префиксу.
        
        Args:
            prefix: Префикс для фильтрации (например, "hr/" или "it/")
        
        Returns:
            Список ключей объектов
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=self.config.bucket_name,
                Prefix=prefix
            )
            return [obj['Key'] for obj in response.get('Contents', [])]
        except (ClientError, BotoCoreError) as e:
            raise RuntimeError(f"Failed to list objects with prefix {prefix}: {e}")
    
    def delete_document(self, object_key: str) -> None:
        """
        Удаляет документ из S3 хранилища.
        
        Args:
            object_key: Ключ объекта в S3
        
        Raises:
            ClientError: Если удаление не удалось
        """
        try:
            self.client.delete_object(
                Bucket=self.config.bucket_name,
                Key=object_key
            )
        except (ClientError, BotoCoreError) as e:
            raise RuntimeError(f"Failed to delete {object_key} from S3: {e}")
    
    def document_exists(self, object_key: str) -> bool:
        """
        Проверяет существование документа в S3.
        
        Args:
            object_key: Ключ объекта в S3
        
        Returns:
            True если документ существует, False иначе
        """
        try:
            self.client.head_object(
                Bucket=self.config.bucket_name,
                Key=object_key
            )
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                return False
            raise

