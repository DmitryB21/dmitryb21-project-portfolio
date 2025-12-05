"""
Модуль для работы с эмбеддингами и векторным поиском
Интеграция с OpenAI и Qdrant
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import openai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import numpy as np
from config_utils import get_config

logger = logging.getLogger(__name__)

class EmbeddingProvider:
    """Абстрактный класс для провайдеров эмбеддингов"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
    
    async def get_embedding(self, text: str) -> List[float]:
        """Получить эмбеддинг для текста"""
        raise NotImplementedError
    
    def get_dimension(self) -> int:
        """Получить размерность эмбеддинга"""
        raise NotImplementedError

class FRIDAEmbeddingProvider(EmbeddingProvider):
    """Провайдер эмбеддингов на основе FRIDA (ai-forever/FRIDA)"""
    
    def __init__(self, model_name: str = "ai-forever/FRIDA", device: str = "cpu"):
        super().__init__(model_name)
        self.device = device
        self._frida_embedder = None
        self.dimension = 1536  # FRIDA размерность
    
    def _get_embedder(self):
        """Ленивая загрузка FRIDA embedder"""
        if self._frida_embedder is None:
            # Импортируем FRIDAEmbedder из topic_modeling_service
            from pro_mode.topic_modeling_service import FRIDAEmbedder
            self._frida_embedder = FRIDAEmbedder(
                model_name=self.model_name,
                device=self.device
            )
        return self._frida_embedder
    
    async def get_embedding(self, text: str) -> List[float]:
        """Получить эмбеддинг для текста через FRIDA с режимом search_query"""
        embedder = self._get_embedder()
        
        try:
            # Используем синхронную модель в асинхронном контексте
            import asyncio
            import concurrent.futures
            
            def encode_sync():
                # Используем режим search_query для поисковых запросов
                embeddings = embedder.encode([text], mode="search_query")
                return embeddings[0] if embeddings else []
            
            # Выполняем в отдельном потоке
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                embedding = await loop.run_in_executor(executor, encode_sync)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Ошибка получения эмбеддинга через FRIDA: {e}")
            raise
    
    async def get_embedding_for_classification(self, text: str) -> List[float]:
        """Получить эмбеддинг для классификации через FRIDA с режимом categorize_topic"""
        embedder = self._get_embedder()
        
        try:
            # Используем синхронную модель в асинхронном контексте
            import asyncio
            import concurrent.futures
            
            def encode_sync():
                # Используем режим categorize_topic для классификации тем
                embeddings = embedder.encode([text], mode="categorize_topic")
                return embeddings[0] if embeddings else []
            
            # Выполняем в отдельном потоке
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                embedding = await loop.run_in_executor(executor, encode_sync)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Ошибка получения эмбеддинга для классификации через FRIDA: {e}")
            raise
    
    def get_dimension(self) -> int:
        """Получить размерность эмбеддингов"""
        return self.dimension

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Провайдер эмбеддингов OpenAI"""
    
    def __init__(self, api_key: str, model_name: str = "text-embedding-3-large"):
        super().__init__(model_name)
        # Инициализация клиента OpenAI (совместимость с openai>=1)
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=api_key)
        except Exception:
            # Fallback на синхронный клиент с обёрткой
            openai.api_key = api_key
            self.client = None
        self.dimension = 3072 if "3-large" in model_name else 1536
    
    async def get_embedding(self, text: str) -> List[float]:
        """Получить эмбеддинг через OpenAI API"""
        try:
            if self.client is not None:
                response = await self.client.embeddings.create(
                    model=self.model_name,
                    input=text,
                    encoding_format="float"
                )
                return response.data[0].embedding
            # Синхронный fallback
            response = openai.embeddings.create(model=self.model_name, input=text)
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Ошибка получения эмбеддинга OpenAI: {e}")
            raise
    
    def get_dimension(self) -> int:
        return self.dimension

class QdrantManager:
    """Менеджер для работы с Qdrant"""
    
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = QdrantClient(
            host=host, 
            port=port,
            timeout=30.0  # Увеличиваем таймаут до 30 секунд
        )
        # Старая коллекция telegram_messages больше не используется
        # Теперь используется posts_search (FRIDA) для поиска
        self.collection_name = "posts_search"  # По умолчанию используем коллекцию FRIDA
    
    async def create_collection(self, vector_size: int):
        """Создать коллекцию в Qdrant или пересоздать, если размерность не совпадает"""
        import asyncio
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Проверим наличие коллекции
                collections = self.client.get_collections().collections
                collection_exists = any(c.name == self.collection_name for c in collections)
                
                if collection_exists:
                    # Проверяем размерность существующей коллекции
                    try:
                        collection_info = self.client.get_collection(self.collection_name)
                        # Получаем размерность - поддерживаем разные структуры API
                        try:
                            # Новый формат API
                            existing_size = collection_info.config.params.vectors.size
                        except AttributeError:
                            try:
                                # Альтернативный формат
                                existing_size = collection_info.config.vectors.size
                            except AttributeError:
                                # Если не удалось получить размерность, пересоздаем коллекцию
                                raise ValueError("Не удалось определить размерность коллекции")
                        
                        if existing_size != vector_size:
                            logger.warning(
                                f"⚠️ Размерность коллекции {self.collection_name} не совпадает: "
                                f"ожидается {vector_size}, найдено {existing_size}. "
                                f"Пересоздаю коллекцию..."
                            )
                            # Удаляем старую коллекцию
                            self.client.delete_collection(collection_name=self.collection_name)
                            logger.info(f"🗑️ Старая коллекция {self.collection_name} удалена")
                            # Создаем новую с правильной размерностью
                            self.client.create_collection(
                                collection_name=self.collection_name,
                                vectors_config=VectorParams(
                                    size=vector_size,
                                    distance=Distance.COSINE
                                )
                            )
                            logger.info(f"✅ Коллекция {self.collection_name} пересоздана с размерностью {vector_size}")
                        else:
                            logger.info(f"✅ Коллекция {self.collection_name} существует с правильной размерностью {vector_size}")
                        return
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось проверить размерность коллекции: {e}. Пересоздаю...")
                        # Пытаемся удалить и пересоздать
                        try:
                            if self.client.collection_exists(collection_name=self.collection_name):
                                self.client.delete_collection(collection_name=self.collection_name)
                                logger.info(f"🗑️ Коллекция {self.collection_name} удалена для пересоздания")
                        except Exception as del_e:
                            logger.warning(f"⚠️ Ошибка при удалении коллекции: {del_e}")
                        # Создаем новую
                        self.client.create_collection(
                            collection_name=self.collection_name,
                            vectors_config=VectorParams(
                                size=vector_size,
                                distance=Distance.COSINE
                            )
                        )
                        logger.info(f"✅ Коллекция {self.collection_name} создана с размерностью {vector_size}")
                        return
                else:
                    # Коллекции нет, создаем новую
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(
                            size=vector_size,
                            distance=Distance.COSINE
                        )
                    )
                    logger.info(f"✅ Коллекция {self.collection_name} создана с размерностью {vector_size}")
                    return
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1}/{max_retries} создания коллекции неудачна: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Экспоненциальная задержка: 1, 2, 4 секунды
                    logger.info(f"Повторная попытка через {wait_time} секунд...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Ошибка создания/получения коллекции после {max_retries} попыток: {e}")
                    raise
    
    async def upsert_embedding(self, point_id: str, vector: List[float], payload: Dict[str, Any]):
        """Добавить/обновить эмбеддинг в коллекции"""
        try:
            point = PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            )
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            logger.debug(f"Эмбеддинг {point_id} добавлен в Qdrant")
        except Exception as e:
            logger.error(f"Ошибка добавления эмбеддинга: {e}")
            raise
    
    async def get_collections(self):
        """Получить список коллекций (тонкая обёртка над клиентом)"""
        try:
            return self.client.get_collections()
        except Exception as e:
            logger.error(f"Ошибка получения списка коллекций Qdrant: {e}")
            raise

    async def count_points(self, collection_name: str, exact: bool = True) -> int:
        """Подсчитать количество точек в коллекции"""
        try:
            result = self.client.count(collection_name=collection_name, exact=exact)
            # В разных версиях клиента возвращается объект CountResult или dict
            try:
                return int(result.count)  # CountResult
            except AttributeError:
                if isinstance(result, dict):
                    return int(result.get('count', 0))
                # Попробуем доступ как к объекту с атрибутом value/count
                return int(getattr(result, 'value', 0))
        except Exception as e:
            logger.error(f"Ошибка подсчёта точек в коллекции '{collection_name}': {e}")
            return 0

    async def search_similar(self, query_vector: List[float], limit: int = 10, 
                           filters: Optional[Dict[str, Any]] = None,
                           collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Поиск похожих векторов
        
        Args:
            query_vector: Вектор запроса
            limit: Максимальное количество результатов
            filters: Фильтры для поиска
            collection_name: Имя коллекции (если None, используется self.collection_name)
        """
        # Используем указанную коллекцию или коллекцию по умолчанию
        target_collection = collection_name or self.collection_name
        
        try:
            
            search_filter = None
            if filters:
                conditions = []
                if 'channel_id' in filters:
                    conditions.append(
                        FieldCondition(key="channel_id", match=MatchValue(value=filters['channel_id']))
                    )
                if 'date_from' in filters:
                    conditions.append(
                        FieldCondition(key="date", range={"gte": filters['date_from']})
                    )
                if 'date_to' in filters:
                    conditions.append(
                        FieldCondition(key="date", range={"lte": filters['date_to']})
                    )
                if 'topic_id' in filters:
                    conditions.append(
                        FieldCondition(key="topic_id", match=MatchValue(value=filters['topic_id']))
                    )
                if conditions:
                    search_filter = Filter(must=conditions)
            
            # Используем query_points вместо search (новый API Qdrant)
            query_response = self.client.query_points(
                collection_name=target_collection,
                query=query_vector,
                limit=limit,
                query_filter=search_filter
            )
            
            return [
                {
                    'id': result.id,
                    'score': result.score,
                    'payload': result.payload
                }
                for result in query_response.points
            ]
        except Exception as e:
            logger.error(f"Ошибка поиска в Qdrant (коллекция {target_collection}): {e}")
            raise
    
    async def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Получить информацию о коллекции"""
        try:
            info = self.client.get_collection(collection_name)
            # В новых версиях Qdrant vectors_count может отсутствовать, используем points_count
            vectors_count = getattr(info, 'vectors_count', info.points_count)
            return {
                "points_count": info.points_count,
                "vectors_count": vectors_count,
                "status": getattr(info, 'status', None),
                "optimizer_status": getattr(info, 'optimizer_status', None)
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о коллекции: {e}")
            return {"points_count": 0, "vectors_count": 0}

    async def delete_collection(self, collection_name: str):
        """Удалить коллекцию в Qdrant"""
        try:
            if self.client.collection_exists(collection_name=collection_name):
                self.client.delete_collection(collection_name=collection_name)
                logger.info(f"Коллекция {collection_name} удалена")
            else:
                logger.info(f"Коллекция {collection_name} не существует")
        except Exception as e:
            logger.error(f"Ошибка удаления коллекции {collection_name}: {e}")
            raise

class EmbeddingService:
    """Сервис для работы с эмбеддингами"""
    
    def __init__(self):
        config = get_config()
        # Безопасное чтение из configparser
        api_key = ''
        embedding_model = 'text-embedding-3-large'
        qdrant_host = 'localhost'
        qdrant_port = 6333

        try:
            if 'openai' in config:
                api_key = config['openai'].get('api_key', api_key)
                embedding_model = config['openai'].get('embedding_model', embedding_model)
            if 'qdrant' in config:
                qdrant_host = config['qdrant'].get('host', qdrant_host)
                qdrant_port = int(config['qdrant'].get('port', qdrant_port))
        except Exception:
            # Если по каким-то причинам структура конфигурации неожиданная, используем значения по умолчанию
            pass

        # Для поиска используем FRIDA, для индексации - локальный провайдер (legacy)
        # Получаем настройки FRIDA из конфига
        frida_device = "cpu"
        try:
            if 'topic_modeling' in config:
                frida_device = config['topic_modeling'].get('frida_device', 'cpu')
        except Exception:
            pass
        
        logger.info(f"Используется FRIDA провайдер эмбеддингов для поиска (ai-forever/FRIDA, device={frida_device})")
        self.provider = FRIDAEmbeddingProvider(device=frida_device)
        self.qdrant = QdrantManager(
            host=qdrant_host,
            port=qdrant_port
        )
    
    async def initialize(self):
        """Инициализация сервиса"""
        await self.qdrant.create_collection(self.provider.get_dimension())
    
    async def process_message(self, message_id: int, text: str, channel_id: int, 
                            published_at: str) -> str:
        """Обработать сообщение: создать эмбеддинг и сохранить в Qdrant"""
        try:
            # Получаем эмбеддинг
            embedding = await self.provider.get_embedding(text)
            
            # Формируем payload для Qdrant
            payload = {
                'message_id': message_id,
                'channel_id': channel_id,
                'date': published_at,
                'text_preview': text[:200] + "..." if len(text) > 200 else text
            }
            
            # Сохраняем в Qdrant (используем message_id как числовой ID)
            await self.qdrant.upsert_embedding(message_id, embedding, payload)
            logger.debug(f"✅ Эмбеддинг для сообщения {message_id} добавлен в Qdrant")
            
            # Сохраняем метаданные в PostgreSQL
            await self._save_embedding_metadata(message_id, embedding)
            
            logger.info(f"✅ Сообщение {message_id} успешно обработано: эмбеддинг добавлен в Qdrant и метаданные сохранены в PostgreSQL")
            return str(message_id)
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения {message_id}: {e}")
            raise
    
    async def search_semantic(self, query: str, limit: int = 10, 
                            filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Семантический поиск с использованием FRIDA
        
        Использует FRIDA с режимом search_query для запросов
        и ищет в коллекции posts_search, где документы индексированы через FRIDA с режимом search_document
        """
        try:
            # Получаем эмбеддинг запроса через FRIDA с режимом search_query
            query_embedding = await self.provider.get_embedding(query)
            
            # Ищем в коллекции posts_search (где индексируются документы через FRIDA)
            results = await self.qdrant.search_similar(
                query_embedding, 
                limit, 
                filters,
                collection_name="posts_search"  # Используем коллекцию с FRIDA эмбеддингами
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка семантического поиска: {e}")
            raise
    
    async def _save_embedding_metadata(self, message_id: int, embedding: List[float]) -> None:
        """Сохранить метаданные эмбеддинга в PostgreSQL"""
        try:
            config = get_config()
            import asyncpg
            
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Проверяем, существует ли сообщение в базе
            message_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM messages WHERE id = $1)",
                message_id
            )
            
            if not message_exists:
                logger.warning(f"⚠️ Сообщение {message_id} не найдено в таблице messages, пропускаем сохранение метаданных")
                await conn.close()
                return
            
            # Сохраняем запись о том, что эмбеддинг создан
            await conn.execute("""
                INSERT INTO embeddings (message_id, model, vector_id, embedding_dim)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (message_id, model) DO UPDATE SET
                    vector_id = EXCLUDED.vector_id,
                    embedding_dim = EXCLUDED.embedding_dim,
                    created_at = NOW()
            """, 
            message_id, 
            self.provider.model_name, 
            str(message_id),  # vector_id в Qdrant
            len(embedding)    # размерность вектора
            )
            
            await conn.close()
            logger.debug(f"✅ Метаданные эмбеддинга для сообщения {message_id} сохранены в PostgreSQL")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения метаданных эмбеддинга для сообщения {message_id}: {e}")
            import traceback
            logger.debug(f"Трассировка: {traceback.format_exc()}")

# Глобальный экземпляр сервиса
embedding_service = EmbeddingService()
