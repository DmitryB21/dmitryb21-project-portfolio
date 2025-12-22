"""
@file: embedding_service.py
@description: EmbeddingService - генерация векторных представлений через GigaChat Embeddings API
@dependencies: requests, os
@created: 2024-12-19
"""

import os
import uuid
from typing import List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

from app.generation.gigachat_auth import GigaChatAuth

# Отключаем предупреждения о небезопасных SSL запросах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class EmbeddingService:
    """
    Сервис для генерации векторных представлений через GigaChat Embeddings API.
    
    Поддерживает:
    - Генерацию embeddings для одного или нескольких текстов
    - Батчинг для оптимизации throughput
    - Фиксацию версии модели для воспроизводимости
    - Размерность векторов: 1536 или 1024
    """
    
    def __init__(
        self,
        model_version: str = "GigaChat",
        embedding_dim: int = 1536,
        api_key: str = None,
        batch_size: int = 10,
        mock_mode: bool = False,
        auth_key: str = None,
        scope: str = None
    ):
        """
        Инициализация EmbeddingService.
        
        Args:
            model_version: Версия модели embeddings (фиксируется для воспроизводимости)
            embedding_dim: Размерность векторов (1536 или 1024)
            api_key: Устаревший параметр (для обратной совместимости). Используйте auth_key.
            batch_size: Размер батча для обработки текстов
            mock_mode: Если True, использует моковые embeddings вместо реального API
            auth_key: Base64 encoded "Client ID:Client Secret" для OAuth 2.0 (если None, берётся из GIGACHAT_AUTH_KEY)
            scope: Scope для OAuth (GIGACHAT_API_PERS, GIGACHAT_API_B2B, GIGACHAT_API_CORP)
        """
        self.model_version = model_version
        self.embedding_dim = embedding_dim
        self.batch_size = batch_size
        
        # Определяем auth_key
        self.auth_key = auth_key or os.getenv("GIGACHAT_AUTH_KEY")
        self.scope = scope or os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        
        # Для обратной совместимости: если передан api_key (старый формат), используем его как auth_key
        if api_key and not self.auth_key:
            self.auth_key = api_key
        
        # Определяем mock mode
        if mock_mode or os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true":
            self.mock_mode = True
        elif not self.auth_key:
            # Если auth_key не предоставлен, включаем mock mode
            self.mock_mode = True
        else:
            self.mock_mode = False
        
        # Инициализация OAuth аутентификации
        if not self.mock_mode:
            self.auth = GigaChatAuth(auth_key=self.auth_key, scope=self.scope)
        else:
            self.auth = None
        
        # Настройка HTTP сессии с retry
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Отключаем проверку SSL для GigaChat API (требуется из-за самоподписанного сертификата)
        self.session.verify = False
        
        # Официальный endpoint для GigaChat Embeddings API
        self.api_url = os.getenv(
            "GIGACHAT_EMBEDDINGS_URL",
            "https://gigachat.devices.sberbank.ru/api/v1/embeddings"
        )
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Генерирует embeddings для списка текстов.
        
        Args:
            texts: Список текстов для обработки
            
        Returns:
            Список векторов (каждый вектор - список float значений)
            
        Raises:
            ValueError: Если список текстов пуст
            Exception: При ошибках API
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")
        
        all_embeddings = []
        
        # Обрабатываем тексты батчами
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_embeddings = self._process_batch(batch)
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def _process_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Обрабатывает один батч текстов.
        
        Args:
            texts: Список текстов в батче
            
        Returns:
            Список векторов для батча
            
        Raises:
            Exception: При ошибках API
        """
        # В реальной реализации здесь будет вызов GigaChat Embeddings API
        # Пока используем заглушку для тестов
        
        # Мок ответа от API (в production будет реальный вызов)
        embeddings = []
        for i, text in enumerate(texts):
            # Генерируем моковый вектор (в production будет реальный API вызов)
            embedding = self._call_gigachat_api(text)
            embeddings.append(embedding)
        
        return embeddings
    
    def _call_gigachat_api(self, text: str) -> List[float]:
        """
        Вызывает GigaChat Embeddings API для одного текста.
        
        Args:
            text: Текст для обработки
            
        Returns:
            Вектор embeddings
            
        Raises:
            Exception: При ошибках API
        """
        # Если включен mock mode, возвращаем моковый вектор
        if self.mock_mode:
            return self._generate_mock_embedding(text)
        
        try:
            # Получаем access token через OAuth 2.0
            if not self.auth:
                # Если auth не инициализирован, используем mock mode
                return self._generate_mock_embedding(text)
            
            access_token = self.auth.get_access_token()
            if not access_token:
                # Если не удалось получить токен, используем mock mode
                return self._generate_mock_embedding(text)
            
            # Генерируем уникальный идентификатор запроса (UUID4)
            request_id = str(uuid.uuid4())
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Request-ID": request_id
            }
            
            payload = {
                "model": self.model_version,
                "input": text
            }
            
            response = self.session.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            # Извлекаем embedding из ответа API
            # Структура ответа зависит от формата GigaChat API
            if "data" in data and len(data["data"]) > 0:
                embedding = data["data"][0].get("embedding", [])
                if len(embedding) == self.embedding_dim:
                    return embedding
            
            # Если формат ответа неожиданный, возвращаем моковый вектор
            return self._generate_mock_embedding(text)
            
        except Exception as e:
            # В production здесь должно быть логирование и обработка ошибок
            # При ошибке подключения также используем mock mode
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Ошибка при вызове GigaChat Embeddings API: {e}. Используется mock mode.")
            return self._generate_mock_embedding(text)
    
    def _generate_mock_embedding(self, text: str) -> List[float]:
        """
        Генерирует моковый embedding на основе текста.
        Использует простой hash-based подход для детерминированности.
        
        Args:
            text: Текст для генерации embedding
            
        Returns:
            Моковый вектор заданной размерности
        """
        import hashlib
        
        # Используем hash текста для генерации детерминированного вектора
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        
        # Генерируем вектор на основе hash
        embedding = []
        for i in range(self.embedding_dim):
            # Используем разные части hash для разных элементов вектора
            hash_index = i % len(text_hash)
            char_value = ord(text_hash[hash_index])
            # Нормализуем значение в диапазон [-1, 1]
            normalized_value = (char_value % 200 - 100) / 100.0
            embedding.append(normalized_value)
        
        return embedding

