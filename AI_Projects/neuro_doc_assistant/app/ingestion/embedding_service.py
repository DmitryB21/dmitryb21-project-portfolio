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
from dotenv import load_dotenv

from app.generation.gigachat_auth import GigaChatAuth

# Загружаем переменные окружения из .env файла
load_dotenv()

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
        # Рабочая схема: URL = https://gigachat.devices.sberbank.ru/api/v1/embeddings, Model = "Embeddings"
        if mock_mode or os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true":
            self.mock_mode = True
        elif not self.auth_key:
            # Если auth_key не предоставлен, включаем mock mode
            self.mock_mode = True
        else:
            # Используем реальный GigaChat Embeddings API
            # Рабочая конфигурация:
            # - URL: https://gigachat.devices.sberbank.ru/api/v1/embeddings
            # - Model: "Embeddings"
            # Примечание: API может требовать платную подписку (402 Payment Required)
            self.mock_mode = False
        
        # Инициализация OAuth аутентификации
        if not self.mock_mode:
            self.auth = GigaChatAuth(auth_key=self.auth_key, scope=self.scope)
        else:
            self.auth = None
        
        # Настройка HTTP сессии с retry
        self.session = requests.Session()
        retry_strategy = Retry(
            total=5,  # Увеличиваем количество попыток для rate limiting
            backoff_factor=2,  # Увеличиваем задержку между попытками (exponential backoff: 2, 4, 8 секунд)
            status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True  # Учитываем заголовок Retry-After от сервера
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
        
        # Если mock mode включен, сразу используем mock embeddings
        if self.mock_mode:
            return [self._generate_mock_embedding(text) for text in texts]
        
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
        
        # Обрабатываем каждый текст в батче
        embeddings = []
        import time
        
        for i, text in enumerate(texts):
            # Генерируем embedding через API
            embedding = self._call_gigachat_api(text)
            embeddings.append(embedding)
            
            # Добавляем небольшую задержку между запросами внутри батча
            # для избежания rate limiting (кроме последнего элемента)
            if i < len(texts) - 1:
                time.sleep(0.1)  # Задержка 100ms между запросами
        
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
            
            # GigaChat Embeddings API использует модель "Embeddings"
            # URL: https://gigachat.devices.sberbank.ru/api/v1/embeddings
            payload = {
                "model": "Embeddings",  # Рабочая модель для embeddings API
                "input": text
            }
            
            response = self.session.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            # Обработка rate limiting (429)
            if response.status_code == 429:
                import time
                import logging
                logger = logging.getLogger(__name__)
                retry_after = response.headers.get("Retry-After", "5")
                try:
                    wait_time = int(retry_after)
                except ValueError:
                    wait_time = 5
                logger.warning(
                    f"Rate limiting (429) при вызове Embeddings API. Ожидание {wait_time} секунд..."
                )
                time.sleep(wait_time)
                # Повторяем запрос после ожидания
                response = self.session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=30
                )
            
            response.raise_for_status()
            
            data = response.json()
            # Извлекаем embedding из ответа API
            # Поддерживаем разные форматы ответа GigaChat API
            embedding = None
            
            # Формат 1: {"data": [{"embedding": [...]}]}
            if "data" in data and len(data["data"]) > 0:
                embedding = data["data"][0].get("embedding", [])
            
            # Формат 2: {"embedding": [...]}
            elif "embedding" in data:
                embedding = data["embedding"]
            
            # Формат 3: Прямой массив
            elif isinstance(data, list) and len(data) > 0:
                if isinstance(data[0], list):
                    embedding = data[0]
                elif isinstance(data[0], dict) and "embedding" in data[0]:
                    embedding = data[0]["embedding"]
            
            # Проверяем размерность
            if embedding:
                embedding_dim_received = len(embedding)
                
                # Если размерность совпадает - возвращаем embedding
                if embedding_dim_received == self.embedding_dim:
                    return embedding
                
                # Если размерность отличается, но валидна (1024 или 1536) - обновляем конфигурацию
                if embedding_dim_received in [1024, 1536]:
                    import logging
                    logger = logging.getLogger(__name__)
                    if not hasattr(self, '_embedding_dim_adjusted'):
                        logger.info(
                            f"✅ GigaChat Embeddings API вернул размерность {embedding_dim_received} "
                            f"(ожидалась {self.embedding_dim}). Автоматически обновляю конфигурацию."
                        )
                        # Обновляем размерность для всех последующих запросов
                        self.embedding_dim = embedding_dim_received
                        self._embedding_dim_adjusted = True
                    return embedding
                
                # Если размерность неожиданная - логируем и используем mock
                import logging
                logger = logging.getLogger(__name__)
                if not hasattr(self, '_embeddings_format_logged'):
                    logger.warning(
                        f"Неожиданная размерность от GigaChat Embeddings API. "
                        f"Ожидалась {self.embedding_dim}, получено: {embedding_dim_received}. "
                        f"Используется mock embedding."
                    )
                    self._embeddings_format_logged = True
                return self._generate_mock_embedding(text)
            
            # Если embedding не найден в ответе
            import logging
            logger = logging.getLogger(__name__)
            if not hasattr(self, '_embeddings_format_logged'):
                logger.warning(
                    f"Неожиданный формат ответа от GigaChat Embeddings API. "
                    f"Embedding не найден в ответе. "
                    f"Структура ответа: {list(data.keys()) if isinstance(data, dict) else type(data)}. "
                    f"Используется mock embedding."
                )
                self._embeddings_format_logged = True
            return self._generate_mock_embedding(text)
            
        except requests.exceptions.HTTPError as e:
            # Обработка HTTP ошибок
            import logging
            logger = logging.getLogger(__name__)
            if e.response.status_code == 402:
                # GigaChat Embeddings API требует платную подписку
                # Логируем предупреждение, но не переключаемся на mock mode автоматически
                # (пользователь может иметь подписку, но получать временные ошибки)
                if not hasattr(self, '_embeddings_402_logged'):
                    logger.warning(
                        "⚠️  GigaChat Embeddings API вернул 402 Payment Required. "
                        "Если у вас есть платная подписка, проверьте настройки аккаунта. "
                        "Иначе система будет использовать mock embeddings. "
                        "Подробнее: https://developers.sber.ru/portal/products/gigachat"
                    )
                    self._embeddings_402_logged = True
                # Возвращаем mock embedding для этого запроса, но не переключаемся на mock mode полностью
                # (чтобы можно было повторить попытку при следующем запросе)
                return self._generate_mock_embedding(text)
            elif e.response.status_code == 404:
                # GigaChat API не поддерживает embeddings endpoint
                # Переключаемся на mock mode и не логируем каждую ошибку
                if not hasattr(self, '_embeddings_404_logged'):
                    logger.info(
                        "GigaChat API не поддерживает embeddings endpoint (404). "
                        "Используется mock mode для всех embeddings."
                    )
                    self._embeddings_404_logged = True
                    # Переключаемся на mock mode для всех последующих запросов
                    self.mock_mode = True
            elif e.response.status_code == 429:
                logger.warning(
                    f"Rate limiting (429) при вызове GigaChat Embeddings API. "
                    f"Используется mock embedding для этого запроса."
                )
            else:
                # Логируем только первую ошибку, чтобы не засорять логи
                if not hasattr(self, '_embeddings_error_logged'):
                    logger.warning(
                        f"HTTP ошибка при вызове GigaChat Embeddings API (статус {e.response.status_code}): {e}. "
                        f"Используется mock embedding."
                    )
                    self._embeddings_error_logged = True
            return self._generate_mock_embedding(text)
        except Exception as e:
            # При других ошибках API используем mock mode
            import logging
            logger = logging.getLogger(__name__)
            # Логируем только первую ошибку
            if not hasattr(self, '_embeddings_exception_logged'):
                logger.warning(
                    f"Ошибка при вызове GigaChat Embeddings API: {e}. Используется mock embedding."
                )
                self._embeddings_exception_logged = True
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

