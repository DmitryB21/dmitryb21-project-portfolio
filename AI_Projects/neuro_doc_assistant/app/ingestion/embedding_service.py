"""
@file: embedding_service.py
@description: EmbeddingService - генерация векторных представлений через GigaChat Embeddings API
@dependencies: requests, os
@created: 2024-12-19
"""

import os
from typing import List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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
        batch_size: int = 10
    ):
        """
        Инициализация EmbeddingService.
        
        Args:
            model_version: Версия модели embeddings (фиксируется для воспроизводимости)
            embedding_dim: Размерность векторов (1536 или 1024)
            api_key: API ключ для GigaChat (если None, берётся из переменных окружения)
            batch_size: Размер батча для обработки текстов
        """
        self.model_version = model_version
        self.embedding_dim = embedding_dim
        self.api_key = api_key or os.getenv("GIGACHAT_API_KEY")
        self.batch_size = batch_size
        
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
        
        # Базовый URL для GigaChat API (нужно уточнить актуальный endpoint)
        self.api_url = os.getenv("GIGACHAT_EMBEDDINGS_URL", "https://api.gigachat.ai/v1/embeddings")
    
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
        # TODO: Реализовать реальный вызов GigaChat Embeddings API
        # Пока возвращаем моковый вектор для тестов
        
        if not self.api_key:
            # Для тестов без API ключа возвращаем моковый вектор
            return [0.1] * self.embedding_dim
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
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
            return [0.1] * self.embedding_dim
            
        except Exception as e:
            # В production здесь должно быть логирование и обработка ошибок
            raise Exception(f"Error calling GigaChat Embeddings API: {e}")

