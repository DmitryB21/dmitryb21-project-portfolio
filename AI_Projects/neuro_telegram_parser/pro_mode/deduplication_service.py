"""
Модуль для семантической кластеризации и группировки событий
"""

import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime, timedelta
import asyncpg
from config_utils import get_config
from pro_mode.embedding_service import embedding_service
import numpy as np

# HDBSCAN и PCA импорты
try:
    import hdbscan
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False

# PCA всегда доступен через sklearn
try:
    from sklearn.decomposition import PCA
    PCA_AVAILABLE = True
except ImportError:
    PCA_AVAILABLE = False

logger = logging.getLogger(__name__)

class SemanticClusteringService:
    """Сервис для семантической кластеризации и группировки событий"""
    
    def __init__(self):
        self.similarity_threshold = 0.75  # Порог схожести для объединения в кластер
        self.max_cluster_age_days = 7  # Максимальный возраст кластера для добавления новых сообщений
        self.min_cluster_size = 2  # Минимальный размер кластера для сохранения
        self.search_window_size = 30  # Количество похожих сообщений для поиска (увеличено с 10 до 30)
        self.adaptive_threshold_enabled = True  # Включить адаптивный подбор порога
        
        # LLM генератор заголовков удален (использовался Yandex GPT)
        # Теперь используется только fallback метод на основе ключевых фраз
        self.llm_generator = None
    
    async def process_new_message(self, message_id: int, text: str, channel_id: int, 
                                published_at: datetime) -> Optional[str]:
        """Обработать новое сообщение: найти похожие или создать новый кластер (DEPRECATED - используйте run_hdbscan_clustering)"""
        try:
            # Быстрый выход, если сообщение уже привязано к кластеру
            try:
                config = get_config()
                conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
                existing_cluster = await conn.fetchval(
                    "SELECT cluster_id FROM cluster_messages WHERE message_id = $1 LIMIT 1",
                    message_id
                )
                await conn.close()
                if existing_cluster:
                    logger.info(f"Сообщение {message_id} уже находится в кластере {existing_cluster}, пропуск")
                    return existing_cluster
            except Exception:
                pass

            # Получаем эмбеддинг сообщения
            embedding = await embedding_service.provider.get_embedding(text)
            
            # Ищем похожие сообщения в недавних кластерах
            similar_messages = await self._find_similar_messages(
                embedding, published_at, limit=self.search_window_size
            )
            
            # Определяем эффективный порог
            effective_threshold = self.similarity_threshold
            
            # Применяем адаптивный подход: если топ-результат выше порога, но не сильно
            # (разница между топ-1 и топ-2/3 небольшая), это может быть плотная область
            # и нужно использовать более жесткий порог для точности
            if similar_messages and len(similar_messages) >= 2:
                top_score = similar_messages[0]['score']
                second_score = similar_messages[1]['score']
                score_spread = top_score - second_score
                
                # Если разница маленькая (плотная область), поднимаем порог
                if score_spread < 0.05 and top_score >= self.similarity_threshold:
                    # В плотной области используем более жесткий порог
                    effective_threshold = max(self.similarity_threshold, top_score * 0.98)
                    logger.debug(f"Плотная область обнаружена, эффективный порог: {effective_threshold:.3f}")
            
            if similar_messages and similar_messages[0]['score'] >= effective_threshold:
                # Пытаемся взять cluster_id из payload похожего сообщения
                payload = similar_messages[0].get('payload') or {}
                cluster_id = payload.get('cluster_id')
                if not cluster_id:
                    # Если в payload нет cluster_id, проверим в БД, привязано ли похожее сообщение к какому-либо кластеру
                    try:
                        config = get_config()
                        conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
                        existing = await conn.fetchval(
                            "SELECT cluster_id FROM cluster_messages WHERE message_id = $1 LIMIT 1",
                            payload.get('message_id')
                        )
                        await conn.close()
                        cluster_id = existing
                    except Exception:
                        cluster_id = None
                
                if cluster_id:
                    # Проверяем, не слишком ли большой кластер (предотвращаем раздувание)
                    config = get_config()
                    conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
                    cluster_size = await conn.fetchval("""
                        SELECT COUNT(*) FROM cluster_messages WHERE cluster_id = $1
                    """, cluster_id)
                    await conn.close()
                    
                    # Если кластер слишком большой, создаём новый
                    if cluster_size > 50:
                        logger.info(f"Кластер {cluster_id} слишком большой ({cluster_size} сообщений), создаём новый для сообщения {message_id}")
                        cluster_id = await self._create_new_cluster(message_id, text, channel_id, published_at)
                        logger.info(f"Создан новый кластер {cluster_id} для сообщения {message_id}")
                        return cluster_id
                    
                    # Добавляем к найденному кластеру
                    await self._add_message_to_cluster(message_id, cluster_id, similar_messages[0]['score'])
                    logger.info(f"Сообщение {message_id} добавлено к кластеру {cluster_id} (size={cluster_size+1})")
                    return cluster_id
                
                cluster_id = await self._create_new_cluster(message_id, text, channel_id, published_at)
                logger.info(f"Создан новый кластер {cluster_id} для сообщения {message_id}")
                return cluster_id
            else:
                # Создаем новый кластер
                cluster_id = await self._create_new_cluster(message_id, text, channel_id, published_at)
                logger.info(f"Создан новый кластер {cluster_id} для сообщения {message_id}")
                return cluster_id
                
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения {message_id}: {e}")
            raise
    
    async def _find_similar_messages(self, embedding: List[float], published_at: datetime, 
                                   limit: int = 5) -> List[Dict[str, Any]]:
        """Найти похожие сообщения в недавних кластерах"""
        try:
            # Фильтр по времени (только недавние сообщения)
            date_from = published_at - timedelta(days=self.max_cluster_age_days)
            
            filters = {
                'date_from': date_from.isoformat(),
                'date_to': published_at.isoformat()
            }
            
            # Ищем через Qdrant
            results = await embedding_service.qdrant.search_similar(
                query_vector=embedding,
                limit=limit,
                filters=filters
            )
            
            # Адаптивный порог: анализируем распределение скоров
            if self.adaptive_threshold_enabled and results and len(results) > 3:
                # Вычисляем локальную плотность - разница между топ-1 и топ-3
                top_scores = [r['score'] for r in results[:min(5, len(results))]]
                if len(top_scores) >= 3:
                    score_gap = top_scores[0] - top_scores[2]
                    
                    # Если разрыв маленький - много похожих, можно поднять порог
                    # Если разрыв большой - мало похожих, нужно понизить порог
                    if score_gap > 0.15:
                        # Бинарное разделение - можем использовать более жесткий порог
                        adaptive_threshold = top_scores[0] * 0.95
                    else:
                        # Плотная область - используем текущий порог
                        adaptive_threshold = self.similarity_threshold
                    
                    # Применяем адаптивный порог только если он выше базового
                    if adaptive_threshold > self.similarity_threshold:
                        filtered_results = [r for r in results if r['score'] >= adaptive_threshold]
                        if filtered_results:
                            logger.debug(f"Адаптивный порог: {adaptive_threshold:.3f} (базовый: {self.similarity_threshold:.3f})")
                            return filtered_results
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка поиска похожих сообщений: {e}")
            return []
    
    async def _create_new_cluster(self, message_id: int, text: str, channel_id: int, 
                                published_at: datetime) -> str:
        """Создать новый кластер событий"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            cluster_id = str(uuid.uuid4())
            
            # Генерируем заголовок события через LLM с fallback
            # Используем значения по умолчанию (будут переопределены если переданы в run_clustering)
            title = await self._generate_event_title(
                text, 
                cluster_id,
                max_texts=getattr(self, '_current_max_title_texts', 10),
                max_chars_per_text=getattr(self, '_current_max_title_chars_per_text', 500)
            )
            
            # Создаем кластер в БД
            await conn.execute("""
                INSERT INTO dedup_clusters (cluster_id, title, summary, created_at, stats)
                VALUES ($1, $2, $3, $4, $5::jsonb)
            """, cluster_id, title, text[:500], published_at, json.dumps({
                'message_count': 1,
                'channel_count': 1,
                'channels': [channel_id]
            }))
            
            # Добавляем сообщение в кластер (первое сообщение всегда имеет similarity 1.0)
            await conn.execute("""
                INSERT INTO cluster_messages (cluster_id, message_id, similarity_score, is_primary)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (cluster_id, message_id) DO UPDATE SET similarity_score = EXCLUDED.similarity_score
            """, cluster_id, message_id, 1.0, True)

            # Устанавливаем primary_topic_id кластера по топ-метке сообщения (если есть)
            try:
                primary_topic_id = await conn.fetchval(
                    """
                    SELECT topic_id
                    FROM message_topics
                    WHERE message_id = $1
                    ORDER BY score DESC
                    LIMIT 1
                    """,
                    message_id
                )
                if primary_topic_id is not None:
                    await conn.execute(
                        "UPDATE dedup_clusters SET primary_topic_id = $1, updated_at = NOW() WHERE cluster_id = $2",
                        int(primary_topic_id), cluster_id
                    )
            except Exception:
                pass
            
            # Сохраняем эмбеддинг в Qdrant с метаданными кластера
            embedding = await embedding_service.provider.get_embedding(text)
            payload = {
                'message_id': message_id,
                'channel_id': channel_id,
                'date': published_at.isoformat(),
                'cluster_id': cluster_id,
                'text_preview': text[:200] + "..." if len(text) > 200 else text
            }
            
            # используем числовой ID точки, как и в индексации
            await embedding_service.qdrant.upsert_embedding(message_id, embedding, payload)
            
            await conn.close()
            return cluster_id
            
        except Exception as e:
            logger.error(f"Ошибка создания кластера: {e}")
            raise

    async def backfill_primary_topics(self) -> int:
        """Проставить primary_topic_id для кластеров, где он отсутствует"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            updated = await conn.execute(
                """
                WITH ranked_topics AS (
                    SELECT dc.cluster_id,
                           mt.topic_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY dc.cluster_id
                               ORDER BY MAX(mt.score) DESC
                           ) AS rn
                    FROM dedup_clusters dc
                    JOIN cluster_messages cm ON cm.cluster_id = dc.cluster_id
                    JOIN message_topics mt ON mt.message_id = cm.message_id
                    WHERE dc.primary_topic_id IS NULL
                    GROUP BY dc.cluster_id, mt.topic_id
                )
                UPDATE dedup_clusters dc
                SET primary_topic_id = rt.topic_id,
                    updated_at = NOW()
                FROM ranked_topics rt
                WHERE dc.cluster_id = rt.cluster_id AND rt.rn = 1
                """
            )
            await conn.close()
            # asyncpg returns e.g. 'UPDATE 42'
            try:
                return int(str(updated).split(' ')[-1])
            except Exception:
                return 0
        except Exception as e:
            logger.error(f"Ошибка бэкфилла primary_topic_id: {e}")
            return 0
    
    async def _add_message_to_cluster(self, message_id: int, cluster_id: str, similarity_score: float):
        """Добавить сообщение к существующему кластеру"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Проверяем, существует ли кластер в PostgreSQL
            cluster_exists = await conn.fetchval(
                "SELECT 1 FROM dedup_clusters WHERE cluster_id = $1 LIMIT 1",
                cluster_id
            )
            
            if not cluster_exists:
                logger.warning(f"Кластер {cluster_id} не найден в PostgreSQL, пропускаем добавление сообщения {message_id}")
                await conn.close()
                return
            
            # Добавляем сообщение в кластер
            insert_result = await conn.execute("""
                INSERT INTO cluster_messages (cluster_id, message_id, similarity_score, is_primary)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (cluster_id, message_id) DO NOTHING
            """, cluster_id, message_id, similarity_score, False)
            
            # Обновляем статистику кластера только если действительно вставили новую связь
            if insert_result and insert_result.endswith(" 1"):
                # Обновляем статистику
                await conn.execute("""
                    UPDATE dedup_clusters 
                    SET stats = jsonb_set(
                        jsonb_set(stats, '{message_count}', to_jsonb((stats->>'message_count')::int + 1)),
                        '{channel_count}', to_jsonb(array_length(array(SELECT DISTINCT m.channel_id FROM cluster_messages cm JOIN messages m ON cm.message_id = m.id WHERE cm.cluster_id = $1), 1))
                    ),
                    updated_at = NOW()
                    WHERE cluster_id = $1
                """, cluster_id)
                
                # Обновляем заголовок кластера на основе LLM/ключевых фраз
                try:
                    new_title = await self._generate_event_title(
                        "", 
                        cluster_id,
                        max_texts=getattr(self, '_current_max_title_texts', 10),
                        max_chars_per_text=getattr(self, '_current_max_title_chars_per_text', 500)
                    )
                    await conn.execute("""
                        UPDATE dedup_clusters 
                        SET title = $1, updated_at = NOW()
                        WHERE cluster_id = $2
                    """, new_title, cluster_id)
                except Exception as e:
                    logger.error(f"Ошибка обновления заголовка кластера: {e}")
                
                # ВАЖНО: Обновляем payload в Qdrant с новым cluster_id
                try:
                    # Получаем данные сообщения для обновления payload
                    message_data = await conn.fetchrow("""
                        SELECT m.text_content, m.channel_id, m.published_at
                        FROM messages m
                        WHERE m.id = $1
                    """, message_id)
                    
                    if message_data:
                        # Генерируем эмбеддинг
                        embedding = await embedding_service.provider.get_embedding(message_data['text_content'])
                        
                        # Обновляем payload в Qdrant с правильным cluster_id
                        payload = {
                            'message_id': message_id,
                            'channel_id': message_data['channel_id'],
                            'date': message_data['published_at'].isoformat(),
                            'cluster_id': cluster_id,
                            'text_preview': message_data['text_content'][:200] + "..." if len(message_data['text_content']) > 200 else message_data['text_content']
                        }
                        
                        await embedding_service.qdrant.upsert_embedding(message_id, embedding, payload)
                        logger.debug(f"Обновлен payload в Qdrant для сообщения {message_id} с cluster_id {cluster_id}")
                        
                except Exception as e:
                    logger.error(f"Ошибка обновления payload в Qdrant для сообщения {message_id}: {e}")
            
            await conn.close()
            
        except Exception as e:
            logger.error(f"Ошибка добавления сообщения к кластеру: {e}")
            raise
    
    async def _generate_event_title(self, text: str, cluster_id: str = None,
                                   max_texts: int = 10, max_chars_per_text: int = 500) -> str:
        """Генерировать заголовок события через LLM с fallback на ключевые фразы"""
        try:
            # Получаем тексты всех сообщений в кластере
            texts = [text]
            if cluster_id:
                try:
                    config = get_config()
                    conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
                    cluster_texts = await conn.fetch("""
                        SELECT m.text_content
                        FROM cluster_messages cm
                        JOIN messages m ON cm.message_id = m.id
                        WHERE cm.cluster_id = $1 AND m.text_content IS NOT NULL
                        ORDER BY cm.similarity_score DESC NULLS LAST
                    """, cluster_id)
                    if cluster_texts:
                        texts = [row['text_content'] for row in cluster_texts]
                    await conn.close()
                except Exception as e:
                    logger.error(f"Ошибка получения текстов кластера: {e}")
            
            # Генерация заголовка на основе ключевых фраз (fallback метод)
            import re
            from collections import Counter
            
            # Ищем ключевые фразы и имена собственные
            def extract_key_phrases(text):
                # Удаляем технические элементы
                text = re.sub(r'https?://\S+|www\.\S+', '', text)
                text = re.sub(r'@\S+', '', text)
                text = re.sub(r'[🔹🟩📹⚡️❗️🎥💻🚗📝🗞]', '', text)
                
                # Ищем имена собственные (с заглавной буквы)
                proper_nouns = re.findall(r'\b[А-ЯЁ][а-яё]+\b', text)
                
                # Ищем важные термины в кавычках
                quoted_terms = re.findall(r'«([^»]+)»', text)
                
                # Ищем технические термины и аббревиатуры
                tech_terms = re.findall(r'\b[А-ЯЁ]{2,}\b', text)  # Аббревиатуры
                
                # Ищем географические названия
                geo_terms = re.findall(r'\b(?:Россия|Украина|США|ЕС|НАТО|Москва|Киев|Вашингтон|Брюссель|Париж|Берлин|Лондон|Токио|Пекин)\b', text)
                
                return proper_nouns + quoted_terms + tech_terms + geo_terms
            
            # Собираем ключевые фразы из всех текстов
            all_phrases = []
            for doc in texts:
                phrases = extract_key_phrases(doc)
                all_phrases.extend(phrases)
            
            if not all_phrases:
                # Fallback: первые слова из текста
                words = re.findall(r'\b[а-яёА-ЯЁa-zA-Z]{4,}\b', text)
                return ' '.join(words[:3]) if words else text[:50]
            
            # Подсчитываем частоту фраз
            phrase_freq = Counter(all_phrases)
            
            # Берем самые частые фразы (исключаем слишком общие)
            common_words = {'это', 'что', 'как', 'для', 'был', 'была', 'было', 'были', 'или', 'вот', 'все', 'быть'}
            top_phrases = [phrase for phrase, freq in phrase_freq.most_common(10) 
                          if phrase.lower() not in common_words and len(phrase) > 2]
            
            # Формируем заголовок из топ-3 фраз
            if top_phrases:
                title_phrases = top_phrases[:3]
                title = ' • '.join(title_phrases)
                return title[:100]  # Ограничиваем длину
            
            # Fallback: первые значимые слова
            words = re.findall(r'\b[а-яёА-ЯЁa-zA-Z]{4,}\b', text)
            return ' '.join(words[:3]) if words else text[:50]
            
            # Если ничего не получилось - берем первые слова
            return ' '.join(text.split()[:4]) if len(text.split()) >= 4 else text[:100]
            
        except Exception as e:
            logger.error(f"Ошибка генерации заголовка через TF-IDF: {e}")
            # Fallback на простой метод
            words = text.split()[:4]
            return " ".join(words) + ("..." if len(text.split()) > 4 else "")
    
    async def get_event_clusters(self, limit: int = 20, offset: int = 0, 
                               filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Получить список событий (кластеров)"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            where_clauses = []
            params = []
            param_count = 0
            
            if filters:
                if 'date_from' in filters:
                    param_count += 1
                    where_clauses.append(f"created_at >= ${param_count}")
                    # Преобразуем строку в datetime если необходимо
                    date_from = filters['date_from']
                    if isinstance(date_from, str):
                        from datetime import datetime
                        date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                    params.append(date_from)
                
                if 'date_to' in filters:
                    param_count += 1
                    where_clauses.append(f"created_at <= ${param_count}")
                    # Преобразуем строку в datetime если необходимо
                    date_to = filters['date_to']
                    if isinstance(date_to, str):
                        from datetime import datetime
                        date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                    params.append(date_to)
                
                if 'topic_id' in filters:
                    param_count += 1
                    # Убеждаемся, что topic_id - это целое число, не список
                    topic_id = filters['topic_id']
                    if isinstance(topic_id, list):
                        topic_id = topic_id[0] if topic_id else None
                    if topic_id is not None:
                        where_clauses.append(f"primary_topic_id = ${param_count}")
                        params.append(int(topic_id))
                
                if 'cluster_id' in filters:
                    param_count += 1
                    where_clauses.append(f"dc.cluster_id = ${param_count}")
                    params.append(filters['cluster_id'])
            
            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            
            query = f"""
                SELECT dc.*, 
                       array_agg(DISTINCT m.channel_id) as channel_ids,
                       array_agg(DISTINCT c.name) as channel_names,
                       COUNT(cm.message_id) as message_count
                FROM dedup_clusters dc
                LEFT JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
                LEFT JOIN messages m ON cm.message_id = m.id
                LEFT JOIN channels c ON m.channel_id = c.id
                {where_sql}
                GROUP BY dc.id, dc.cluster_id
                ORDER BY dc.created_at DESC
                LIMIT ${param_count + 1} OFFSET ${param_count + 2}
            """
            
            params.extend([limit, offset])
            
            rows = await conn.fetch(query, *params)
            
            events = []
            for row in rows:
                events.append({
                    'cluster_id': row['cluster_id'],
                    'title': row['title'],
                    'summary': row['summary'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'stats': row['stats'],
                    'channel_ids': row['channel_ids'],
                    'channel_names': row['channel_names'],
                    'message_count': row['message_count']
                })
            
            await conn.close()
            return events
            
        except Exception as e:
            logger.error(f"Ошибка получения событий: {e}")
            raise

    async def run_batch_dedup(self, limit: int = 1000, threshold: float = 0.8) -> Dict[str, Any]:
        """Запустить дедупликацию для последних N сообщений с заданным порогом"""
        try:
            old_threshold = self.similarity_threshold
            self.similarity_threshold = threshold
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])

            rows = await conn.fetch(
                """
                SELECT id, channel_id, text_content, published_at
                FROM messages
                WHERE text_content IS NOT NULL AND length(text_content) > 0
                ORDER BY published_at DESC
                LIMIT $1
                """,
                limit
            )

            processed = 0
            created = 0
            appended = 0

            for row in rows:
                processed += 1
                result = await self.process_new_message(
                    message_id=row['id'],
                    text=row['text_content'],
                    channel_id=row['channel_id'],
                    published_at=row['published_at']
                )
                # Если метод вернул cluster_id, считаем как созданный или присоединённый
                if result:
                    # Простейшая эвристика: если сообщение было первым — score=1.0 и create_new_cluster вызывался
                    # Мы не знаем здесь точно, поэтому просто считаем созданным, если score==1.0 обрабатывалось выше.
                    # Для упрощения: увеличим created, если сообщений в этом кластере было 1 сразу после вставки.
                    created += 1  # допускаем небольшую переоценку на раннем этапе
                else:
                    appended += 1

            await conn.close()
            self.similarity_threshold = old_threshold

            return {
                'processed': processed,
                'created_clusters_guess': created,
                'threshold': threshold,
                'limit': limit
            }
        except Exception as e:
            logger.error(f"Ошибка пакетной дедупликации: {e}")
            raise
    
    async def get_cluster_details(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """Получить детали конкретного кластера"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Получаем информацию о кластере
            cluster_row = await conn.fetchrow("""
                SELECT * FROM dedup_clusters WHERE cluster_id = $1
            """, cluster_id)
            
            if not cluster_row:
                await conn.close()
                return None
            
            # Получаем сообщения кластера
            messages_rows = await conn.fetch("""
                SELECT m.*, cm.similarity_score, cm.is_primary, c.name as channel_name
                FROM cluster_messages cm
                JOIN messages m ON cm.message_id = m.id
                JOIN channels c ON m.channel_id = c.id
                WHERE cm.cluster_id = $1
                ORDER BY cm.similarity_score DESC, m.published_at DESC
            """, cluster_id)
            
            messages = []
            for row in messages_rows:
                messages.append({
                    'message_id': row['id'],
                    'text': row['text_content'],
                    'date': row['published_at'],
                    'channel_name': row['channel_name'],
                    'similarity_score': row['similarity_score'],
                    'is_primary': row['is_primary'],
                    'views': row['views_count'],
                    'forwards': row['forwards_count']
                })
            
            await conn.close()
            
            return {
                'cluster_id': cluster_row['cluster_id'],
                'title': cluster_row['title'],
                'summary': cluster_row['summary'],
                'created_at': cluster_row['created_at'],
                'updated_at': cluster_row['updated_at'],
                'stats': cluster_row['stats'],
                'messages': messages
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения деталей кластера: {e}")
            raise

    async def cleanup_single_clusters(self) -> int:
        """Удаляет кластеры с одним сообщением для улучшения качества дедупликации"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Находим кластеры с одним сообщением
            single_clusters = await conn.fetch("""
                SELECT dc.cluster_id 
                FROM dedup_clusters dc
                LEFT JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
                GROUP BY dc.cluster_id
                HAVING COUNT(cm.message_id) = 1
            """)
            
            deleted_count = 0
            for cluster_row in single_clusters:
                cluster_id = cluster_row['cluster_id']
                
                # Удаляем связи сообщений с кластером
                await conn.execute(
                    "DELETE FROM cluster_messages WHERE cluster_id = $1",
                    cluster_id
                )
                
                # Удаляем сам кластер
                await conn.execute(
                    "DELETE FROM dedup_clusters WHERE cluster_id = $1",
                    cluster_id
                )
                
                deleted_count += 1
            
            await conn.close()
            logger.info(f"Удалено {deleted_count} одиночных кластеров")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки одиночных кластеров: {e}")
            return 0

    async def reprocess_all_messages(self, threshold: float = 0.75, limit: int = 1000) -> Dict[str, int]:
        """Переобработать все сообщения с новыми параметрами дедупликации"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Очищаем существующие кластеры
            await conn.execute("DELETE FROM cluster_messages")
            await conn.execute("DELETE FROM dedup_clusters")
            
            # Очищаем Qdrant коллекции (posts_search и posts_clustering)
            # Старая коллекция telegram_messages больше не используется
            try:
                # Удаляем старые коллекции, если они существуют
                try:
                    await embedding_service.qdrant.delete_collection("telegram_messages")
                    logger.info("Старая коллекция telegram_messages удалена")
                except Exception:
                    pass  # Коллекция может не существовать
                
                # Коллекции posts_search и posts_clustering управляются через TopicModelingService
                logger.info("Qdrant коллекции очищены")
            except Exception as e:
                logger.warning(f"Не удалось очистить Qdrant коллекции: {e}")
            
            # Получаем все проиндексированные сообщения
            messages = await conn.fetch("""
                SELECT m.id, m.text_content, m.channel_id, m.published_at
                FROM messages m
                JOIN embeddings e ON m.id = e.message_id
                WHERE m.text_content IS NOT NULL AND LENGTH(m.text_content) > 10
                ORDER BY m.published_at ASC
                LIMIT $1
            """, limit)
            
            await conn.close()
            
            # Устанавливаем новый порог
            self.similarity_threshold = threshold
            
            processed_count = 0
            clustered_count = 0
            
            for message_row in messages:
                cluster_id = await self.process_new_message(
                    message_row['id'],
                    message_row['text_content'],
                    message_row['channel_id'],
                    message_row['published_at']
                )
                
                processed_count += 1
                if cluster_id:
                    clustered_count += 1
                
                if processed_count % 50 == 0:
                    logger.info(f"Обработано {processed_count}/{len(messages)} сообщений")
            
            # Очищаем одиночные кластеры
            deleted_singles = await self.cleanup_single_clusters()
            
            logger.info(f"Переобработка завершена: {processed_count} сообщений, {clustered_count} кластеризовано, {deleted_singles} одиночных кластеров удалено")
            
            return {
                'processed': processed_count,
                'clustered': clustered_count,
                'deleted_singles': deleted_singles
            }
            
        except Exception as e:
            logger.error(f"Ошибка переобработки сообщений: {e}")
            return {'processed': 0, 'clustered': 0, 'deleted_singles': 0}

    async def analyze_clustering_quality(self, limit: int = 1000) -> Dict[str, Any]:
        """Анализ качества кластеризации: метрики, статистика, рекомендации"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Получаем все кластеры с сообщениями
            clusters = await conn.fetch("""
                SELECT 
                    dc.cluster_id,
                    dc.title,
                    dc.created_at,
                    COUNT(cm.message_id) as message_count,
                    array_agg(DISTINCT cm.similarity_score) as scores
                FROM dedup_clusters dc
                LEFT JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
                GROUP BY dc.cluster_id, dc.title, dc.created_at
                ORDER BY dc.created_at DESC
                LIMIT $1
            """, limit)
            
            total_clusters = len(clusters)
            if total_clusters == 0:
                await conn.close()
                return {
                    'status': 'no_clusters',
                    'message': 'Кластеры не найдены'
                }
            
            # Анализ размеров кластеров
            cluster_sizes = [row['message_count'] for row in clusters]
            single_clusters = sum(1 for size in cluster_sizes if size == 1)
            small_clusters = sum(1 for size in cluster_sizes if 2 <= size <= 5)
            medium_clusters = sum(1 for size in cluster_sizes if 6 <= size <= 20)
            large_clusters = sum(1 for size in cluster_sizes if size > 20)
            
            # Анализ similarity scores
            all_scores = []
            for cluster in clusters:
                scores = cluster['scores']
                if scores and len(scores) > 0:
                    all_scores.extend([float(s) for s in scores if s is not None])
            
            # Вычисляем метрики качества
            avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
            min_score = min(all_scores) if all_scores else 0
            max_score = max(all_scores) if all_scores else 1
            
            # Анализ распределения размеров
            avg_cluster_size = sum(cluster_sizes) / len(cluster_sizes) if cluster_sizes else 0
            median_cluster_size = sorted(cluster_sizes)[len(cluster_sizes) // 2] if cluster_sizes else 0
            
            # Рекомендации
            recommendations = []
            
            if single_clusters / total_clusters > 0.3:
                recommendations.append({
                    'type': 'warning',
                    'message': f'Большой процент одиночных кластеров ({single_clusters / total_clusters * 100:.1f}%). Порог схожести слишком высокий.',
                    'action': 'Понизить порог схожести'
                })
            
            if avg_score < 0.7:
                recommendations.append({
                    'type': 'warning',
                    'message': f'Низкое среднее сходство ({avg_score:.2f}). Кластеры могут содержать слабосвязанные сообщения.',
                    'action': 'Повысить порог схожести'
                })
            
            if large_clusters > total_clusters * 0.1:
                recommendations.append({
                    'type': 'info',
                    'message': f'Много крупных кластеров ({large_clusters}). Возможно, они слишком общие.',
                    'action': 'Рассмотреть возможность разделения крупных кластеров'
                })
            
            await conn.close()
            
            return {
                'status': 'ok',
                'metrics': {
                    'total_clusters': total_clusters,
                    'avg_cluster_size': round(avg_cluster_size, 2),
                    'median_cluster_size': median_cluster_size,
                    'avg_similarity_score': round(avg_score, 3),
                    'min_similarity_score': round(min_score, 3),
                    'max_similarity_score': round(max_score, 3),
                },
                'distribution': {
                    'single_clusters': single_clusters,
                    'small_clusters': small_clusters,
                    'medium_clusters': medium_clusters,
                    'large_clusters': large_clusters
                },
                'recommendations': recommendations,
                'current_threshold': self.similarity_threshold
            }
            
        except Exception as e:
            logger.error(f"Ошибка анализа качества кластеризации: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def get_clustering_statistics(self) -> Dict[str, Any]:
        """Получить базовую статистику по кластеризации"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Общая статистика
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT dc.cluster_id) as total_clusters,
                    COUNT(DISTINCT cm.message_id) as total_messages_in_clusters,
                    AVG(msg_count) as avg_cluster_size,
                    MAX(msg_count) as max_cluster_size
                FROM dedup_clusters dc
                LEFT JOIN (
                    SELECT cluster_id, COUNT(*) as msg_count
                    FROM cluster_messages
                    GROUP BY cluster_id
                ) cm_stats ON dc.cluster_id = cm_stats.cluster_id
                LEFT JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
            """)
            
            # Статистика по similarity scores
            scores_stats = await conn.fetchrow("""
                SELECT 
                    AVG(similarity_score) as avg_score,
                    MIN(similarity_score) as min_score,
                    MAX(similarity_score) as max_score
                FROM cluster_messages
                WHERE similarity_score IS NOT NULL
            """)
            
            await conn.close()
            
            return {
                'total_clusters': stats['total_clusters'] or 0,
                'total_messages_in_clusters': stats['total_messages_in_clusters'] or 0,
                'avg_cluster_size': round(float(stats['avg_cluster_size']) if stats['avg_cluster_size'] else 0, 2),
                'max_cluster_size': stats['max_cluster_size'] or 0,
                'similarity_score': {
                    'avg': round(float(scores_stats['avg_score']) if scores_stats['avg_score'] else 0, 3),
                    'min': round(float(scores_stats['min_score']) if scores_stats['min_score'] else 0, 3),
                    'max': round(float(scores_stats['max_score']) if scores_stats['max_score'] else 1, 3)
                }
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики кластеризации: {e}")
            return {}

    async def _recluster_large_clusters(self, large_cluster_ids: List[str], embeddings_array: np.ndarray, 
                                       messages_data: List[Dict], min_cluster_size: int, epsilon: float) -> Dict[str, Any]:
        """Автоматическая перекластеризация больших кластеров с более строгими параметрами"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            split_count = 0
            total_new_clusters = 0
            
            for cluster_id in large_cluster_ids:
                try:
                    # Получаем сообщения кластера
                    cluster_messages = await conn.fetch("""
                        SELECT m.id, m.text_content, m.channel_id, m.published_at
                        FROM cluster_messages cm
                        JOIN messages m ON cm.message_id = m.id
                        WHERE cm.cluster_id = $1
                        ORDER BY m.published_at ASC
                    """, cluster_id)
                    
                    if len(cluster_messages) <= 30:
                        continue
                    
                    # Получаем эмбеддинги для сообщений этого кластера
                    cluster_embeddings_list = []
                    cluster_message_data = []
                    for msg_row in cluster_messages:
                        try:
                            emb = await embedding_service.provider.get_embedding(msg_row['text_content'])
                            if emb:
                                cluster_embeddings_list.append(emb)
                                cluster_message_data.append({
                                    'id': msg_row['id'],
                                    'text': msg_row['text_content'],
                                    'channel_id': msg_row['channel_id'],
                                    'published_at': msg_row['published_at']
                                })
                        except Exception as e:
                            logger.warning(f"Ошибка получения эмбеддинга для сообщения {msg_row['id']}: {e}")
                            continue
                    
                    if len(cluster_embeddings_list) < min_cluster_size * 2:
                        continue
                    
                    cluster_embeddings = np.array(cluster_embeddings_list)
                    
                    # Стандартизация
                    from sklearn.preprocessing import StandardScaler
                    scaler = StandardScaler()
                    cluster_embeddings_scaled = scaler.fit_transform(cluster_embeddings)
                    
                    # Используем более строгий epsilon для перекластеризации
                    stricter_epsilon = max(0.01, epsilon * 0.5)  # В два раза строже
                    
                    # Повторная кластеризация с более строгими параметрами
                    reclusterer = hdbscan.HDBSCAN(
                        min_cluster_size=min_cluster_size,
                        min_samples=max(2, min_cluster_size - 1),
                        metric='euclidean',
                        cluster_selection_epsilon=stricter_epsilon,
                        cluster_selection_method='eom',
                        alpha=0.3,
                        leaf_size=10
                    )
                    
                    sub_labels = reclusterer.fit_predict(cluster_embeddings_scaled)
                    n_sub_clusters = len(set(sub_labels)) - (1 if -1 in sub_labels else 0)
                    
                    if n_sub_clusters <= 1:
                        logger.info(f"Кластер {cluster_id[:8]}... не удалось разбить на подкластеры")
                        continue
                    
                    # Группируем по новым меткам
                    sub_clusters = {}
                    for i, sub_label in enumerate(sub_labels):
                        if sub_label == -1:
                            continue
                        if sub_label not in sub_clusters:
                            sub_clusters[sub_label] = []
                        sub_clusters[sub_label].append(cluster_message_data[i])
                    
                    # Удаляем старый кластер и создаём новые
                    await conn.execute("DELETE FROM cluster_messages WHERE cluster_id = $1", cluster_id)
                    await conn.execute("DELETE FROM dedup_clusters WHERE cluster_id = $1", cluster_id)
                    
                    # Создаём новые кластеры
                    for sub_label, sub_messages in sub_clusters.items():
                        if not sub_messages:
                            continue
                        
                        first_msg = sub_messages[0]
                        new_cluster_id = await self._create_new_cluster(
                            message_id=first_msg['id'],
                            text=first_msg['text'],
                            channel_id=first_msg['channel_id'],
                            published_at=first_msg['published_at']
                        )
                        
                        # Вычисляем центроид для этого подкластера (все сообщения подкластера)
                        sub_indices = [i for i, m in enumerate(cluster_message_data) if m['id'] in [sm['id'] for sm in sub_messages]]
                        if sub_indices:
                            sub_embeddings = cluster_embeddings[sub_indices]
                            sub_centroid = np.mean(sub_embeddings, axis=0)
                        else:
                            # Fallback - используем эмбеддинг первого сообщения
                            first_msg_idx = next(i for i, m in enumerate(cluster_message_data) if m['id'] == first_msg['id'])
                            sub_centroid = cluster_embeddings[first_msg_idx]
                        
                        # Добавляем остальные сообщения с реальной similarity
                        def cosine_sim(v1, v2):
                            dot = np.dot(v1, v2)
                            n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
                            return float(dot / (n1 * n2)) if n1 > 0 and n2 > 0 else 0.0
                        
                        for msg in sub_messages[1:]:
                            msg_idx = next(i for i, m in enumerate(cluster_message_data) if m['id'] == msg['id'])
                            msg_emb = cluster_embeddings[msg_idx]
                            similarity = cosine_sim(msg_emb, sub_centroid)
                            
                            await self._add_message_to_cluster(
                                message_id=msg['id'],
                                cluster_id=new_cluster_id,
                                similarity_score=similarity
                            )
                        
                        total_new_clusters += 1
                    
                    split_count += 1
                    logger.info(f"Кластер {cluster_id[:8]}... разбит на {n_sub_clusters} подкластеров")
                    
                except Exception as e:
                    logger.error(f"Ошибка перекластеризации кластера {cluster_id}: {e}")
                    continue
            
            await conn.close()
            
            return {
                'split_clusters': split_count,
                'new_clusters_created': total_new_clusters
            }
            
        except Exception as e:
            logger.error(f"Ошибка перекластеризации больших кластеров: {e}")
            return {
                'split_clusters': 0,
                'new_clusters_created': 0
            }

    async def split_large_clusters(self, max_size: int = 20, inner_threshold: float = 0.9, time_bucket_days: int = 1) -> Dict[str, Any]:
        """Автоматически разделить слишком крупные кластеры на более мелкие.

        Алгоритм:
        1) Находим кластеры с размером > max_size.
        2) Делим по временным сегментам (time_bucket_days).
        3) Внутри сегмента выполняем жадную рекластеризацию по косинусному сходству (порог inner_threshold).
        4) Для каждой подгруппы создаем новый кластер и переносим сообщения.
        5) Исходный крупный кластер удаляется.
        """
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])

            # 1) Находим крупные кластеры
            large_clusters = await conn.fetch(
                """
                SELECT dc.cluster_id, COUNT(cm.message_id) as size
                FROM dedup_clusters dc
                JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
                GROUP BY dc.cluster_id
                HAVING COUNT(cm.message_id) > $1
                ORDER BY size DESC
                """,
                max_size
            )

            if not large_clusters:
                await conn.close()
                return {
                    'status': 'ok',
                    'processed_clusters': 0,
                    'created_clusters': 0,
                    'moved_messages': 0
                }

            processed = 0
            created_total = 0
            moved_total = 0

            for row in large_clusters:
                processed += 1
                cluster_id = row['cluster_id']

                # 2) Получаем сообщения кластера
                messages = await conn.fetch(
                    """
                    SELECT m.id, m.text_content, m.channel_id, m.published_at
                    FROM cluster_messages cm
                    JOIN messages m ON cm.message_id = m.id
                    WHERE cm.cluster_id = $1 AND m.text_content IS NOT NULL AND LENGTH(m.text_content) > 10
                    ORDER BY m.published_at ASC
                    """,
                    cluster_id
                )

                if not messages:
                    # Удаляем пустой кластер на всякий случай
                    await conn.execute("DELETE FROM dedup_clusters WHERE cluster_id = $1", cluster_id)
                    continue

                # 3) Делим по временным сегментам
                from collections import defaultdict
                buckets: Dict[str, List[Any]] = defaultdict(list)
                for m in messages:
                    dt: datetime = m['published_at']
                    # Нормализуем к началу сегмента (кратному time_bucket_days)
                    bucket_key = dt.strftime('%Y-%m-%d')
                    if time_bucket_days > 1:
                        # Простая группировка по floor(day / bucket)
                        # Для стабильности используем номер дня в году // bucket
                        day_index = int(dt.strftime('%j'))
                        year = dt.strftime('%Y')
                        bucket_key = f"{year}-d{(day_index-1)//time_bucket_days}"
                    buckets[bucket_key].append(m)

                # 4) Внутри каждого сегмента — жадная рекластеризация
                subgroups: List[List[Any]] = []
                for _, group_msgs in buckets.items():
                    if len(group_msgs) <= max_size:
                        subgroups.append(group_msgs)
                        continue

                    # Получаем эмбеддинги для группы
                    embeddings: Dict[int, List[float]] = {}
                    for m in group_msgs:
                        try:
                            emb = await embedding_service.provider.get_embedding(m['text_content'])
                        except Exception:
                            emb = None
                        embeddings[m['id']] = emb

                    # Простая косинусная функция
                    from math import sqrt
                    def cosine(a: List[float], b: List[float]) -> float:
                        if not a or not b:
                            return 0.0
                        dot = sum(x*y for x, y in zip(a, b))
                        na = sqrt(sum(x*x for x in a))
                        nb = sqrt(sum(y*y for y in b))
                        if na == 0 or nb == 0:
                            return 0.0
                        return dot / (na * nb)

                    # Жадная группировка
                    remaining = list(group_msgs)
                    while remaining:
                        seed = remaining.pop(0)
                        seed_emb = embeddings.get(seed['id'])
                        current_group = [seed]
                        rest = []
                        for m in remaining:
                            sim = cosine(seed_emb, embeddings.get(m['id']))
                            if sim >= inner_threshold and len(current_group) < max_size:
                                current_group.append(m)
                            else:
                                rest.append(m)
                        subgroups.append(current_group)
                        remaining = rest

                # 5) Создаем новые кластеры и переносим сообщения
                created_for_this = 0
                moved_for_this = 0
                new_cluster_ids: List[str] = []
                for subgroup in subgroups:
                    if not subgroup:
                        continue
                    # Создаем первый кластер под группу
                    first = subgroup[0]
                    new_cluster_id = await self._create_new_cluster(
                        message_id=first['id'],
                        text=first['text_content'],
                        channel_id=first['channel_id'],
                        published_at=first['published_at']
                    )
                    new_cluster_ids.append(new_cluster_id)
                    created_for_this += 1

                    # Добавляем остальные сообщения в новый кластер
                    for m in subgroup[1:]:
                        try:
                            # Оценим сходство с первым сообщением подгруппы
                            emb_first = await embedding_service.provider.get_embedding(first['text_content'])
                            emb_cur = await embedding_service.provider.get_embedding(m['text_content'])
                            # Косинус
                            from math import sqrt
                            def cos(a, b):
                                if not a or not b:
                                    return 0.0
                                dot = sum(x*y for x, y in zip(a, b))
                                na = sqrt(sum(x*x for x in a))
                                nb = sqrt(sum(y*y for y in b))
                                if na == 0 or nb == 0:
                                    return 0.0
                                return dot / (na * nb)
                            score = cos(emb_first, emb_cur)
                            await self._add_message_to_cluster(m['id'], new_cluster_id, score)
                            moved_for_this += 1
                        except Exception:
                            # В случае ошибки всё равно пробуем добавить с дефолтным скором
                            await self._add_message_to_cluster(m['id'], new_cluster_id, 0.0)
                            moved_for_this += 1

                # 6) Удаляем исходный крупный кластер и его связи
                await conn.execute("DELETE FROM cluster_messages WHERE cluster_id = $1", cluster_id)
                await conn.execute("DELETE FROM dedup_clusters WHERE cluster_id = $1", cluster_id)

                created_total += created_for_this
                moved_total += moved_for_this

            await conn.close()

            return {
                'status': 'ok',
                'processed_clusters': processed,
                'created_clusters': created_total,
                'moved_messages': moved_total,
                'params': {
                    'max_size': max_size,
                    'inner_threshold': inner_threshold,
                    'time_bucket_days': time_bucket_days
                }
            }
        except Exception as e:
            logger.error(f"Ошибка автосплита крупных кластеров: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    async def run_clustering(self, limit: int = 1000, min_cluster_size: int = 3, pca_dimensions: int = 50, 
                           time_window_days: int = 7, cluster_selection_epsilon: float = None, 
                           disable_pca: bool = False, max_title_texts: int = 10, 
                           max_title_chars_per_text: int = 500) -> Dict[str, Any]:
        """Запустить HDBSCAN кластеризацию с PCA сжатием векторов
        
        Args:
            limit: максимальное количество сообщений для кластеризации
            min_cluster_size: минимальный размер кластера
            pca_dimensions: размерность после PCA сжатия
            time_window_days: временное окно для кластеризации
            cluster_selection_epsilon: параметр epsilon для HDBSCAN (если None, используется адаптивный)
            disable_pca: если True, PCA не применяется
        
        Returns:
            Dict с результатами кластеризации
        """
        # Проверяем доступность HDBSCAN и PCA
        if not HDBSCAN_AVAILABLE:
            return {
                'status': 'error',
                'message': 'HDBSCAN не установлен. Установите: pip install hdbscan'
            }
        
        if not PCA_AVAILABLE:
            return {
                'status': 'error',
                'message': 'PCA не доступен. Установите: pip install scikit-learn'
            }
        
        try:
            # Сохраняем параметры для генерации заголовков
            self._current_max_title_texts = max_title_texts
            self._current_max_title_chars_per_text = max_title_chars_per_text
            
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Очищаем существующие кластеры для перезапуска
            logger.info("Очистка существующих кластеров...")
            await conn.execute("DELETE FROM cluster_messages")
            await conn.execute("DELETE FROM dedup_clusters")
            
            # Получаем сообщения за заданное время
            cutoff_date = datetime.now() - timedelta(days=time_window_days)
            rows = await conn.fetch("""
                SELECT m.id, m.text_content, m.channel_id, m.published_at
                FROM messages m
                JOIN embeddings e ON m.id = e.message_id
                WHERE m.published_at >= $1
                  AND m.text_content IS NOT NULL
                  AND LENGTH(m.text_content) > 10
                ORDER BY m.published_at ASC
                LIMIT $2
            """, cutoff_date, limit)
            
            if not rows:
                await conn.close()
                return {
                    'status': 'ok',
                    'message': 'Нет сообщений для кластеризации',
                    'clusters_created': 0,
                    'messages_processed': 0
                }
            
            # Подготовка данных
            message_ids = []
            embeddings_list = []
            messages_data = []
            
            for row in rows:
                try:
                    # Получаем эмбеддинг из Qdrant через embedding_service
                    msg_text = row['text_content']
                    emb = await embedding_service.provider.get_embedding(msg_text)
                    
                    if emb and len(emb) > 0:
                        message_ids.append(row['id'])
                        embeddings_list.append(emb)
                        messages_data.append({
                            'id': row['id'],
                            'text': row['text_content'],
                            'channel_id': row['channel_id'],
                            'published_at': row['published_at']
                        })
                except Exception as e:
                    logger.warning(f"Ошибка получения эмбеддинга для сообщения {row['id']}: {e}")
                    continue
            
            if len(embeddings_list) < min_cluster_size:
                await conn.close()
                return {
                    'status': 'error',
                    'message': f'Недостаточно сообщений для кластеризации (требуется минимум {min_cluster_size})'
                }
            
            # Преобразуем в numpy array
            embeddings_array = np.array(embeddings_list)
            logger.info(f"Подготовлено {len(embeddings_array)} сообщений с размерностью {embeddings_array.shape[1]}")
            
            # Предобработка данных - стандартизация эмбеддингов
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            embeddings_scaled = scaler.fit_transform(embeddings_array)
            logger.info("Применена стандартизация эмбеддингов")
            
            # PCA сжатие (если не отключено)
            n_samples, n_features = embeddings_array.shape
            
            if disable_pca:
                embeddings_reduced = embeddings_scaled
                explained_variance = 1.0
                logger.info("PCA отключен пользователем, используем исходные векторы")
            else:
                # Адаптивный выбор количества компонент
                if n_samples < 50:
                    # Для малых данных используем меньше компонент
                    target_dims = min(pca_dimensions, n_features // 2)
                elif n_samples < 200:
                    # Для средних данных используем больше компонент
                    target_dims = min(pca_dimensions * 2, n_features - 1)
                else:
                    # Для больших данных используем максимум компонент
                    target_dims = min(pca_dimensions * 3, n_features - 1)
                
                # n_components должен быть < min(n_samples, n_features)
                max_allowed = max(1, min(n_samples - 1, n_features - 1))
                n_components = min(target_dims, max_allowed)
                
                if n_components < n_features and n_components >= 10:
                    logger.info(f"Применяем улучшенное PCA сжатие: {n_features} -> {n_components} измерений (samples={n_samples})")
                    pca = PCA(n_components=n_components, svd_solver='auto', random_state=42)
                    embeddings_reduced = pca.fit_transform(embeddings_scaled)
                    try:
                        explained_variance = float(np.sum(pca.explained_variance_ratio_))
                    except Exception:
                        explained_variance = 0.0
                    logger.info(f"PCA объясняет {explained_variance:.2%} дисперсии")
                    
                    # Предупреждение если объясненная дисперсия слишком мала
                    if explained_variance < 0.8:
                        logger.warning(f"PCA объясняет только {explained_variance:.2%} дисперсии - возможно, слишком агрессивное сжатие")
                else:
                    embeddings_reduced = embeddings_scaled
                    explained_variance = 1.0
                    logger.info(f"Пропускаем PCA сжатие (компонент: {n_components}, признаков: {n_features})")
            
            # HDBSCAN кластеризация с PCA сжатием
            logger.info(f"Запуск HDBSCAN кластеризации с PCA сжатием")
            logger.info(f"Размер данных: {len(embeddings_reduced)} сообщений, {embeddings_reduced.shape[1]} измерений")
            
            try:
                # HDBSCAN кластеризация с оптимизированными параметрами
                # Адаптивные параметры в зависимости от размера данных
                if n_samples < 50:
                    # Для малых данных - более консервативные параметры
                    adaptive_min_cluster = max(2, min_cluster_size)
                    default_epsilon = 0.2
                    adaptive_alpha = 0.7
                elif n_samples < 200:
                    # Для средних данных - сбалансированные параметры
                    adaptive_min_cluster = max(2, min_cluster_size - 1)
                    default_epsilon = 0.3
                    adaptive_alpha = 0.5
                else:
                    # Для больших данных - более агрессивные параметры
                    adaptive_min_cluster = max(2, min_cluster_size - 1)
                    default_epsilon = 0.4
                    adaptive_alpha = 0.3
                
                # Используем переданный epsilon или адаптивный
                final_epsilon = cluster_selection_epsilon if cluster_selection_epsilon is not None else default_epsilon
                
                clusterer = hdbscan.HDBSCAN(
                    min_cluster_size=adaptive_min_cluster,
                    min_samples=max(2, adaptive_min_cluster - 1),
                    metric='euclidean',
                    cluster_selection_epsilon=final_epsilon,
                    cluster_selection_method='eom',
                    alpha=adaptive_alpha,
                    leaf_size=20 if n_samples > 100 else 10
                )
                
                logger.info(f"HDBSCAN параметры: min_cluster_size={adaptive_min_cluster}, epsilon={final_epsilon}, alpha={adaptive_alpha}")
                
                cluster_labels = clusterer.fit_predict(embeddings_reduced)
                
                # Анализ результатов HDBSCAN
                n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
                n_noise = list(cluster_labels).count(-1)
                
                logger.info(f"HDBSCAN: создано {n_clusters} кластеров, {n_noise} шумовых сообщений")
                
                # Если HDBSCAN не дал результатов, пробуем альтернативные алгоритмы
                if n_clusters == 0:
                    logger.warning("HDBSCAN не создал кластеров, пробуем альтернативные алгоритмы")
                    
                    # 1. Пробуем DBSCAN
                    try:
                        from sklearn.cluster import DBSCAN
                        from sklearn.neighbors import NearestNeighbors
                        
                        # Адаптивный выбор eps для DBSCAN
                        nbrs = NearestNeighbors(n_neighbors=adaptive_min_cluster).fit(embeddings_reduced)
                        distances, indices = nbrs.kneighbors(embeddings_reduced)
                        distances = np.sort(distances[:, adaptive_min_cluster-1], axis=0)
                        eps = distances[int(len(distances) * 0.1)]  # 10-й процентиль
                        
                        dbscan = DBSCAN(eps=eps, min_samples=adaptive_min_cluster)
                        cluster_labels = dbscan.fit_predict(embeddings_reduced)
                        n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
                        n_noise = list(cluster_labels).count(-1)
                        
                        if n_clusters > 0:
                            logger.info(f"DBSCAN: создано {n_clusters} кластеров, {n_noise} шумовых (eps={eps:.3f})")
                        else:
                            raise Exception("DBSCAN не создал кластеров")
                            
                    except Exception as e:
                        logger.warning(f"DBSCAN не сработал: {e}")
                        
                        # 2. Пробуем K-means
                        try:
                            from sklearn.cluster import KMeans
                            from sklearn.metrics import silhouette_score
                            
                            best_k = 2
                            best_score = -1
                            
                            # Тестируем разное количество кластеров
                            for n_clusters_k in range(2, min(20, len(embeddings_reduced) // 2) + 1):
                                if n_clusters_k < len(embeddings_reduced):
                                    kmeans = KMeans(n_clusters=n_clusters_k, random_state=42, n_init=10)
                                    labels = kmeans.fit_predict(embeddings_reduced)
                                    
                                    if len(set(labels)) > 1:
                                        score = silhouette_score(embeddings_reduced, labels)
                                        if score > best_score:
                                            best_score = score
                                            best_k = n_clusters_k
                            
                            # Финальная кластеризация с лучшим k
                            kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
                            cluster_labels = kmeans.fit_predict(embeddings_reduced)
                            n_clusters = best_k
                            n_noise = 0
                            logger.info(f"K-means: создано {n_clusters} кластеров (silhouette={best_score:.3f})")
                            
                        except Exception as e2:
                            logger.warning(f"K-means не сработал: {e2}")
                            # В крайнем случае создаем одиночные кластеры
                            cluster_labels = list(range(len(embeddings_reduced)))
                            n_clusters = len(embeddings_reduced)
                            n_noise = 0
                            logger.warning("Создаем одиночные кластеры как последний fallback")
                
                # Если и K-means не сработал, создаем одиночные кластеры
                if n_clusters == 0:
                    logger.warning("Все методы кластеризации не сработали, создаем одиночные кластеры")
                    cluster_labels = list(range(len(embeddings_reduced)))
                    n_clusters = len(embeddings_reduced)
                    n_noise = 0
                
            except Exception as e:
                logger.error(f"Ошибка HDBSCAN кластеризации: {e}")
                # В крайнем случае создаем одиночные кластеры
                cluster_labels = list(range(len(embeddings_reduced)))
                n_clusters = len(embeddings_reduced)
                n_noise = 0
            
            # Анализ результатов (уже выполнен выше)
            
            # Создаем кластеры в БД
            cluster_map = {}  # label -> cluster_id
            messages_processed = 0
            
            # Сначала группируем сообщения по меткам кластеров
            clusters_by_label = {}
            for i, label in enumerate(cluster_labels):
                if label not in clusters_by_label:
                    clusters_by_label[label] = []
                clusters_by_label[label].append(messages_data[i])
            
            # Вычисляем центроиды кластеров для корректного расчёта similarity_score
            cluster_centroids = {}
            for label, indices in clusters_by_label.items():
                if label == -1:  # Пропускаем шум
                    continue
                cluster_indices = [messages_data.index(m) for m in clusters_by_label[label]]
                if len(cluster_indices) > 0:
                    cluster_embeddings = embeddings_array[cluster_indices]
                    centroid = np.mean(cluster_embeddings, axis=0)
                    cluster_centroids[label] = centroid
            
            # Функция для вычисления косинусной близости
            def cosine_similarity(vec1, vec2):
                """Вычислить косинусную близость между двумя векторами"""
                dot_product = np.dot(vec1, vec2)
                norm1 = np.linalg.norm(vec1)
                norm2 = np.linalg.norm(vec2)
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                return float(dot_product / (norm1 * norm2))
            
            # Создаем кластеры для каждой группы
            similarity_stats_per_cluster = {}  # Для анализа распределения similarity
            
            for label, messages in clusters_by_label.items():
                if label == -1:  # Пропускаем шумовые сообщения
                    continue
                    
                # Первое сообщение создает кластер
                first_msg = messages[0]
                cluster_id = await self._create_new_cluster(
                    message_id=first_msg['id'],
                    text=first_msg['text'],
                    channel_id=first_msg['channel_id'],
                    published_at=first_msg['published_at']
                )
                cluster_map[label] = cluster_id
                messages_processed += 1
                
                # Получаем индекс первого сообщения в массивах
                first_msg_index = next(i for i, m in enumerate(messages_data) if m['id'] == first_msg['id'])
                first_msg_embedding = embeddings_array[first_msg_index]
                
                # Если есть центроид, используем его, иначе используем первое сообщение
                centroid = cluster_centroids.get(label, first_msg_embedding)
                
                # Список similarity scores для этого кластера
                cluster_similarities = []
                
                # Первое сообщение всегда имеет similarity 1.0 (это "якорь" кластера)
                # similarity_score=1.0 уже установлен при создании кластера в _create_new_cluster
                cluster_similarities.append(1.0)
                
                # Остальные сообщения добавляем к кластеру с реальной similarity
                for msg in messages[1:]:
                    msg_index = next(i for i, m in enumerate(messages_data) if m['id'] == msg['id'])
                    msg_embedding = embeddings_array[msg_index]
                    
                    # Вычисляем косинусную близость к центроиду кластера
                    similarity = cosine_similarity(msg_embedding, centroid)
                    cluster_similarities.append(similarity)
                    
                    await self._add_message_to_cluster(
                        message_id=msg['id'],
                        cluster_id=cluster_id,
                        similarity_score=similarity
                    )
                    messages_processed += 1
                
                # Сохраняем статистику similarity для этого кластера
                if cluster_similarities:
                    similarity_stats_per_cluster[cluster_id] = {
                        'min': float(np.min(cluster_similarities)),
                        'max': float(np.max(cluster_similarities)),
                        'avg': float(np.mean(cluster_similarities)),
                        'median': float(np.median(cluster_similarities)),
                        'std': float(np.std(cluster_similarities)),
                        'values': [float(v) for v in cluster_similarities]
                    }
                    logger.info(f"Кластер {cluster_id[:8]}...: similarity min={similarity_stats_per_cluster[cluster_id]['min']:.3f}, "
                              f"max={similarity_stats_per_cluster[cluster_id]['max']:.3f}, "
                              f"avg={similarity_stats_per_cluster[cluster_id]['avg']:.3f}")
            
            # Вычисляем метрики качества
            silhouette_avg = None
            if n_clusters > 1 and len(embeddings_reduced) > n_clusters:
                try:
                    from sklearn.metrics import silhouette_score
                    # Для экономии памяти берем подвыборку
                    sample_size = min(1000, len(embeddings_reduced))
                    indices = np.random.choice(len(embeddings_reduced), sample_size, replace=False)
                    silhouette_avg = float(silhouette_score(
                        embeddings_reduced[indices],
                        cluster_labels[indices]
                    ))
                except Exception as e:
                    logger.warning(f"Не удалось вычислить silhouette score: {e}")
            
            # Автоматическая перекластеризация больших кластеров
            large_clusters_split = {}
            if len(cluster_map) > 0:
                # Находим большие кластеры (более 30 сообщений)
                large_cluster_ids = []
                for label, cluster_id in cluster_map.items():
                    if label in clusters_by_label:
                        cluster_size = len(clusters_by_label[label])
                        if cluster_size > 30:
                            large_cluster_ids.append(cluster_id)
                
                if large_cluster_ids:
                    logger.info(f"Найдено {len(large_cluster_ids)} больших кластеров для перекластеризации")
                    split_result = await self._recluster_large_clusters(
                        large_cluster_ids, 
                        embeddings_array, 
                        messages_data,
                        min_cluster_size=max(2, min_cluster_size),
                        epsilon=final_epsilon if cluster_selection_epsilon is not None else 0.05
                    )
                    large_clusters_split = split_result
            
            await conn.close()
            
            # Агрегированная статистика по similarity
            all_similarities = []
            for stats in similarity_stats_per_cluster.values():
                all_similarities.extend(stats['values'])
            
            similarity_global_stats = {}
            if all_similarities:
                similarity_global_stats = {
                    'min': float(np.min(all_similarities)),
                    'max': float(np.max(all_similarities)),
                    'avg': float(np.mean(all_similarities)),
                    'median': float(np.median(all_similarities)),
                    'std': float(np.std(all_similarities))
                }
            
            return {
                'status': 'ok',
                'clusters_created': len(cluster_map),
                'messages_processed': messages_processed,
                'noise_messages': n_noise,
                'metrics': {
                    'silhouette_score': round(silhouette_avg, 3) if silhouette_avg else None,
                    'pca_variance_explained': round(explained_variance, 3),
                    'original_dimensions': embeddings_array.shape[1],
                    'reduced_dimensions': embeddings_reduced.shape[1],
                    'similarity_distribution': similarity_global_stats,
                    'similarity_per_cluster': similarity_stats_per_cluster
                },
                'params': {
                    'min_cluster_size': min_cluster_size,
                    'pca_dimensions': pca_dimensions,
                    'time_window_days': time_window_days,
                    'limit': limit,
                    'cluster_selection_epsilon': final_epsilon,
                    'disable_pca': disable_pca
                },
                'large_clusters_split': large_clusters_split
            }
            
        except Exception as e:
            logger.error(f"Ошибка HDBSCAN кластеризации: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

# Глобальный экземпляр сервиса (для обратной совместимости сохраняем старое имя)
deduplication_service = SemanticClusteringService()
clustering_service = SemanticClusteringService()  # Новое имя для использования в коде
