"""
Основной модуль Pro-режима
Координация всех сервисов и API endpoints
"""

import asyncio
import logging
import json
import statistics
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import asyncpg
from config_utils import get_config
logger = logging.getLogger(__name__)

class ProModeService:
    """Основной сервис Pro-режима"""
    
    def __init__(self):
        self.initialized = False
        self._embedding_service = None
        self._deduplication_service = None
        self._classification_service = None
        self._onboarding_service = None
    
    async def initialize(self):
        """Инициализация всех сервисов"""
        try:
            await self._get_embedding_service().initialize()
            self.initialized = True
            logger.info("Pro-режим инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации Pro-режима: {e}")
            raise

    def initialize_sync(self):
        """Синхронная обёртка для инициализации (удобно для фоновых задач)"""
        if not self.initialized:
            import asyncio as _asyncio
            _asyncio.run(self.initialize())
    
    async def process_new_message(self, message_id: int, text: str, channel_id: int, 
                                published_at: datetime) -> Dict[str, Any]:
        """Обработать новое сообщение: классификация + дедупликация"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Классификация по темам
            classifications = await self._get_classification_service().classify_message(message_id, text)
            
            # Дедупликация и создание/обновление событий
            cluster_id = await self._get_deduplication_service().process_new_message(
                message_id, text, channel_id, published_at
            )
            
            return {
                'message_id': message_id,
                'classifications': classifications,
                'cluster_id': cluster_id,
                'processed_at': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения {message_id}: {e}")
            raise
    
    async def search_semantic(self, query: str, filters: Optional[Dict[str, Any]] = None, 
                            limit: int = 20) -> List[Dict[str, Any]]:
        """Семантический поиск"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Поиск через Qdrant
            results = await self._get_embedding_service().search_semantic(query, limit, filters)
            
            # Дополняем результаты информацией из БД
            enriched_results = []
            for result in results:
                payload = result.get('payload', {})
                # Поддерживаем как post_id (из posts_search), так и message_id (из старой коллекции)
                message_id = payload.get('message_id') or payload.get('post_id')
                
                if not message_id:
                    logger.warning(f"Пропущен результат без message_id/post_id: {payload}")
                    continue
                
                # Получаем полную информацию о сообщении
                message_info = await self._get_message_info(message_id)
                if message_info:
                    enriched_results.append({
                        'message_id': message_id,
                        'score': result['score'],
                        'text': message_info['text'],
                        'channel_name': message_info['channel_name'],
                        'published_at': message_info['published_at'],
                        'views': message_info['views'],
                        'forwards': message_info['forwards'],
                        'topics': message_info['topics']
                    })
                else:
                    # Если нет информации в БД, используем данные из payload
                    text_preview = payload.get('text', '')[:500] if payload.get('text') else ''
                    enriched_results.append({
                        'message_id': message_id,
                        'score': result['score'],
                        'text': text_preview,
                        'channel_name': None,
                        'published_at': payload.get('timestamp'),
                        'views': None,
                        'forwards': None,
                        'topics': []
                    })
            
            return enriched_results
            
        except Exception as e:
            logger.error(f"Ошибка семантического поиска: {e}")
            raise
    
    async def get_trending_events(self, period: str = 'daily', limit: int = 10) -> List[Dict[str, Any]]:
        """Получить трендовые события (кластеры) с расширенной аналитикой"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Определяем временной диапазон
            if period == 'daily':
                date_from = datetime.now() - timedelta(days=1)
                prev_period_from = datetime.now() - timedelta(days=2)
            elif period == 'weekly':
                date_from = datetime.now() - timedelta(weeks=1)
                prev_period_from = datetime.now() - timedelta(weeks=2)
            elif period == 'monthly':
                date_from = datetime.now() - timedelta(days=30)
                prev_period_from = datetime.now() - timedelta(days=60)
            else:
                date_from = datetime.now() - timedelta(days=1)
                prev_period_from = datetime.now() - timedelta(days=2)
            
            # Получаем трендовые события с динамикой
            # Группируем по событиям (dedup_clusters), а не по темам
            query = """
                WITH current_period AS (
                    SELECT 
                        dc.cluster_id,
                        dc.id as event_id,
                        dc.title, 
                        dc.summary,
                        dc.primary_topic_id,
                        COALESCE(t.name, 'Без темы') as topic_name,
                        COALESCE(t.color, '#808080') as topic_color,
                        COUNT(DISTINCT cm.message_id) as message_count,
                        AVG(cm.similarity_score) as avg_similarity,
                        COUNT(DISTINCT m.channel_id) as channel_count,
                        SUM(COALESCE(m.views_count, 0)) as total_views,
                        SUM(COALESCE(m.forwards_count, 0)) as total_forwards,
                        MIN(m.published_at) as first_mention_at,
                        MAX(m.published_at) as last_mention_at
                    FROM dedup_clusters dc
                    JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
                    JOIN messages m ON cm.message_id = m.id
                    LEFT JOIN topics t ON dc.primary_topic_id = t.id
                    WHERE m.published_at >= $1
                    GROUP BY dc.cluster_id, dc.id, dc.title, dc.summary, dc.primary_topic_id, t.name, t.color
                    HAVING COUNT(DISTINCT cm.message_id) >= 2  -- Минимум 2 сообщения для значимого события
                ),
                previous_period AS (
                    SELECT 
                        dc.cluster_id,
                        COUNT(DISTINCT cm.message_id) as prev_message_count,
                        AVG(cm.similarity_score) as prev_avg_similarity,
                        COUNT(DISTINCT m.channel_id) as prev_channel_count,
                        SUM(COALESCE(m.views_count, 0)) as prev_total_views,
                        SUM(COALESCE(m.forwards_count, 0)) as prev_total_forwards
                    FROM dedup_clusters dc
                    JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
                    JOIN messages m ON cm.message_id = m.id
                    WHERE m.published_at >= $2 AND m.published_at < $1
                    GROUP BY dc.cluster_id
                )
                SELECT 
                    cp.cluster_id,
                    cp.event_id,
                    cp.title, 
                    cp.summary,
                    cp.primary_topic_id,
                    cp.topic_name,
                    cp.topic_color,
                    cp.message_count, 
                    cp.avg_similarity, 
                    cp.channel_count,
                    cp.total_views, 
                    cp.total_forwards,
                    cp.first_mention_at,
                    cp.last_mention_at,
                    COALESCE(pp.prev_message_count, 0) as prev_message_count,
                    COALESCE(pp.prev_avg_similarity, 0) as prev_avg_similarity,
                    COALESCE(pp.prev_channel_count, 0) as prev_channel_count,
                    COALESCE(pp.prev_total_views, 0) as prev_total_views,
                    COALESCE(pp.prev_total_forwards, 0) as prev_total_forwards,
                    CASE 
                        WHEN COALESCE(pp.prev_message_count, 0) = 0 THEN 100.0
                        ELSE CAST(((cp.message_count::float - pp.prev_message_count::float) / pp.prev_message_count::float) * 100::float AS NUMERIC(10,1))
                    END as growth_percentage,
                    CASE 
                        WHEN COALESCE(pp.prev_avg_similarity, 0) = 0 THEN 0.0
                        ELSE CAST((cp.avg_similarity - pp.prev_avg_similarity)::float AS NUMERIC(10,3))
                    END as similarity_change
                FROM current_period cp
                LEFT JOIN previous_period pp ON cp.cluster_id = pp.cluster_id
                ORDER BY cp.message_count DESC, cp.total_views DESC
                LIMIT $3
            """
            
            rows = await conn.fetch(query, date_from, prev_period_from, limit)
            
            trends = []
            for row in rows:
                # Определяем тренд (рост/падение/стабильность)
                if row['growth_percentage'] > 10:
                    trend_direction = 'up'
                    trend_icon = '📈'
                elif row['growth_percentage'] < -10:
                    trend_direction = 'down'
                    trend_icon = '📉'
                else:
                    trend_direction = 'stable'
                    trend_icon = '➡️'
                
                # Рассчитываем популярность (комбинированная метрика)
                # Для событий используем другие веса: больше внимания к количеству сообщений и просмотров
                popularity_score = (
                    row['message_count'] * 0.5 +  # Вес 50% - количество сообщений о событии
                    min(row['total_views'] / 10000, 100) * 0.3 +  # Вес 30% - охват
                    row['channel_count'] * 2 * 0.15 +  # Вес 15% - количество источников (×2 для усиления)
                    float(row['avg_similarity']) * 100 * 0.05  # Вес 5% - качество кластеризации
                )
                
                trends.append({
                    'cluster_id': row['cluster_id'],
                    'event_id': row['event_id'],
                    'title': row['title'] or 'Без названия',
                    'summary': row['summary'] or '',
                    'topic_id': row['primary_topic_id'],
                    'topic_name': row['topic_name'],
                    'topic_color': row['topic_color'],
                    'message_count': row['message_count'],
                    'avg_similarity': float(row['avg_similarity']),
                    'channel_count': row['channel_count'],
                    'total_views': row['total_views'],
                    'total_forwards': row['total_forwards'],
                    'first_mention_at': row['first_mention_at'].isoformat() if row['first_mention_at'] else None,
                    'last_mention_at': row['last_mention_at'].isoformat() if row['last_mention_at'] else None,
                    'growth_percentage': float(row['growth_percentage']),
                    'similarity_change': float(row['similarity_change']),
                    'trend_direction': trend_direction,
                    'trend_icon': trend_icon,
                    'popularity_score': round(popularity_score, 1),
                    'prev_message_count': row['prev_message_count'],
                    'prev_avg_similarity': float(row['prev_avg_similarity']),
                    'prev_channel_count': row['prev_channel_count']
                })
            
            await conn.close()
            return trends
            
        except Exception as e:
            logger.error(f"Ошибка получения трендов событий: {e}")
            raise
    
    async def get_trending_events_with_spikes(self, window_hours: int = 6, z_threshold: float = 2.0, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Получить трендовые события (кластеры) с обнаружением всплесков интереса
        
        Логика:
        - Скользящее окно window_hours часов
        - Считаем количество сообщений события в каждом окне
        - Если значение сильно выше среднего (z-score > threshold), помечаем всплеск
        - Ранжируем события: всплесковые выше
        
        Args:
            window_hours: Размер скользящего окна в часах (по умолчанию 6)
            z_threshold: Порог z-score для обнаружения всплеска (по умолчанию 2.0)
            limit: Максимальное количество событий для возврата
            
        Returns:
            Список событий с информацией о всплесках
        """
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Временной диапазон для анализа: последние 7 дней (для расчета статистики)
            now = datetime.now(timezone.utc)
            analysis_start = now - timedelta(days=7)
            current_window_start = now - timedelta(hours=window_hours)
            
            # Получаем все события (кластеры) с их сообщениями за период анализа
            query = """
                SELECT 
                    dc.cluster_id,
                    dc.id as event_id,
                    dc.title,
                    dc.summary,
                    dc.primary_topic_id,
                    COALESCE(t.name, 'Без темы') as topic_name,
                    COALESCE(t.color, '#808080') as topic_color,
                    m.id as message_id,
                    m.published_at
                FROM dedup_clusters dc
                JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
                JOIN messages m ON cm.message_id = m.id
                LEFT JOIN topics t ON dc.primary_topic_id = t.id
                WHERE m.published_at >= $1
                ORDER BY dc.cluster_id, m.published_at
            """
            
            rows = await conn.fetch(query, analysis_start)
            
            # Группируем сообщения по событиям (кластерам)
            events_data = {}
            for row in rows:
                cluster_id = row['cluster_id']
                if cluster_id not in events_data:
                    events_data[cluster_id] = {
                        'cluster_id': cluster_id,
                        'event_id': row['event_id'],
                        'title': row['title'],
                        'summary': row['summary'],
                        'primary_topic_id': row['primary_topic_id'],
                        'topic_name': row['topic_name'],
                        'topic_color': row['topic_color'],
                        'messages': []
                    }
                # Приводим datetime к timezone-aware, если он naive
                msg_time = row['published_at']
                if msg_time.tzinfo is None:
                    msg_time = msg_time.replace(tzinfo=timezone.utc)
                events_data[cluster_id]['messages'].append(msg_time)
            
            # Получаем информацию о каналах и схожести для всех событий одним запросом
            channel_query = """
                SELECT 
                    dc.cluster_id,
                    COUNT(DISTINCT m.channel_id) as channel_count,
                    SUM(COALESCE(m.views_count, 0)) as total_views,
                    SUM(COALESCE(m.forwards_count, 0)) as total_forwards,
                    AVG(cm.similarity_score) as avg_similarity
                FROM dedup_clusters dc
                JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
                JOIN messages m ON cm.message_id = m.id
                WHERE m.published_at >= $1
                GROUP BY dc.cluster_id
            """
            channel_rows = await conn.fetch(channel_query, current_window_start)
            channel_info = {
                row['cluster_id']: {
                    'channel_count': row['channel_count'],
                    'total_views': row['total_views'],
                    'total_forwards': row['total_forwards'],
                    'avg_similarity': float(row['avg_similarity']) if row['avg_similarity'] is not None else 0.0
                }
                for row in channel_rows
            }
            await conn.close()
            
            # Анализируем каждое событие на всплески
            results = []
            window_delta = timedelta(hours=window_hours)
            
            for cluster_id, event_info in events_data.items():
                messages = sorted(event_info['messages'])
                
                if len(messages) < 3:  # Минимум 3 сообщения для статистики
                    continue
                
                # Разбиваем временной ряд на окна и считаем количество сообщений в каждом
                window_counts = []
                current_time = analysis_start
                
                while current_time < now:
                    window_end = current_time + window_delta
                    count = sum(1 for msg_time in messages if current_time <= msg_time < window_end)
                    if count > 0:  # Учитываем только окна с сообщениями
                        window_counts.append(count)
                    current_time += timedelta(hours=1)  # Сдвигаем окно на 1 час
                
                if len(window_counts) < 3:  # Нужно минимум 3 окна для статистики
                    continue
                
                # Вычисляем статистику
                mean_count = statistics.mean(window_counts)
                if len(window_counts) > 1:
                    stdev_count = statistics.stdev(window_counts)
                else:
                    stdev_count = 0.0
                
                # Текущее окно (последние window_hours часов)
                current_count = sum(1 for msg_time in messages if msg_time >= current_window_start)
                
                # Вычисляем z-score для текущего окна
                if stdev_count > 0:
                    z_score = (current_count - mean_count) / stdev_count
                else:
                    z_score = 0.0
                
                # Определяем всплеск
                is_spike = z_score > z_threshold
                
                # Общая статистика по событию
                total_messages = len(messages)
                recent_messages = current_count
                
                # Получаем информацию о каналах и схожести
                info = channel_info.get(cluster_id, {
                    'channel_count': 0,
                    'total_views': 0,
                    'total_forwards': 0,
                    'avg_similarity': 0.0
                })
                
                # Рассчитываем популярность (с бонусом за всплеск)
                popularity_score = (
                    total_messages * 0.4 +
                    recent_messages * 0.3 +
                    info['channel_count'] * 2 * 0.2 +
                    (z_score * 10 if is_spike else 0) * 0.1  # Бонус за всплеск
                )
                
                results.append({
                    'cluster_id': cluster_id,
                    'event_id': event_info['event_id'],
                    'title': event_info['title'] or 'Без названия',
                    'summary': event_info['summary'] or '',
                    'topic_id': event_info['primary_topic_id'],
                    'topic_name': event_info['topic_name'],
                    'topic_color': event_info['topic_color'],
                    'total_messages': total_messages,
                    'recent_messages': recent_messages,  # В последнем окне
                    'channel_count': info['channel_count'],
                    'total_views': info['total_views'],
                    'total_forwards': info['total_forwards'],
                    'avg_similarity': round(info['avg_similarity'], 3),
                    'mean_count': round(mean_count, 2),
                    'stdev_count': round(stdev_count, 2),
                    'current_count': current_count,
                    'z_score': round(z_score, 2),
                    'is_spike': is_spike,
                    'spike_intensity': round(z_score, 2) if is_spike else 0.0,
                    'popularity_score': round(popularity_score, 1),
                    'window_hours': window_hours,
                    'first_mention_at': messages[0].isoformat() if messages else None,
                    'last_mention_at': messages[-1].isoformat() if messages else None
                })
            
            # Сортируем: сначала всплесковые (по z-score), потом остальные (по popularity_score)
            results.sort(key=lambda x: (
                not x['is_spike'],  # Всплесковые первыми
                -x['z_score'] if x['is_spike'] else -x['popularity_score']  # По убыванию
            ))
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Ошибка получения трендовых событий со всплесками: {e}", exc_info=True)
            raise
    
    async def get_trending_topics_with_spikes(self, window_hours: int = 6, z_threshold: float = 2.0, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Получить трендовые темы с обнаружением всплесков интереса
        
        Логика:
        - Скользящее окно window_hours часов
        - Считаем количество постов темы в каждом окне
        - Если значение сильно выше среднего (z-score > threshold), помечаем всплеск
        - Ранжируем темы: всплесковые выше
        
        Args:
            window_hours: Размер скользящего окна в часах (по умолчанию 6)
            z_threshold: Порог z-score для обнаружения всплеска (по умолчанию 2.0)
            limit: Максимальное количество тем для возврата
            
        Returns:
            Список тем с информацией о всплесках
        """
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Временной диапазон для анализа: последние 7 дней (для расчета статистики)
            # Используем UTC для консистентности с данными из БД
            now = datetime.now(timezone.utc)
            analysis_start = now - timedelta(days=7)
            
            # Получаем все темы с их сообщениями за период анализа
            query = """
                SELECT 
                    t.id as topic_id,
                    t.name as topic_name,
                    t.description as topic_description,
                    t.color as topic_color,
                    m.id as message_id,
                    m.published_at
                FROM topics t
                JOIN message_topics mt ON t.id = mt.topic_id
                JOIN messages m ON mt.message_id = m.id
                WHERE m.published_at >= $1
                ORDER BY t.id, m.published_at
            """
            
            rows = await conn.fetch(query, analysis_start)
            
            # Группируем сообщения по темам
            topics_data = {}
            for row in rows:
                topic_id = row['topic_id']
                if topic_id not in topics_data:
                    topics_data[topic_id] = {
                        'topic_id': topic_id,
                        'topic_name': row['topic_name'],
                        'topic_description': row['topic_description'],
                        'topic_color': row['topic_color'],
                        'messages': []
                    }
                # Приводим datetime к timezone-aware, если он naive
                msg_time = row['published_at']
                if msg_time.tzinfo is None:
                    # Если naive, предполагаем UTC
                    msg_time = msg_time.replace(tzinfo=timezone.utc)
                topics_data[topic_id]['messages'].append(msg_time)
            
            # Получаем информацию о каналах для всех тем одним запросом
            current_window_start = now - timedelta(hours=window_hours)
            channel_query = """
                SELECT 
                    mt.topic_id,
                    COUNT(DISTINCT m.channel_id) as channel_count
                FROM message_topics mt
                JOIN messages m ON mt.message_id = m.id
                WHERE m.published_at >= $1
                GROUP BY mt.topic_id
            """
            channel_rows = await conn.fetch(channel_query, current_window_start)
            channel_counts = {row['topic_id']: row['channel_count'] for row in channel_rows}
            await conn.close()
            
            # Анализируем каждую тему на всплески
            results = []
            window_delta = timedelta(hours=window_hours)
            
            for topic_id, topic_info in topics_data.items():
                messages = sorted(topic_info['messages'])
                
                if len(messages) < 3:  # Минимум 3 сообщения для статистики
                    continue
                
                # Разбиваем временной ряд на окна и считаем количество сообщений в каждом
                window_counts = []
                current_time = analysis_start
                
                while current_time < now:
                    window_end = current_time + window_delta
                    count = sum(1 for msg_time in messages if current_time <= msg_time < window_end)
                    if count > 0:  # Учитываем только окна с сообщениями
                        window_counts.append(count)
                    current_time += timedelta(hours=1)  # Сдвигаем окно на 1 час
                
                if len(window_counts) < 3:  # Нужно минимум 3 окна для статистики
                    continue
                
                # Вычисляем статистику
                mean_count = statistics.mean(window_counts)
                if len(window_counts) > 1:
                    stdev_count = statistics.stdev(window_counts)
                else:
                    stdev_count = 0.0
                
                # Текущее окно (последние window_hours часов)
                current_count = sum(1 for msg_time in messages if msg_time >= current_window_start)
                
                # Вычисляем z-score для текущего окна
                if stdev_count > 0:
                    z_score = (current_count - mean_count) / stdev_count
                else:
                    z_score = 0.0
                
                # Определяем всплеск
                is_spike = z_score > z_threshold
                
                # Общая статистика по теме
                total_messages = len(messages)
                recent_messages = current_count
                channel_count = channel_counts.get(topic_id, 0)
                
                # Рассчитываем популярность (с бонусом за всплеск)
                popularity_score = (
                    total_messages * 0.4 +
                    recent_messages * 0.3 +
                    channel_count * 2 * 0.2 +
                    (z_score * 10 if is_spike else 0) * 0.1  # Бонус за всплеск
                )
                
                results.append({
                    'topic_id': topic_id,
                    'topic_name': topic_info['topic_name'],
                    'topic_description': topic_info['topic_description'],
                    'topic_color': topic_info['topic_color'],
                    'total_messages': total_messages,
                    'recent_messages': recent_messages,  # В последнем окне
                    'channel_count': channel_count,
                    'mean_count': round(mean_count, 2),
                    'stdev_count': round(stdev_count, 2),
                    'current_count': current_count,
                    'z_score': round(z_score, 2),
                    'is_spike': is_spike,
                    'spike_intensity': round(z_score, 2) if is_spike else 0.0,
                    'popularity_score': round(popularity_score, 1),
                    'window_hours': window_hours
                })
            
            # Сортируем: сначала всплесковые (по z-score), потом остальные (по popularity_score)
            results.sort(key=lambda x: (
                not x['is_spike'],  # Всплесковые первыми
                -x['z_score'] if x['is_spike'] else -x['popularity_score']  # По убыванию
            ))
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Ошибка получения трендовых тем со всплесками: {e}", exc_info=True)
            raise
    
    async def get_trending_topics(self, period: str = 'daily', limit: int = 10) -> List[Dict[str, Any]]:
        """Получить трендовые темы (deprecated, используйте get_trending_topics_with_spikes)"""
        # Используем новую логику со всплесками
        return await self.get_trending_topics_with_spikes(window_hours=6, z_threshold=2.0, limit=limit)
    
    async def get_topic_connections(self, topic_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить связи между темами на основе совместного упоминания в сообщениях"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Находим темы, которые часто упоминаются вместе с заданной темой
            query = """
                WITH topic_messages AS (
                    SELECT DISTINCT mt.message_id
                    FROM message_topics mt
                    WHERE mt.topic_id = $1
                ),
                related_topics AS (
                    SELECT 
                        mt2.topic_id,
                        t.name,
                        t.color,
                        COUNT(DISTINCT tm.message_id) as co_mention_count,
                        AVG(mt2.score) as avg_score
                    FROM topic_messages tm
                    JOIN message_topics mt2 ON tm.message_id = mt2.message_id
                    JOIN topics t ON mt2.topic_id = t.id
                    WHERE mt2.topic_id != $1
                    GROUP BY mt2.topic_id, t.name, t.color
                    HAVING COUNT(DISTINCT tm.message_id) >= 3
                )
                SELECT 
                    rt.topic_id,
                    rt.name,
                    rt.color,
                    rt.co_mention_count,
                    rt.avg_score,
                    CAST((rt.co_mention_count::float / (
                        SELECT COUNT(DISTINCT message_id) 
                        FROM message_topics 
                        WHERE topic_id = $1
                    ) * 100::float) AS NUMERIC(10,1)) as connection_strength
                FROM related_topics rt
                ORDER BY rt.co_mention_count DESC, rt.avg_score DESC
                LIMIT $2
            """
            
            rows = await conn.fetch(query, topic_id, limit)
            
            connections = []
            for row in rows:
                connections.append({
                    'topic_id': row['topic_id'],
                    'name': row['name'],
                    'color': row['color'],
                    'co_mention_count': row['co_mention_count'],
                    'avg_score': float(row['avg_score']),
                    'connection_strength': float(row['connection_strength'])
                })
            
            await conn.close()
            return connections
            
        except Exception as e:
            logger.error(f"Ошибка получения связей тем: {e}")
            raise
    
    async def get_trending_channels_by_event(self, cluster_id: str, period: str = 'daily', limit: int = 10) -> List[Dict[str, Any]]:
        """Получить трендовые каналы по конкретному событию (кластеру)"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Определяем временной диапазон
            if period == 'daily':
                date_from = datetime.now() - timedelta(days=1)
            elif period == 'weekly':
                date_from = datetime.now() - timedelta(weeks=1)
            elif period == 'monthly':
                date_from = datetime.now() - timedelta(days=30)
            else:
                date_from = datetime.now() - timedelta(days=1)
            
            query = """
                SELECT 
                    c.id,
                    c.name,
                    c.username,
                    c.description,
                    COUNT(DISTINCT m.id) as message_count,
                    COUNT(DISTINCT cm.message_id) as event_messages,
                    AVG(cm.similarity_score) as avg_similarity,
                    SUM(COALESCE(m.views_count, 0)) as total_views,
                    SUM(COALESCE(m.forwards_count, 0)) as total_forwards,
                    CAST((AVG(cm.similarity_score) * COUNT(DISTINCT cm.message_id))::float AS NUMERIC(10,1)) as event_activity_score
                FROM channels c
                JOIN messages m ON c.id = m.channel_id
                JOIN cluster_messages cm ON m.id = cm.message_id
                WHERE cm.cluster_id = $1
                AND m.published_at >= $2
                GROUP BY c.id, c.name, c.username, c.description
                HAVING COUNT(DISTINCT cm.message_id) >= 1
                ORDER BY event_activity_score DESC, total_views DESC
                LIMIT $3
            """
            
            rows = await conn.fetch(query, cluster_id, date_from, limit)
            
            channels = []
            for row in rows:
                channels.append({
                    'channel_id': row['id'],
                    'name': row['name'],
                    'username': row['username'],
                    'description': row['description'],
                    'message_count': row['message_count'],
                    'event_messages': row['event_messages'],
                    'avg_similarity': float(row['avg_similarity']),
                    'total_views': row['total_views'],
                    'total_forwards': row['total_forwards'],
                    'event_activity_score': float(row['event_activity_score'])
                })
            
            await conn.close()
            return channels
            
        except Exception as e:
            logger.error(f"Ошибка получения трендовых каналов по событию: {e}")
            raise
    
    async def get_trending_channels_by_topic(self, topic_id: int, period: str = 'daily', limit: int = 10) -> List[Dict[str, Any]]:
        """Получить трендовые каналы по конкретной теме (legacy метод)"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Определяем временной диапазон
            if period == 'daily':
                date_from = datetime.now() - timedelta(days=1)
            elif period == 'weekly':
                date_from = datetime.now() - timedelta(weeks=1)
            elif period == 'monthly':
                date_from = datetime.now() - timedelta(days=30)
            else:
                date_from = datetime.now() - timedelta(days=1)
            
            query = """
                SELECT 
                    c.id,
                    c.name,
                    c.username,
                    c.description,
                    COUNT(DISTINCT m.id) as message_count,
                    COUNT(DISTINCT mt.message_id) as topic_messages,
                    AVG(mt.score) as avg_topic_score,
                    SUM(COALESCE(m.views_count, 0)) as total_views,
                    SUM(COALESCE(m.forwards_count, 0)) as total_forwards,
                    CAST((AVG(mt.score) * COUNT(DISTINCT mt.message_id))::float AS NUMERIC(10,1)) as topic_activity_score
                FROM channels c
                JOIN messages m ON c.id = m.channel_id
                JOIN message_topics mt ON m.id = mt.message_id
                WHERE mt.topic_id = $1
                AND m.published_at >= $2
                GROUP BY c.id, c.name, c.username, c.description
                HAVING COUNT(DISTINCT mt.message_id) >= 1
                ORDER BY topic_activity_score DESC, total_views DESC
                LIMIT $3
            """
            
            rows = await conn.fetch(query, topic_id, date_from, limit)
            
            channels = []
            for row in rows:
                channels.append({
                    'channel_id': row['id'],
                    'name': row['name'],
                    'username': row['username'],
                    'description': row['description'],
                    'message_count': row['message_count'],
                    'topic_messages': row['topic_messages'],
                    'avg_topic_score': float(row['avg_topic_score']),
                    'total_views': row['total_views'],
                    'total_forwards': row['total_forwards'],
                    'topic_activity_score': float(row['topic_activity_score'])
                })
            
            await conn.close()
            return channels
            
        except Exception as e:
            logger.error(f"Ошибка получения трендовых каналов: {e}")
            raise
    
    async def get_trend_analytics(self, period: str = 'daily') -> Dict[str, Any]:
        """Получить общую аналитику трендов по событиям"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Определяем временной диапазон
            if period == 'daily':
                date_from = datetime.now() - timedelta(days=1)
            elif period == 'weekly':
                date_from = datetime.now() - timedelta(weeks=1)
            elif period == 'monthly':
                date_from = datetime.now() - timedelta(days=30)
            else:
                date_from = datetime.now() - timedelta(days=1)
            
            # Общая статистика по событиям (кластерам)
            analytics_query = """
                WITH event_stats AS (
                    SELECT 
                        dc.cluster_id,
                        dc.title,
                        COUNT(DISTINCT cm.message_id) as message_count,
                        AVG(cm.similarity_score) as avg_similarity,
                        COUNT(DISTINCT m.channel_id) as channel_count,
                        SUM(COALESCE(m.views_count, 0)) as total_views,
                        SUM(COALESCE(m.forwards_count, 0)) as total_forwards
                    FROM dedup_clusters dc
                    JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
                    JOIN messages m ON cm.message_id = m.id
                    WHERE m.published_at >= $1
                    GROUP BY dc.cluster_id, dc.title
                    HAVING COUNT(DISTINCT cm.message_id) >= 2
                )
                SELECT 
                    COUNT(*) as total_active_events,
                    SUM(message_count) as total_messages,
                    AVG(avg_similarity) as avg_similarity,
                    SUM(channel_count) as total_active_channels,
                    SUM(total_views) as total_views,
                    SUM(total_forwards) as total_forwards,
                    MAX(message_count) as max_messages,
                    MIN(message_count) as min_messages,
                    AVG(message_count) as avg_messages_per_event
                FROM event_stats
            """
            
            analytics_row = await conn.fetchrow(analytics_query, date_from)
            
            # Топ-5 самых активных событий
            top_events_query = """
                SELECT dc.title, COUNT(DISTINCT cm.message_id) as message_count
                FROM dedup_clusters dc
                JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
                JOIN messages m ON cm.message_id = m.id
                WHERE m.published_at >= $1
                GROUP BY dc.cluster_id, dc.title
                HAVING COUNT(DISTINCT cm.message_id) >= 2
                ORDER BY message_count DESC
                LIMIT 5
            """
            
            top_events_rows = await conn.fetch(top_events_query, date_from)
            
            # Топ-5 самых активных каналов
            top_channels_query = """
                SELECT c.name, COUNT(DISTINCT m.id) as message_count
                FROM channels c
                JOIN messages m ON c.id = m.channel_id
                WHERE m.published_at >= $1
                GROUP BY c.id, c.name
                ORDER BY message_count DESC
                LIMIT 5
            """
            
            top_channels_rows = await conn.fetch(top_channels_query, date_from)
            
            await conn.close()
            
            return {
                'period': period,
                'total_active_events': analytics_row['total_active_events'] or 0,
                'total_messages': analytics_row['total_messages'] or 0,
                'avg_similarity': float(analytics_row['avg_similarity'] or 0),
                'total_active_channels': analytics_row['total_active_channels'] or 0,
                'total_views': analytics_row['total_views'] or 0,
                'total_forwards': analytics_row['total_forwards'] or 0,
                'max_messages': analytics_row['max_messages'] or 0,
                'min_messages': analytics_row['min_messages'] or 0,
                'avg_messages_per_event': float(analytics_row['avg_messages_per_event'] or 0),
                'top_events': [{'name': row['title'] or 'Без названия', 'message_count': row['message_count']} for row in top_events_rows],
                'top_channels': [{'name': row['name'], 'message_count': row['message_count']} for row in top_channels_rows]
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения аналитики трендов: {e}")
            raise
    
    async def get_event_feed(self, user_id: str, limit: int = 20, offset: int = 0,
                           filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Получить персонализированную ленту событий"""
        try:
            # Получаем предпочтения пользователя
            preferences = await self._get_onboarding_service().get_user_preferences(user_id)
            
            # Применяем фильтры на основе предпочтений только если явно не указан topic_id
            if preferences and preferences['selected_topics'] and filters and 'topic_id' not in filters:
                # Если нет конкретного topic_id в фильтрах, используем предпочтения пользователя
                filters['topic_id'] = preferences['selected_topics'][0]
            elif not filters:
                filters = {}
            
            # Получаем события
            events = await self._get_deduplication_service().get_event_clusters(limit, offset, filters)
            
            return events
            
        except Exception as e:
            logger.error(f"Ошибка получения ленты событий: {e}")
            raise
    
    async def save_search_query(self, user_id: str, name: str, query: str, 
                              filters: Dict[str, Any], cadence: str = 'manual') -> bool:
        """Сохранить поисковый запрос"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            await conn.execute("""
                INSERT INTO saved_searches (user_id, name, query, filters, cadence)
                VALUES ($1, $2, $3, $4, $5)
            """, user_id, name, query, filters, cadence)
            
            await conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения поискового запроса: {e}")
            return False
    
    async def get_saved_searches(self, user_id: str) -> List[Dict[str, Any]]:
        """Получить сохранённые поисковые запросы"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            rows = await conn.fetch("""
                SELECT * FROM saved_searches 
                WHERE user_id = $1 AND is_active = TRUE
                ORDER BY created_at DESC
            """, user_id)
            
            searches = []
            for row in rows:
                searches.append({
                    'id': row['id'],
                    'name': row['name'],
                    'query': row['query'],
                    'filters': row['filters'],
                    'cadence': row['cadence'],
                    'last_run_at': row['last_run_at'],
                    'created_at': row['created_at']
                })
            
            await conn.close()
            return searches
            
        except Exception as e:
            logger.error(f"Ошибка получения сохранённых запросов: {e}")
            raise

    async def get_saved_search(self, search_id: int) -> Optional[Dict[str, Any]]:
        """Получить конкретный сохраненный поиск"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            row = await conn.fetchrow("""
                SELECT id, user_id, name, query, filters, cadence, created_at
                FROM saved_searches WHERE id = $1
            """, search_id)
            
            await conn.close()
            
            if row:
                return {
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'name': row['name'],
                    'query': row['query'],
                    'filters': json.loads(row['filters']) if row['filters'] else {},
                    'cadence': row['cadence'],
                    'created_at': row['created_at']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения сохраненного поиска: {e}")
            raise

    async def delete_saved_search(self, search_id: int) -> bool:
        """Удалить сохраненный поиск"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            result = await conn.execute("""
                DELETE FROM saved_searches WHERE id = $1
            """, search_id)
            
            await conn.close()
            
            return result == "DELETE 1"
            
        except Exception as e:
            logger.error(f"Ошибка удаления сохраненного поиска: {e}")
            raise
    
    async def _get_message_info(self, message_id: int) -> Optional[Dict[str, Any]]:
        """Получить полную информацию о сообщении"""
        try:
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Получаем сообщение с каналом
            message_row = await conn.fetchrow("""
                SELECT m.*, c.name as channel_name
                FROM messages m
                JOIN channels c ON m.channel_id = c.id
                WHERE m.id = $1
            """, message_id)
            
            if not message_row:
                await conn.close()
                return None
            
            # Получаем темы сообщения
            topic_rows = await conn.fetch("""
                SELECT t.name, mt.score
                FROM message_topics mt
                JOIN topics t ON mt.topic_id = t.id
                WHERE mt.message_id = $1
                ORDER BY mt.score DESC
            """, message_id)
            
            topics = [{'name': row['name'], 'score': float(row['score'])} for row in topic_rows]
            
            await conn.close()
            
            return {
                'text': message_row['text_content'],
                'channel_name': message_row['channel_name'],
                'published_at': message_row['published_at'],
                'views': message_row['views_count'],
                'forwards': message_row['forwards_count'],
                'topics': topics
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о сообщении: {e}")
            return None

    def _get_embedding_service(self):
        """Lazy-инициализация embedding_service"""
        if self._embedding_service is None:
            from pro_mode.embedding_service import embedding_service
            self._embedding_service = embedding_service
        return self._embedding_service

    def _get_deduplication_service(self):
        """Lazy-инициализация deduplication_service"""
        if self._deduplication_service is None:
            from pro_mode.deduplication_service import deduplication_service
            self._deduplication_service = deduplication_service
        return self._deduplication_service

    def _get_classification_service(self):
        """Lazy-инициализация classification_service"""
        if self._classification_service is None:
            from pro_mode.classification_service import classification_service
            self._classification_service = classification_service
        return self._classification_service

    def _get_onboarding_service(self):
        """Lazy-инициализация onboarding_service"""
        if self._onboarding_service is None:
            from pro_mode.classification_service import onboarding_service
            self._onboarding_service = onboarding_service
        return self._onboarding_service

# Глобальный экземпляр сервиса
pro_mode_service = ProModeService()
