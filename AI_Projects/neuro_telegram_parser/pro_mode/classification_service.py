"""
Модуль для классификации сообщений и онбординга пользователей
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncpg
from config_utils import get_config
from pro_mode.embedding_service import embedding_service

logger = logging.getLogger(__name__)

class ClassificationService:
    """Сервис для классификации сообщений по темам"""
    
    def __init__(self):
        self.confidence_threshold = 0.6  # Повышен для categorize_topic (рекомендуется 0.6-0.7)
        
        # Инициализируем провайдер эмбеддингов для классификации
        # Используется локальный провайдер (sentence-transformers)
        self.classification_provider = None
        self._init_embedding_provider()
        
        # Кеш эталонов тем
        self._topic_references_cache: Dict[int, List[float]] = {}
        self._topics_cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 3600  # 1 час
    
    def _init_embedding_provider(self):
        """Инициализация провайдера эмбеддингов для классификации"""
        try:
            # Используем FRIDA провайдер эмбеддингов
            from pro_mode.embedding_service import FRIDAEmbeddingProvider
            from config_utils import get_config
            config = get_config()
            frida_device = "cpu"
            try:
                if 'topic_modeling' in config:
                    frida_device = config['topic_modeling'].get('frida_device', 'cpu')
            except Exception:
                pass
            self.classification_provider = FRIDAEmbeddingProvider(device=frida_device)
            logger.info(f"Используется FRIDA провайдер эмбеддингов для классификации (device={frida_device})")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации провайдера эмбеддингов: {e}")
            # Fallback на FRIDA
            from pro_mode.embedding_service import FRIDAEmbeddingProvider
            self.classification_provider = FRIDAEmbeddingProvider(device="cpu")
    
    async def _prepare_topic_references(self) -> Dict[int, List[float]]:
        """Подготовить эталоны тем с использованием categorize_topic (с кешированием)"""
        # Проверяем кеш
        if (self._topics_cache_timestamp and 
            (datetime.now() - self._topics_cache_timestamp).total_seconds() < self._cache_ttl):
            logger.debug(f"Используются кешированные эталоны тем ({len(self._topic_references_cache)} тем)")
            return self._topic_references_cache
        
        # Получаем темы из БД
        topics = await self._get_all_topics()
        
        # Инициализируем провайдер
        if not self.classification_provider:
            from pro_mode.embedding_service import FRIDAEmbeddingProvider
            self.classification_provider = FRIDAEmbeddingProvider(device="cpu")
        
        # Создаем эталоны с categorize_topic
        logger.info(f"Подготовка эталонов тем с categorize_topic ({len(topics)} тем)...")
        references = {}
        
        # Батчинг для эффективности
        batch_size = 50
        for i in range(0, len(topics), batch_size):
            batch_topics = topics[i:i + batch_size]
            topic_texts = []
            topic_ids = []
            
            for topic in batch_topics:
                topic_description = topic.get('description', '') or ''
                topic_text = f"{topic['name']} {topic_description} {' '.join(topic.get('synonyms', []) or [])}"
                topic_texts.append(topic_text)
                topic_ids.append(topic['id'])
            
            # Кодируем батч тем с categorize_topic
            try:
                # Используем синхронную модель в асинхронном контексте
                import concurrent.futures
                embedder = self.classification_provider._get_embedder()
                
                def encode_sync():
                    return embedder.encode(topic_texts, mode="categorize_topic")
                
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    embeddings = await loop.run_in_executor(executor, encode_sync)
                
                # Сохраняем эталоны
                for idx, topic_id in enumerate(topic_ids):
                    if idx < len(embeddings):
                        references[topic_id] = embeddings[idx]
                
            except Exception as e:
                logger.error(f"Ошибка создания эталона для батча тем: {e}")
                continue
        
        # Обновляем кеш
        self._topic_references_cache = references
        self._topics_cache_timestamp = datetime.now()
        logger.info(f"✅ Подготовлено {len(references)} эталонов тем (кешировано)")
        
        return references
    
    async def classify_message(self, message_id: int, text: str) -> List[Dict[str, Any]]:
        """Классифицировать сообщение по темам с использованием categorize_topic"""
        try:
            # Получаем эталоны тем (с кешированием)
            topic_references = await self._prepare_topic_references()
            
            if not topic_references:
                logger.warning("Нет эталонов тем для классификации")
                return []
            
            # Получаем эмбеддинг сообщения с categorize_topic
            if not self.classification_provider:
                from pro_mode.embedding_service import FRIDAEmbeddingProvider
                self.classification_provider = FRIDAEmbeddingProvider(device="cpu")
            
            message_embedding = await self.classification_provider.get_embedding_for_classification(text)
            
            # Сравниваем с эталонами
            classifications = []
            for topic_id, topic_embedding in topic_references.items():
                similarity = self._cosine_similarity(message_embedding, topic_embedding)
                
                if similarity >= self.confidence_threshold:
                    # Получаем название темы из БД для отчета
                    topic_name = await self._get_topic_name(topic_id)
                    classifications.append({
                        'topic_id': topic_id,
                        'topic_name': topic_name or f"Тема {topic_id}",
                        'score': similarity,
                        'method': 'categorize_topic'
                    })
            
            # Выбираем лучшую классификацию (top-1)
            if classifications:
                classifications.sort(key=lambda x: x['score'], reverse=True)
                # Оставляем только лучшую, если разница значительна
                if len(classifications) > 1 and classifications[0]['score'] > 0.75:
                    classifications = [classifications[0]]
                else:
                    # Если разница незначительна, оставляем все выше порога
                    classifications = classifications[:1]  # Все равно берем только лучшую
            
            # Сохраняем классификации в БД
            if classifications:
                await self._save_classifications(message_id, classifications)
            
            return classifications
            
        except Exception as e:
            logger.error(f"Ошибка классификации сообщения {message_id}: {e}")
            raise
    
    async def _get_topic_name(self, topic_id: int) -> Optional[str]:
        """Получить название темы по ID"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            name = await conn.fetchval("SELECT name FROM topics WHERE id = $1", topic_id)
            await conn.close()
            return name
        except Exception:
            return None
    
    def invalidate_cache(self):
        """Инвалидировать кеш эталонов тем (вызывать при изменении тем)"""
        self._topic_references_cache.clear()
        self._topics_cache_timestamp = None
        logger.info("Кеш эталонов тем инвалидирован")
    
    async def _get_all_topics(self) -> List[Dict[str, Any]]:
        """Получить все темы из БД"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            rows = await conn.fetch("""
                SELECT id, name, description, synonyms FROM topics ORDER BY name
            """)
            
            topics = []
            for row in rows:
                topics.append({
                    'id': row['id'],
                    'name': row['name'],
                    'description': row.get('description', '') or '',
                    'synonyms': row['synonyms'] or []
                })
            
            await conn.close()
            return topics
            
        except Exception as e:
            logger.error(f"Ошибка получения тем: {e}")
            raise
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Вычислить косинусное сходство между векторами"""
        import numpy as np
        
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    async def _save_classifications(self, message_id: int, classifications: List[Dict[str, Any]]):
        """Сохранить классификации в БД"""
        try:
            if not classifications:
                logger.debug(f"Нет классификаций для сохранения сообщения {message_id}")
                return
                
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            saved_count = 0
            for classification in classifications:
                try:
                    result = await conn.execute("""
                        INSERT INTO message_topics (message_id, topic_id, score, method)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (message_id, topic_id) DO UPDATE SET
                            score = EXCLUDED.score,
                            method = EXCLUDED.method,
                            created_at = NOW()
                    """, message_id, classification['topic_id'], classification['score'], classification['method'])
                    
                    # Проверяем, что INSERT/UPDATE выполнен
                    if 'INSERT' in result or 'UPDATE' in result:
                        saved_count += 1
                        logger.debug(f"✅ Сохранена классификация: message_id={message_id}, topic_id={classification['topic_id']}, score={classification['score']:.3f}")
                    else:
                        logger.warning(f"⚠️ Не удалось сохранить классификацию: message_id={message_id}, topic_id={classification['topic_id']}")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка сохранения одной классификации: message_id={message_id}, topic_id={classification['topic_id']}, error={e}")
                    raise
            
            logger.info(f"💾 Сохранено {saved_count}/{len(classifications)} классификаций для сообщения {message_id}")
            await conn.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения классификаций для сообщения {message_id}: {e}")
            import traceback
            logger.error(f"Трассировка: {traceback.format_exc()}")
            raise

    async def classify_recent_messages(self, limit: int = 500, threshold: float = None, 
                                     topic_ids: List[int] = None, 
                                     channel_ids: List[int] = None) -> Dict[str, Any]:
        """Классифицировать последние N сообщений с текстом"""
        try:
            # Переопределяем порог уверенности если указан
            old_threshold = None
            if threshold is not None:
                old_threshold = self.confidence_threshold
                self.confidence_threshold = threshold
            
            logger.info(f"🚀 Классификация запущена с порогом {self.confidence_threshold}")
            
            # Конвертируем IDs в int если они пришли как строки
            if channel_ids:
                channel_ids = [int(cid) for cid in channel_ids]
            if topic_ids:
                topic_ids = [int(tid) for tid in topic_ids]
            
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Формируем SQL запрос с фильтрами
            query = """
                SELECT id, text_content
                FROM messages
                WHERE text_content IS NOT NULL AND length(text_content) > 0
            """
            params = []
            param_num = 1
            
            # Добавляем фильтр по каналам если указан
            if channel_ids:
                query += f" AND channel_id = ANY(${param_num})"
                params.append(channel_ids)
                param_num += 1
            
            query += f" ORDER BY published_at DESC LIMIT ${param_num}"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            await conn.close()
            
            total_messages = len(rows)
            logger.info(f"📋 Найдено сообщений для классификации: {total_messages}")
            
            # Если указаны темы, получаем только их
            topics_to_check = None
            if topic_ids:
                topics_to_check = await self._get_topics_by_ids(topic_ids)
                logger.info(f"📂 Используется {len(topics_to_check)} тем (по ID)")
            else:
                topics_to_check = await self._get_all_topics()
                logger.info(f"📂 Используется {len(topics_to_check)} тем (все)")

            processed = 0
            classified = 0
            errors = 0
            
            logger.info(f"🔄 Начинаем обработку {total_messages} сообщений...")
            
            for idx, row in enumerate(rows, 1):
                try:
                    # Логируем начало обработки каждого сообщения для отладки
                    logger.info(f"🔄 Обработка сообщения {idx}/{total_messages} (ID: {row['id']})...")
                    
                    classifications = await self._classify_message_with_topics(
                        row['id'], row['text_content'], topics_to_check
                    )
                    processed += 1
                    if classifications:
                        classified += 1
                        logger.info(f"✅ Сообщение {idx} классифицировано в {len(classifications)} тем(у): {[c['topic_name'] for c in classifications]}")
                    else:
                        logger.info(f"❌ Сообщение {idx} не классифицировано (ни одна тема не подошла)")
                    
                    # Логируем прогресс каждые 10 сообщений
                    if idx % 10 == 0 or idx == total_messages:
                        logger.info(f"📊 Прогресс: {idx}/{total_messages} ({processed} обработано, {classified} классифицировано, {errors} ошибок)")
                        
                except Exception as e:
                    errors += 1
                    logger.warning(f"⚠️ Классификация сообщения {row['id']} пропущена: {e}")
                    import traceback
                    logger.debug(f"Трассировка ошибки: {traceback.format_exc()}")
                    continue
            
            # Восстанавливаем старый порог
            if old_threshold is not None:
                self.confidence_threshold = old_threshold
            
            return {
                'total_messages': total_messages,
                'processed': processed,
                'classified': classified,
                'errors': errors,
                'success_rate': (classified / processed * 100) if processed > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Ошибка классификации сообщений: {e}")
            raise
    
    async def classify_all_messages_in_pipeline(self, message_ids: List[int] = None, 
                                                limit: int = None) -> Dict[str, Any]:
        """Классифицировать все сообщения в рамках пайплайна тематического моделирования"""
        try:
            logger.info("🚀 Запуск классификации сообщений в рамках пайплайна...")
            
            # Подготавливаем эталоны тем (с кешированием)
            topic_references = await self._prepare_topic_references()
            if not topic_references:
                logger.warning("Нет эталонов тем для классификации")
                return {
                    'total_messages': 0,
                    'processed': 0,
                    'classified': 0,
                    'errors': 0,
                    'success_rate': 0
                }
            
            # Получаем сообщения для классификации
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            if message_ids:
                # Классифицируем конкретные сообщения
                query = """
                    SELECT id, text_content
                    FROM messages
                    WHERE id = ANY($1::bigint[])
                      AND text_content IS NOT NULL 
                      AND length(text_content) > 10
                """
                rows = await conn.fetch(query, message_ids)
            else:
                # Классифицируем последние сообщения
                query = """
                    SELECT id, text_content
                    FROM messages
                    WHERE text_content IS NOT NULL 
                      AND length(text_content) > 10
                    ORDER BY published_at DESC
                """
                if limit:
                    query += f" LIMIT {limit}"
                rows = await conn.fetch(query)
            
            await conn.close()
            
            total_messages = len(rows)
            logger.info(f"📋 Найдено сообщений для классификации: {total_messages}")
            
            if total_messages == 0:
                return {
                    'total_messages': 0,
                    'processed': 0,
                    'classified': 0,
                    'errors': 0,
                    'success_rate': 0
                }
            
            # Инициализируем провайдер
            if not self.classification_provider:
                from pro_mode.embedding_service import FRIDAEmbeddingProvider
                self.classification_provider = FRIDAEmbeddingProvider(device="cpu")
            
            # Получаем названия тем заранее (для оптимизации)
            logger.info("Загрузка названий тем...")
            topic_names_cache = {}
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            try:
                topic_ids_list = list(topic_references.keys())
                if topic_ids_list:
                    rows_topics = await conn.fetch(
                        "SELECT id, name FROM topics WHERE id = ANY($1::int[])",
                        topic_ids_list
                    )
                    for row in rows_topics:
                        topic_names_cache[row['id']] = row['name']
            finally:
                await conn.close()
            
            # Заполняем недостающие названия
            for topic_id in topic_references.keys():
                if topic_id not in topic_names_cache:
                    topic_names_cache[topic_id] = f"Тема {topic_id}"
            
            processed = 0
            classified = 0
            errors = 0
            
            # Батчинг для эффективности
            batch_size = 50
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                batch_texts = [row['text_content'] for row in batch]
                batch_ids = [row['id'] for row in batch]
                
                try:
                    # Кодируем батч сообщений с categorize_topic
                    import concurrent.futures
                    embedder = self.classification_provider._get_embedder()
                    
                    def encode_sync():
                        return embedder.encode(batch_texts, mode="categorize_topic")
                    
                    loop = asyncio.get_event_loop()
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        message_embeddings = await loop.run_in_executor(executor, encode_sync)
                    
                    # Сравниваем с эталонами тем
                    for idx, (message_id, message_embedding) in enumerate(zip(batch_ids, message_embeddings)):
                        try:
                            classifications = []
                            for topic_id, topic_embedding in topic_references.items():
                                similarity = self._cosine_similarity(message_embedding, topic_embedding)
                                
                                if similarity >= self.confidence_threshold:
                                    classifications.append({
                                        'topic_id': topic_id,
                                        'topic_name': topic_names_cache.get(topic_id, f"Тема {topic_id}"),
                                        'score': similarity,
                                        'method': 'categorize_topic'
                                    })
                            
                            # Выбираем лучшую классификацию
                            if classifications:
                                classifications.sort(key=lambda x: x['score'], reverse=True)
                                if len(classifications) > 1 and classifications[0]['score'] > 0.75:
                                    classifications = [classifications[0]]
                                else:
                                    classifications = classifications[:1]
                                
                                # Сохраняем классификацию
                                await self._save_classifications(message_id, classifications)
                                classified += 1
                            
                            processed += 1
                            
                        except Exception as e:
                            errors += 1
                            logger.warning(f"⚠️ Ошибка классификации сообщения {message_id}: {e}")
                            continue
                    
                    # Логируем прогресс
                    if (i + batch_size) % 100 == 0 or (i + batch_size) >= len(rows):
                        logger.info(f"📊 Прогресс классификации: {min(i + batch_size, len(rows))}/{len(rows)} "
                                  f"({processed} обработано, {classified} классифицировано, {errors} ошибок)")
                
                except Exception as e:
                    errors += len(batch)
                    logger.error(f"❌ Ошибка обработки батча сообщений: {e}")
                    continue
            
            success_rate = (classified / processed * 100) if processed > 0 else 0
            logger.info(f"✅ Классификация завершена: {processed} обработано, {classified} классифицировано, "
                       f"{errors} ошибок (успешность: {success_rate:.1f}%)")
            
            return {
                'total_messages': total_messages,
                'processed': processed,
                'classified': classified,
                'errors': errors,
                'success_rate': success_rate
            }
            
        except Exception as e:
            logger.error(f"Ошибка классификации сообщений в пайплайне: {e}")
            raise
            
            result = {
                'processed': processed,
                'classified': classified,
                'errors': errors,
                'limit': limit,
                'total_found': total_messages
            }
            
            logger.info(f"✅ Классификация завершена! Обработано: {processed}, Классифицировано: {classified}, Ошибок: {errors}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка пакетной классификации: {e}")
            import traceback
            logger.error(f"Трассировка: {traceback.format_exc()}")
            raise
    
    async def _get_topics_by_ids(self, topic_ids: List[int]) -> List[Dict[str, Any]]:
        """Получить темы по ID"""
        try:
            # Конвертируем IDs в int если они пришли как строки
            if topic_ids:
                topic_ids = [int(tid) for tid in topic_ids]
            
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            rows = await conn.fetch("""
                SELECT id, name, description, synonyms FROM topics WHERE id = ANY($1) ORDER BY name
            """, topic_ids)
            
            topics = []
            for row in rows:
                topics.append({
                    'id': row['id'],
                    'name': row['name'],
                    'description': row.get('description', '') or '',
                    'synonyms': row['synonyms'] or []
                })
            
            await conn.close()
            return topics
            
        except Exception as e:
            logger.error(f"Ошибка получения тем по ID: {e}")
            raise
    
    async def _classify_message_with_topics(self, message_id: int, text: str, 
                                            topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Классифицировать сообщение по заданным темам (использует categorize_topic)"""
        try:
            # Фильтруем слишком короткие или неинформативные сообщения
            text_clean = text.strip()
            if not text_clean or len(text_clean) < 10:
                logger.debug(f"Пропущено сообщение {message_id}: слишком короткое или пустое")
                return []
            
            # Фильтруем служебные сообщения (только упоминания, без текста)
            if text_clean.startswith('@') and len(text_clean.split()) <= 1:
                logger.debug(f"Пропущено сообщение {message_id}: служебное сообщение")
                return []
            
            # Используем categorize_topic для классификации
            return await self.classify_message(message_id, text_clean)
            
        except Exception as e:
            logger.error(f"Ошибка классификации сообщения {message_id}: {e}")
            import traceback
            logger.error(f"Трассировка: {traceback.format_exc()}")
            return []

class OnboardingService:
    """Сервис для онбординга пользователей"""
    
    async def save_user_preferences(self, user_id: str, selected_topics: List[int], 
                                  seed_channels: List[int]) -> bool:
        """Сохранить предпочтения пользователя"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            await conn.execute("""
                INSERT INTO user_preferences (user_id, selected_topics, seed_channels)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET
                    selected_topics = EXCLUDED.selected_topics,
                    seed_channels = EXCLUDED.seed_channels,
                    updated_at = NOW()
            """, user_id, selected_topics, seed_channels)
            
            await conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения предпочтений пользователя: {e}")
            return False
    
    async def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получить предпочтения пользователя"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            row = await conn.fetchrow("""
                SELECT * FROM user_preferences WHERE user_id = $1
            """, user_id)
            
            await conn.close()
            
            if row:
                return {
                    'user_id': row['user_id'],
                    'selected_topics': row['selected_topics'] or [],
                    'seed_channels': row['seed_channels'] or [],
                    'blacklisted_topics': row['blacklisted_topics'] or [],
                    'notification_settings': row['notification_settings'] or {},
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения предпочтений пользователя: {e}")
            return None
    
    async def get_recommended_channels(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Получить рекомендованные каналы на основе предпочтений"""
        try:
            preferences = await self.get_user_preferences(user_id)
            if not preferences or not preferences['selected_topics']:
                return []
            
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Находим каналы, которые часто публикуют контент по выбранным темам
            query = """
                SELECT c.id, c.name, c.description, c.username,
                       COUNT(DISTINCT m.id) as message_count,
                       AVG(mt.score) as avg_topic_score
                FROM channels c
                JOIN messages m ON c.id = m.channel_id
                JOIN message_topics mt ON m.id = mt.message_id
                WHERE mt.topic_id = ANY($1::integer[])
                  AND (CASE WHEN cardinality($2::bigint[]) > 0 THEN c.id NOT IN (SELECT unnest($2::bigint[])) ELSE TRUE END)
                GROUP BY c.id, c.name, c.description, c.username
                HAVING COUNT(DISTINCT m.id) >= 5
                ORDER BY avg_topic_score DESC, message_count DESC
                LIMIT $3
            """
            
            rows = await conn.fetch(query, preferences['selected_topics'], 
                                  preferences['seed_channels'], limit)
            
            recommendations = []
            for row in rows:
                recommendations.append({
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'],
                    'username': row['username'],
                    'message_count': row['message_count'],
                    'avg_topic_score': float(row['avg_topic_score'])
                })
            
            await conn.close()
            return recommendations
            
        except Exception as e:
            logger.error(f"Ошибка получения рекомендаций каналов: {e}")
            return []
    
    async def validate_channel(self, channel_identifier: str) -> Optional[Dict[str, Any]]:
        """Валидировать существование канала"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Пробуем найти по username или ID
            row = await conn.fetchrow("""
                SELECT id, name, description, username FROM channels 
                WHERE username = $1 OR id = $1::bigint
            """, channel_identifier)
            
            await conn.close()
            
            if row:
                return {
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'],
                    'username': row['username']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка валидации канала: {e}")
            return None

# Глобальные экземпляры сервисов
classification_service = ClassificationService()
onboarding_service = OnboardingService()
