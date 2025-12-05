"""
Flask API endpoints для Pro-режима
"""

from dataclasses import asdict
from flask import Blueprint, request, jsonify, render_template
import asyncio
import logging
import redis
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pro_mode import pro_mode_service
from pro_mode.classification_service import onboarding_service, classification_service
from pro_mode.deduplication_service import deduplication_service
from pro_mode.embedding_service import embedding_service
from pro_mode.export_service import export_service
from pro_mode.topic_modeling_settings import (
    load_topic_modeling_settings,
    save_topic_modeling_settings,
    get_setting_specs,
    get_setting_groups,
)
from pro_mode.topic_modeling_service import TopicModelingService
from pro_mode.topic_modeling_progress import (
    get_current_progress,
    request_cancel,
)
from config_utils import get_config
import asyncpg
import redis

# Создаем logger ПЕРЕД импортом задач Huey
logger = logging.getLogger(__name__)

# Импорт задач Huey для topic modeling
try:
    from pro_mode.tasks_pro import run_topic_modeling_pipeline
    TOPIC_MODELING_AVAILABLE = True
except ImportError:
    TOPIC_MODELING_AVAILABLE = False
    logger.warning("Topic modeling tasks не доступны (Huey не настроен?)")

# Создаем Blueprint для Pro-режима
pro_bp = Blueprint('pro', __name__, url_prefix='/pro')

@pro_bp.route('/')
def pro_dashboard():
    """Главная страница Pro-режима (требует аутентификации)"""
    from flask import session, redirect
    # Проверяем аутентификацию через session (для страниц) или JWT токен (для API)
    if not session.get('authenticated'):
        # Пробуем проверить через JWT токен в заголовках
        from auth.dependencies import get_current_user_sync
        user = get_current_user_sync()
        if not user:
            return redirect('/login')
        # Если токен валиден, сохраняем в session
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['authenticated'] = True
    return render_template('pro/dashboard.html')


@pro_bp.route('/users')
def users_management():
    """Страница управления пользователями (только для администраторов)"""
    from flask import session, redirect
    from auth.dependencies import get_current_user_sync
    
    # Сначала проверяем session (для обычных переходов по ссылкам)
    if session.get('authenticated'):
        user_id = session.get('user_id')
        if user_id:
            # Получаем пользователя из БД для проверки актуальности
            import asyncio
            from auth.user_service import user_service
            user = asyncio.run(user_service.get_user_by_id(user_id))
            if user and user.get("is_active"):
                # Проверяем роль администратора
                if user.get("role") != "admin":
                    return redirect('/pro/')
                return render_template('pro/users.html')
    
    # Если нет session, проверяем JWT токен (для API запросов)
    user = get_current_user_sync()
    if not user:
        return redirect('/login')
    
    # Если токен валиден, сохраняем в session
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['authenticated'] = True
    
    # Проверяем роль администратора
    if user.get("role") != "admin":
        return redirect('/pro/')
    
    return render_template('pro/users.html')

@pro_bp.route('/onboarding')
def onboarding():
    """Страница онбординга"""
    return render_template('pro/onboarding.html')

@pro_bp.route('/feed')
def feed():
    """Лента событий"""
    return render_template('pro/feed.html')

@pro_bp.route('/search')
def search():
    """Семантический поиск"""
    return render_template('pro/search.html')

@pro_bp.route('/trends')
def trends():
    """Тренды и аналитика"""
    return render_template('pro/trends.html')

# API endpoints

@pro_bp.route('/api/topics', methods=['GET'])
def get_topics():
    """Получить список всех тем из БД"""
    try:
        import asyncpg
        from config_utils import get_config
        async def _fetch_topics():
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            rows = await conn.fetch("""
                SELECT id, name, color, description FROM topics ORDER BY name
            """)
            await conn.close()
            return [
                {
                    'id': r['id'],
                    'name': r['name'],
                    'color': r['color'],
                    'description': r['description']
                } for r in rows
            ]
        topics = asyncio.run(_fetch_topics())
        return jsonify({'topics': topics})
    except Exception as e:
        logger.error(f"Ошибка получения тем: {e}")
        return jsonify({'error': 'Ошибка получения тем'}), 500

@pro_bp.route('/api/topics/list', methods=['GET'])
def get_topics_list():
    """Получить список всех тем из БД (для модального окна классификации)"""
    try:
        import asyncpg
        from config_utils import get_config
        async def _fetch_topics():
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            rows = await conn.fetch("""
                SELECT id, name, color, description FROM topics ORDER BY name
            """)
            await conn.close()
            return [
                {
                    'id': r['id'],
                    'name': r['name'],
                    'color': r['color'],
                    'description': r['description']
                } for r in rows
            ]
        topics = asyncio.run(_fetch_topics())
        return jsonify({'status': 'ok', 'topics': topics})
    except Exception as e:
        logger.error(f"Ошибка получения тем: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@pro_bp.route('/api/channels', methods=['GET'])
def get_channels():
    """Получить список всех каналов из БД"""
    try:
        import asyncpg
        from config_utils import get_config
        async def _fetch_channels():
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            rows = await conn.fetch("""
                SELECT id, name, username, description FROM channels ORDER BY name
            """)
            await conn.close()
            return [
                {
                    'id': r['id'],
                    'name': r['name'],
                    'title': r['name'],
                    'username': r['username'],
                    'description': r['description'],
                    'members_count': None,  # Колонка не существует
                    'type': None,  # Колонка не существует
                    'is_verified': None  # Колонка не существует
                } for r in rows
            ]
        channels = asyncio.run(_fetch_channels())
        return jsonify({'channels': channels})
    except Exception as e:
        logger.error(f"Ошибка получения каналов: {e}")
        return jsonify({'error': 'Ошибка получения каналов'}), 500

@pro_bp.route('/api/channels/list', methods=['GET'])
def get_channels_list():
    """Получить список всех каналов из БД (для модального окна классификации)"""
    try:
        import asyncpg
        from config_utils import get_config
        async def _fetch_channels():
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            rows = await conn.fetch("""
                SELECT id, name, username, description FROM channels ORDER BY name
            """)
            await conn.close()
            return [
                {
                    'id': r['id'],
                    'name': r['name'],
                    'username': r['username'],
                    'description': r['description']
                } for r in rows
            ]
        channels = asyncio.run(_fetch_channels())
        return jsonify({'status': 'ok', 'channels': channels})
    except Exception as e:
        logger.error(f"Ошибка получения каналов: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@pro_bp.route('/api/onboarding/preferences', methods=['POST'])
def save_user_preferences():
    """Сохранить предпочтения пользователя"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'default_user')
        selected_topics = data.get('selected_topics', [])
        seed_channels = data.get('seed_channels', [])
        
        success = asyncio.run(onboarding_service.save_user_preferences(user_id, selected_topics, seed_channels))
        
        if success:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': 'Ошибка сохранения предпочтений'}), 500
            
    except Exception as e:
        logger.error(f"Ошибка сохранения предпочтений: {e}")
        return jsonify({'error': 'Ошибка сохранения предпочтений'}), 500

@pro_bp.route('/api/onboarding/recommendations', methods=['GET'])
def get_channel_recommendations():
    """Получить рекомендации каналов"""
    try:
        user_id = request.args.get('user_id', 'default_user')
        limit = int(request.args.get('limit', 20))
        
        recommendations = asyncio.run(onboarding_service.get_recommended_channels(user_id, limit))
        
        return jsonify({'recommendations': recommendations})
        
    except Exception as e:
        logger.error(f"Ошибка получения рекомендаций: {e}")
        return jsonify({'error': 'Ошибка получения рекомендаций'}), 500


# API endpoints старого функционала классификации удалены - используется только тематическое моделирование

@pro_bp.route('/api/feed', methods=['GET'])
def get_event_feed():
    """Получить ленту событий"""
    try:
        user_id = request.args.get('user_id', 'default_user')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        # Фильтры
        filters = {}
        if request.args.get('date_from'):
            filters['date_from'] = request.args.get('date_from')
        if request.args.get('date_to'):
            filters['date_to'] = request.args.get('date_to')
        if request.args.get('topic_id'):
            filters['topic_id'] = int(request.args.get('topic_id'))
        if request.args.get('cluster_id'):
            filters['cluster_id'] = request.args.get('cluster_id')
        
        events = asyncio.run(pro_mode_service.get_event_feed(user_id, limit, offset, filters))
        # Если нет primary_topic_id у кластеров, попробуем бэкфилл и повторим один раз
        if not events:
            try:
                from pro_mode.deduplication_service import deduplication_service
                asyncio.run(deduplication_service.backfill_primary_topics())
                events = asyncio.run(pro_mode_service.get_event_feed(user_id, limit, offset, filters))
            except Exception:
                pass
        
        return jsonify({'events': events})
        
    except Exception as e:
        logger.error(f"Ошибка получения ленты: {e}")
        return jsonify({'error': 'Ошибка получения ленты'}), 500

@pro_bp.route('/api/messages/by-topic', methods=['GET'])
def get_messages_by_topic():
    """Получить сообщения по теме"""
    try:
        topic_id = request.args.get('topic_id')
        if not topic_id:
            return jsonify({'error': 'topic_id required'}), 400
        
        topic_id = int(topic_id)
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        result = asyncio.run(get_classified_messages(topic_id, limit, offset))
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Ошибка получения сообщений по теме: {e}")
        return jsonify({'error': 'Ошибка получения сообщений'}), 500

async def get_classified_messages(topic_id: int, limit: int, offset: int):
    """Получить классифицированные сообщения по теме"""
    try:
        config = get_config()
        conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
        
        # Получаем сообщения с выбранной темой
        rows = await conn.fetch("""
            SELECT m.id, m.text_content, m.published_at, 
                   c.name as channel_name, c.id as channel_id,
                   mt.score
            FROM message_topics mt
            JOIN messages m ON mt.message_id = m.id
            JOIN channels c ON m.channel_id = c.id
            WHERE mt.topic_id = $1
            ORDER BY m.published_at DESC
            LIMIT $2 OFFSET $3
        """, topic_id, limit, offset)
        
        await conn.close()
        
        messages = []
        for row in rows:
            messages.append({
                'message_id': row['id'],
                'text': row['text_content'][:500] if row['text_content'] else '',
                'channel_name': row['channel_name'],
                'channel_id': row['channel_id'],
                'published_at': row['published_at'].isoformat() if row['published_at'] else None,
                'score': float(row['score']) if row['score'] else 0.0
            })
        
        return {'messages': messages, 'total': len(messages)}
        
    except Exception as e:
        logger.error(f"Ошибка получения сообщений по теме: {e}")
        raise

@pro_bp.route('/api/search/semantic', methods=['POST'])
def semantic_search():
    """Семантический поиск"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        limit = data.get('limit', 20)
        
        # Фильтры
        filters = {}
        if 'date_from' in data:
            filters['date_from'] = data['date_from']
        if 'date_to' in data:
            filters['date_to'] = data['date_to']
        if 'channel_id' in data:
            filters['channel_id'] = data['channel_id']
        if 'topic_id' in data:
            filters['topic_id'] = data['topic_id']
        
        # Инициализируем сервис если нужно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(pro_mode_service.search_semantic(query, filters, limit))
        finally:
            loop.close()
        
        return jsonify({'results': results})
        
    except Exception as e:
        logger.error(f"Ошибка семантического поиска: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Ошибка поиска'}), 500

@pro_bp.route('/api/search/save', methods=['POST'])
def save_search():
    """Сохранить поисковый запрос"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'default_user')
        name = data.get('name', '')
        query = data.get('query', '')
        filters = data.get('filters', {})
        cadence = data.get('cadence', 'manual')
        
        success = asyncio.run(pro_mode_service.save_search_query(user_id, name, query, filters, cadence))
        
        if success:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': 'Ошибка сохранения запроса'}), 500
            
    except Exception as e:
        logger.error(f"Ошибка сохранения поискового запроса: {e}")
        return jsonify({'error': 'Ошибка сохранения запроса'}), 500


@pro_bp.route('/api/search/saved', methods=['GET'])
def get_saved_searches():
    """Получить сохраненные поиски пользователя"""
    try:
        user_id = request.args.get('user_id', 'default_user')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            searches = loop.run_until_complete(pro_mode_service.get_saved_searches(user_id))
            return jsonify({'searches': searches})
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка получения сохраненных поисков: {e}")
        return jsonify({'error': 'Ошибка получения сохраненных поисков'}), 500


@pro_bp.route('/api/search/saved/<int:search_id>', methods=['GET'])
def get_saved_search(search_id: int):
    """Получить конкретный сохраненный поиск"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            search = loop.run_until_complete(pro_mode_service.get_saved_search(search_id))
            if search:
                return jsonify({'search': search})
            else:
                return jsonify({'error': 'Поиск не найден'}), 404
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка получения сохраненного поиска: {e}")
        return jsonify({'error': 'Ошибка получения сохраненного поиска'}), 500


@pro_bp.route('/api/search/saved/<int:search_id>', methods=['DELETE'])
def delete_saved_search(search_id: int):
    """Удалить сохраненный поиск"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            success = loop.run_until_complete(pro_mode_service.delete_saved_search(search_id))
            if success:
                return jsonify({'status': 'ok'})
            else:
                return jsonify({'error': 'Поиск не найден'}), 404
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка удаления сохраненного поиска: {e}")
        return jsonify({'error': 'Ошибка удаления сохраненного поиска'}), 500

@pro_bp.route('/trends')
def trends_page():
    """Страница анализа трендов"""
    return render_template('pro/trends.html')

@pro_bp.route('/api/trends', methods=['GET'])
def get_trends():
    """Получить трендовые события с обнаружением всплесков интереса"""
    try:
        # Параметры для обнаружения всплесков
        window_hours = int(request.args.get('window_hours', 6))
        z_threshold = float(request.args.get('z_threshold', 2.0))
        limit = int(request.args.get('limit', 20))
        
        # Используем логику со всплесками для событий (кластеров)
        trends = asyncio.run(pro_mode_service.get_trending_events_with_spikes(
            window_hours=window_hours,
            z_threshold=z_threshold,
            limit=limit
        ))
        
        # Форматируем для UI
        formatted_trends = []
        for trend in trends:
            # Определяем направление тренда на основе z-score
            if trend['is_spike']:
                trend_direction = 'spike'
                trend_icon = '🔥'
            elif trend['z_score'] > 1.0:
                trend_direction = 'up'
                trend_icon = '📈'
            elif trend['z_score'] < -1.0:
                trend_direction = 'down'
                trend_icon = '📉'
            else:
                trend_direction = 'stable'
                trend_icon = '➡️'
            
            # Вычисляем процент роста относительно среднего значения
            # Показываем, насколько текущее окно (6 часов) выше среднего за период
            growth_percentage = 0.0
            if 'mean_count' in trend and trend['mean_count'] > 0:
                # Процент роста = (текущее - среднее) / среднее * 100
                growth_percentage = round(((trend['current_count'] - trend['mean_count']) / trend['mean_count']) * 100, 1)
            elif trend['recent_messages'] > 0:
                # Если нет среднего значения, но есть сообщения в текущем окне
                growth_percentage = 100.0
            
            formatted_trends.append({
                'cluster_id': trend['cluster_id'],
                'event_id': trend['event_id'],
                'title': trend['title'],
                'summary': trend['summary'],
                'topic_id': trend['topic_id'],
                'topic_name': trend['topic_name'],
                'topic_color': trend['topic_color'],
                'message_count': trend['total_messages'],
                'recent_messages': trend['recent_messages'],
                'channel_count': trend['channel_count'],
                'total_views': trend['total_views'],
                'total_forwards': trend['total_forwards'],
                'avg_similarity': trend.get('avg_similarity', 0.0),
                'growth_percentage': growth_percentage,
                'trend_direction': trend_direction,
                'trend_icon': trend_icon,
                'is_spike': trend['is_spike'],
                'z_score': trend['z_score'],
                'spike_intensity': trend['spike_intensity'],
                'popularity_score': trend['popularity_score'],
                'mean_count': trend['mean_count'],
                'current_count': trend['current_count'],
                'window_hours': trend['window_hours'],
                'first_mention_at': trend['first_mention_at'],
                'last_mention_at': trend['last_mention_at']
            })
        
        return jsonify({'trends': formatted_trends})
        
    except Exception as e:
        logger.error(f"Ошибка получения трендов: {e}", exc_info=True)
        return jsonify({'error': 'Ошибка получения трендов'}), 500

@pro_bp.route('/api/trends/connections/<int:topic_id>', methods=['GET'])
def get_topic_connections(topic_id):
    """Получить связи между темами"""
    try:
        limit = int(request.args.get('limit', 10))
        
        connections = asyncio.run(pro_mode_service.get_topic_connections(topic_id, limit))
        
        return jsonify({'connections': connections})
        
    except Exception as e:
        logger.error(f"Ошибка получения связей тем: {e}")
        return jsonify({'error': 'Ошибка получения связей тем'}), 500

@pro_bp.route('/api/trends/channels/<cluster_id>', methods=['GET'])
def get_trending_channels_by_event(cluster_id):
    """Получить трендовые каналы по событию"""
    try:
        period = request.args.get('period', 'daily')
        limit = int(request.args.get('limit', 10))
        
        channels = asyncio.run(pro_mode_service.get_trending_channels_by_event(cluster_id, period, limit))
        
        return jsonify({'channels': channels})
        
    except Exception as e:
        logger.error(f"Ошибка получения трендовых каналов: {e}")
        return jsonify({'error': 'Ошибка получения трендовых каналов'}), 500

@pro_bp.route('/api/trends/channels/topic/<int:topic_id>', methods=['GET'])
def get_trending_channels_by_topic(topic_id):
    """Получить трендовые каналы по теме (legacy endpoint)"""
    try:
        period = request.args.get('period', 'daily')
        limit = int(request.args.get('limit', 10))
        
        channels = asyncio.run(pro_mode_service.get_trending_channels_by_topic(topic_id, period, limit))
        
        return jsonify({'channels': channels})
        
    except Exception as e:
        logger.error(f"Ошибка получения трендовых каналов: {e}")
        return jsonify({'error': 'Ошибка получения трендовых каналов'}), 500

@pro_bp.route('/api/trends/analytics', methods=['GET'])
def get_trend_analytics():
    """Получить общую аналитику трендов"""
    try:
        period = request.args.get('period', 'daily')
        
        analytics = asyncio.run(pro_mode_service.get_trend_analytics(period))
        
        return jsonify({'analytics': analytics})
        
    except Exception as e:
        logger.error(f"Ошибка получения аналитики трендов: {e}")
        return jsonify({'error': 'Ошибка получения аналитики трендов'}), 500

# API endpoints старого функционала классификации удалены - используется только тематическое моделирование

@pro_bp.route('/api/dedup/reprocess', methods=['POST'])
def reprocess_deduplication():
    """Переобработать дедупликацию с улучшенными параметрами"""
    try:
        data = request.get_json() or {}
        threshold = data.get('threshold', 0.75)
        limit = data.get('limit', 1000)
        
        # Запускаем переобработку через Huey
        from pro_mode.tasks_pro import reprocess_deduplication_task
        task = reprocess_deduplication_task(threshold, limit)
        
        return jsonify({
            "status": "ok",
            "result": {
                "task_id": str(task.id),
                "threshold": threshold,
                "limit": limit,
                "message": "Переобработка дедупликации запущена"
            }
        })
        
    except Exception as e:
        logger.error(f"Ошибка запуска переобработки дедупликации: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@pro_bp.route('/api/dedup/cleanup', methods=['POST'])
def cleanup_single_clusters():
    """Очистить одиночные кластеры"""
    try:
        from pro_mode.deduplication_service import deduplication_service
        
        deleted_count = asyncio.run(deduplication_service.cleanup_single_clusters())
        
        return jsonify({
            "status": "ok",
            "result": {
                "deleted_count": deleted_count,
                "message": f"Удалено {deleted_count} одиночных кластеров"
            }
        })
        
    except Exception as e:
        logger.error(f"Ошибка очистки одиночных кластеров: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@pro_bp.route('/api/dedup/stats', methods=['GET'])
def get_deduplication_stats():
    """Получить статистику дедупликации"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        config = get_config()
        conn = psycopg2.connect(dsn=config['postgresql']['dsn'])
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Общая статистика
            cursor.execute("SELECT COUNT(*) as total_embeddings FROM embeddings")
            total_embeddings = cursor.fetchone()['total_embeddings']
            
            cursor.execute("SELECT COUNT(*) as total_clusters FROM dedup_clusters")
            total_clusters = cursor.fetchone()['total_clusters']
            
            cursor.execute("SELECT COUNT(*) as total_links FROM cluster_messages")
            total_links = cursor.fetchone()['total_links']
            
            # Статистика по размерам кластеров (только активные кластеры с сообщениями)
            cursor.execute("""
                SELECT 
                    COUNT(cm.message_id) as cluster_size,
                    COUNT(DISTINCT dc.cluster_id) as cluster_count
                FROM dedup_clusters dc
                INNER JOIN cluster_messages cm ON dc.cluster_id = cm.cluster_id
                GROUP BY dc.cluster_id
                HAVING COUNT(cm.message_id) > 0
                ORDER BY cluster_size
            """)
            cluster_sizes = cursor.fetchall()
            
            # Подсчитываем статистику
            size_stats = {}
            for row in cluster_sizes:
                size = row['cluster_size']
                cluster_count = 1  # Каждый row - это один кластер
                if size not in size_stats:
                    size_stats[size] = 0
                size_stats[size] += cluster_count
            
            # Средний размер кластера
            avg_cluster_size = total_links / total_clusters if total_clusters > 0 else 0
            
            # Коэффициент дедупликации
            dedup_ratio = total_links / total_clusters if total_clusters > 0 else 0
            
        conn.close()
        
        return jsonify({
            "status": "ok",
            "stats": {
                "total_embeddings": total_embeddings,
                "total_clusters": total_clusters,
                "total_links": total_links,
                "avg_cluster_size": round(avg_cluster_size, 2),
                "dedup_ratio": round(dedup_ratio, 2),
                "cluster_size_distribution": size_stats
            }
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики дедупликации: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@pro_bp.route('/api/events/<cluster_id>', methods=['GET'])
def get_event_details(cluster_id):
    """Получить детали события"""
    try:
        from pro_mode.deduplication_service import deduplication_service
        
        details = asyncio.run(deduplication_service.get_cluster_details(cluster_id))
        
        if details:
            return jsonify({'event': details})
        else:
            return jsonify({'error': 'Событие не найдено'}), 404
            
    except Exception as e:
        logger.error(f"Ошибка получения деталей события: {e}")
        return jsonify({'error': 'Ошибка получения деталей события'}), 500

# API endpoints старого функционала кластеризации удалены - используется только тематическое моделирование

@pro_bp.route('/api/dedup/split_large', methods=['POST'])
def split_large_clusters():
    """Автосплит крупных кластеров"""
    try:
        from pro_mode.deduplication_service import deduplication_service

        payload = request.get_json(silent=True) or {}
        max_size = int(payload.get('max_size', 20))
        inner_threshold = float(payload.get('inner_threshold', 0.9))
        time_bucket_days = int(payload.get('time_bucket_days', 1))

        result = asyncio.run(deduplication_service.split_large_clusters(
            max_size=max_size,
            inner_threshold=inner_threshold,
            time_bucket_days=time_bucket_days
        ))

        return jsonify(result)
    except Exception as e:
        logger.error(f"Ошибка автосплита крупных кластеров: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# API endpoints старого функционала кластеризации удалены - используется только тематическое моделирование

# API endpoints старого функционала индексации удалены - используется только тематическое моделирование

@pro_bp.route('/api/dedup/run', methods=['POST'])
def run_dedup():
    """Запустить пакетную дедупликацию с параметрами threshold и limit"""
    try:
        # Сначала инициализируем embedding_service если он еще не инициализирован
        try:
            asyncio.run(embedding_service.initialize())
        except Exception as e:
            logger.warning(f"Embedding service уже инициализирован: {e}")
        
        data = request.get_json(silent=True) or {}
        threshold = float(data.get('threshold', 0.8))
        limit = int(data.get('limit', 1000))
        
        logger.info(f"Запуск дедупликации: threshold={threshold}, limit={limit}")
        
        # Выполняем синхронно через asyncio.run
        result = asyncio.run(deduplication_service.run_batch_dedup(limit=limit, threshold=threshold))
        return jsonify({'status': 'ok', 'result': result})
    except Exception as e:
        logger.error(f"Ошибка запуска дедупликации: {e}", exc_info=True)
        return jsonify({'error': f'Ошибка запуска дедупликации: {str(e)}'}), 500

@pro_bp.route('/api/stats', methods=['GET'])
def get_pro_stats():
    """Получить статистику Pro-режима"""
    try:
        stats = asyncio.run(_get_pro_stats_async())
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Ошибка получения статистики Pro-режима: {e}")
        return jsonify({"error": "Ошибка получения статистики"}), 500

async def _get_pro_stats_async():
    """Асинхронное получение статистики"""
    try:
        from pro_mode.embedding_service import embedding_service
        import asyncpg
        from config_utils import get_config
        
        config = get_config()
        
        # Пробуем подключиться к PostgreSQL с таймаутом
        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(dsn=config['postgresql']['dsn'], timeout=5),
                timeout=10.0
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"Ошибка подключения к PostgreSQL: {e}")
            # Возвращаем статистику без данных из PostgreSQL
            return {
                "indexed_messages": 0,
                "total_messages": 0,
                "indexing_progress": 0,
                "qdrant_status": "❌ Ошибка подключения к PostgreSQL",
                "collections_count": 0,
                "collection_info": {"points_count": 0, "vectors_count": 0},
                "events_count": 0,
                "topics_count": 0,
                "channels_count": 0,
                "classified_messages": 0,
                "postgresql_status": "❌ Недоступен"
            }
        
        try:
            # Общее количество сообщений
            total_messages = await conn.fetchval("SELECT COUNT(*) FROM messages")
            
            # Статус Qdrant
            qdrant_status = "✅ Доступен"
            try:
                collections = await embedding_service.qdrant.get_collections()
                collection_count = len(collections.collections)
            except Exception:
                qdrant_status = "❌ Недоступен"
                collection_count = 0
            
            # Информация о коллекции posts_search (FRIDA)
            collection_info = {"points_count": 0, "vectors_count": 0}
            indexed_count = 0  # Используем реальное количество векторов из Qdrant
            if qdrant_status == "✅ Доступен":
                try:
                    collection_info = await embedding_service.qdrant.get_collection_info("posts_search")
                except Exception:
                    pass
                try:
                    # Точное количество точек (векторов) в коллекции posts_search
                    vectors_count = await embedding_service.qdrant.count_points("posts_search", exact=True)
                    indexed_count = vectors_count  # Используем точное количество из Qdrant
                    collection_info["vectors_count"] = vectors_count
                    collection_info["points_count"] = vectors_count
                except Exception:
                    pass
            
            # Дополнительная статистика для общей статистики
            events_count = await conn.fetchval("SELECT COUNT(*) FROM dedup_clusters")
            topics_count = await conn.fetchval("SELECT COUNT(*) FROM topics")
            channels_count = await conn.fetchval("SELECT COUNT(*) FROM channels")
            classified_messages = await conn.fetchval("SELECT COUNT(DISTINCT message_id) FROM message_topics")
            
            await conn.close()
            
            return {
                "indexed_messages": indexed_count or 0,
                "total_messages": total_messages or 0,
                "indexing_progress": round((indexed_count or 0) / max(total_messages or 1, 1) * 100, 1),
                "qdrant_status": qdrant_status,
                "collections_count": collection_count,
                "collection_info": {
                    "points_count": collection_info.get("points_count", 0),
                    "vectors_count": collection_info.get("vectors_count", 0)
                },
                # Дополнительные поля для общей статистики
                "events_count": events_count or 0,
                "topics_count": topics_count or 0,
                "channels_count": channels_count or 0,
                "classified_messages": classified_messages or 0,
                "postgresql_status": "✅ Доступен"
            }
        finally:
            if not conn.is_closed():
                await conn.close()
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}", exc_info=True)
        return {
            "indexed_messages": 0,
            "total_messages": 0,
            "indexing_progress": 0,
            "qdrant_status": "❌ Ошибка",
            "collections_count": 0,
            "collection_info": {"points_count": 0, "vectors_count": 0},
            "events_count": 0,
            "topics_count": 0,
            "channels_count": 0,
            "classified_messages": 0,
            "postgresql_status": "❌ Ошибка"
        }

# API endpoints старого функционала индексации удалены - используется только тематическое моделирование


@pro_bp.route('/api/reset', methods=['POST'])
def reset_all_data():
    """Сброс всех данных: PostgreSQL, Qdrant, Redis"""
    try:
        # Получаем подтверждение от пользователя
        data = request.get_json()
        confirm = data.get('confirm', False)
        
        if not confirm:
            return jsonify({
                "status": "error",
                "error": "Требуется подтверждение для сброса данных"
            }), 400
        
        # Запускаем сброс асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_reset_all_data_async())
            return jsonify({
                "status": "ok",
                "result": result
            })
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка сброса данных: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@pro_bp.route('/api/task-status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """Получить статус задачи (универсальный endpoint для любых задач)"""
    try:
        # Используем fallback на Redis напрямую
        config = get_config()
        redis_client = redis.Redis(
            host=config['redis']['host'],
            port=int(config['redis']['port']),
            decode_responses=True
        )
        
        # Проверяем результат напрямую в Redis
        result_key = f"huey:telegram-parser:result:{task_id}"
        result_data = redis_client.get(result_key)
        
        if result_data:
            # Результат найден - задача завершена
            import json
            try:
                result = json.loads(result_data)
                return jsonify({
                    "status": "completed",
                    "result": result
                })
            except Exception as e:
                logger.warning(f"Ошибка парсинга результата задачи {task_id}: {e}")
                return jsonify({
                    "status": "completed",
                    "result": {}
                })
        
        # Результата нет - проверяем, есть ли задача в очереди
        task_key = f"huey:telegram-parser:task:{task_id}"
        task_exists = redis_client.exists(task_key)
        
        if task_exists:
            return jsonify({
                "status": "pending",
                "message": "Задача в процессе выполнения"
            })
        
        # Проверяем scheduled и готовящиеся к выполнению задачи
        scheduled_key = f"huey:telegram-parser:scheduled:{task_id}"
        if redis_client.exists(scheduled_key):
            return jsonify({
                "status": "pending",
                "message": "Задача в очереди на выполнение"
            })
        
        # Проверяем выполняющиеся задачи
        executing_key = f"huey:telegram-parser:executing:{task_id}"
        if redis_client.exists(executing_key):
            return jsonify({
                "status": "pending",
                "message": "Задача в процессе выполнения"
            })
        
        # Если результата нет и задачи нет нигде - скорее всего задача еще не началась или выполняется
        # Возвращаем pending чтобы не создавать ложных успехов
        return jsonify({
            "status": "pending",
            "message": "Задача в процессе выполнения"
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса задачи: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


async def _reset_all_data_async():
    """Асинхронная функция сброса всех данных"""
    config = get_config()
    results = {}
    
    try:
        # 1. Очистка PostgreSQL
        logger.info("🧹 Очистка PostgreSQL...")
        conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
        
        # Удаляем данные в правильном порядке (с учетом foreign key constraints)
        tables_to_clear = [
            'cluster_messages',
            'dedup_clusters', 
            'message_topics',
            'embeddings',
            'topics',
            'messages',
            'channels'
        ]
        
        for table in tables_to_clear:
            try:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                await conn.execute(f"DELETE FROM {table}")
                results[f'postgresql_{table}'] = count
                logger.info(f"✅ Очищена таблица {table}: {count} записей")
            except Exception as e:
                logger.error(f"❌ Ошибка очистки таблицы {table}: {e}")
                results[f'postgresql_{table}_error'] = str(e)
        
        await conn.close()
        
        # 2. Очистка Qdrant
        logger.info("🧹 Очистка Qdrant...")
        deleted_collections = []
        qdrant_errors: Dict[str, str] = {}
        try:
            collections_response = embedding_service.qdrant.client.get_collections()
            for collection in collections_response.collections:
                name = getattr(collection, "name", None)
                if not name:
                    continue
                try:
                    await embedding_service.qdrant.delete_collection(name)
                    deleted_collections.append(name)
                except Exception as col_exc:
                    error_message = str(col_exc)
                    qdrant_errors[name] = error_message
                    logger.error(f"❌ Ошибка удаления коллекции {name}: {error_message}")

            results['qdrant_deleted_collections'] = deleted_collections
            if qdrant_errors:
                results['qdrant_errors'] = qdrant_errors
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка коллекций Qdrant: {e}")
            results['qdrant_error'] = str(e)
        
        # 3. Очистка Redis
        logger.info("🧹 Очистка Redis...")
        try:
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.flushdb()
            results['redis_cleared'] = True
            logger.info("✅ Redis очищен")
        except Exception as e:
            logger.error(f"❌ Ошибка очистки Redis: {e}")
            results['redis_error'] = str(e)
        
        logger.info("🎉 Сброс данных завершен")
        return results
        
    except Exception as e:
        logger.error(f"❌ Общая ошибка сброса данных: {e}")
        raise


@pro_bp.route('/api/topics/add', methods=['POST'])
def add_topic():
    """Добавить новую тему"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({
                "status": "error",
                "error": "Название темы не может быть пустым"
            }), 400
        
        # Запускаем добавление темы асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_add_topic_async(name, description))
            return jsonify({
                "status": "ok",
                "result": result
            })
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка добавления темы: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


async def _add_topic_async(name: str, description: str = ""):
    """Асинхронная функция добавления темы"""
    config = get_config()
    conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
    
    try:
        # Проверяем, не существует ли уже такая тема
        existing = await conn.fetchval(
            "SELECT id FROM topics WHERE name = $1",
            name
        )
        
        if existing:
            return {"error": "Тема с таким названием уже существует"}
        
        # Добавляем новую тему
        topic_id = await conn.fetchval(
            "INSERT INTO topics (name, description, created_at) VALUES ($1, $2, NOW()) RETURNING id",
            name, description
        )
        
        return {
            "topic_id": topic_id,
            "name": name,
            "description": description
        }
        
    finally:
        await conn.close()


@pro_bp.route('/api/topics/<int:topic_id>', methods=['DELETE'])
def delete_topic(topic_id: int):
    """Удалить тему"""
    try:
        # Запускаем удаление темы асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_delete_topic_async(topic_id))
            return jsonify({
                "status": "ok",
                "result": result
            })
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка удаления темы: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


async def _delete_topic_async(topic_id: int):
    """Асинхронная функция удаления темы"""
    config = get_config()
    conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
    
    try:
        # Проверяем, существует ли тема
        topic = await conn.fetchrow(
            "SELECT id, name FROM topics WHERE id = $1",
            topic_id
        )
        
        if not topic:
            return {"error": "Тема не найдена"}
        
        # Удаляем связи с сообщениями
        await conn.execute("DELETE FROM message_topics WHERE topic_id = $1", topic_id)
        
        # Удаляем тему
        await conn.execute("DELETE FROM topics WHERE id = $1", topic_id)
        
        return {
            "deleted_topic_id": topic_id,
            "name": topic['name']
        }
        
    finally:
        await conn.close()


@pro_bp.route('/api/topics/default', methods=['POST'])
def add_default_topics():
    """Добавить предустановленные темы"""
    try:
        # Запускаем добавление тем асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_add_default_topics_async())
            return jsonify({
                "status": "ok",
                "result": result
            })
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка добавления предустановленных тем: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


async def _add_default_topics_async():
    """Асинхронная функция добавления предустановленных тем"""
    default_topics = [
        {
            "name": "📝 Блоги",
            "description": "Персональные и авторские каналы, где публикуются мысли, наблюдения, обзоры, личный опыт и комментарии по различным темам. Контент часто субъективен, ориентирован на личный бренд или аудиторию автора.",
            "synonyms": ["Личные блоги", "Авторские каналы", "Мнения", "Опыт и размышления", "Дневники"]
        },
        {
            "name": "📰 Новости и СМИ",
            "description": "Информационные ресурсы, публикующие новости, репортажи и аналитику по актуальным событиям. Тематика — политика, экономика, общество, происшествия, международные события.",
            "synonyms": ["Новости", "СМИ", "Актуальные события", "Информационные каналы", "Политические новости"]
        },
        {
            "name": "🎭 Юмор и развлечения",
            "description": "Контент, предназначенный для развлечения аудитории: шутки, мемы, анекдоты, смешные видео и истории. Часто ориентирован на вирусное распространение и реакцию пользователей.",
            "synonyms": ["Мемы", "Шутки", "Развлекательный контент", "Приколы", "Юмор"]
        },
        {
            "name": "💻 Технологии",
            "description": "Темы, связанные с IT, гаджетами, инновациями, программированием, стартапами и новыми технологиями. Включает новости из мира науки и техники.",
            "synonyms": ["IT", "Техно", "Инновации", "Гаджеты", "Программирование"]
        },
        {
            "name": "💰 Экономика",
            "description": "Финансовая аналитика, макроэкономика, инвестиции, инфляция, валютные рынки и бизнес-тенденции. Часто сопровождается графиками и экспертными комментариями.",
            "synonyms": ["Финансы", "Инвестиции", "Бизнес-экономика", "Рынки", "Аналитика"]
        },
        {
            "name": "🏢 Бизнес и стартапы",
            "description": "Темы предпринимательства, управления, стартап-культуры и личной эффективности в бизнесе. Часто охватывает кейсы и советы по развитию компаний.",
            "synonyms": ["Предпринимательство", "Стартапы", "Бизнес-развитие", "Менеджмент", "Финансовое управление"]
        },
        {
            "name": "₿ Криптовалюты",
            "description": "Информация о блокчейне, криптовалютах, NFT и DeFi. Аналитика рынка, прогнозы и обучающие материалы по цифровым активам.",
            "synonyms": ["Блокчейн", "Bitcoin", "Crypto", "DeFi", "NFT"]
        },
        {
            "name": "✈️ Путешествия",
            "description": "Описание стран, маршрутов, лайфхаки для туристов, советы по бронированию, фотографии достопримечательностей и личный опыт путешествий.",
            "synonyms": ["Туризм", "Поездки", "Отдых", "Путеводители", "География"]
        },
        {
            "name": "📢 Маркетинг, PR, реклама",
            "description": "Статьи и кейсы по продвижению брендов, анализ рекламных кампаний, тренды digital-маркетинга и социальные сети как инструмент бизнеса.",
            "synonyms": ["Digital", "Реклама", "Продвижение", "Маркетинг", "PR"]
        },
        {
            "name": "🧠 Психология",
            "description": "Посты о человеческом поведении, эмоциях, мотивации, саморазвитии и межличностных отношениях. Часто включает советы по личностному росту.",
            "synonyms": ["Саморазвитие", "Сознание", "Психотерапия", "Мотивация", "Эмоции"]
        },
        {
            "name": "🎨 Дизайн",
            "description": "Темы визуального оформления, UX/UI, графического дизайна, брендинга и эстетики. Часто сопровождаются портфолио и вдохновением.",
            "synonyms": ["UX/UI", "Графика", "Иллюстрации", "Брендинг", "Архитектура визуала"]
        },
        {
            "name": "🏛️ Политика",
            "description": "Публикации о государственных решениях, выборах, геополитике, международных отношениях и политических движениях.",
            "synonyms": ["Геополитика", "Власть", "Выборы", "Политические новости", "Общество"]
        },
        {
            "name": "🖼️ Искусство",
            "description": "Контент о живописи, кино, театре, скульптуре, музыке и современных формах искусства. Часто обсуждаются культурные события и выставки.",
            "synonyms": ["Культура", "Театр", "Живопись", "Музыка", "Киноискусство"]
        },
        {
            "name": "⚖️ Право",
            "description": "Материалы о юриспруденции, гражданском и уголовном праве, законодательстве и юридических консультациях.",
            "synonyms": ["Юриспруденция", "Закон", "Адвокатура", "Правила", "Законодательство"]
        },
        {
            "name": "🎓 Образование",
            "description": "Каналы о школьном и высшем образовании, онлайн-курсах, самообучении и методиках преподавания.",
            "synonyms": ["Учёба", "Курсы", "Самообучение", "Обучение", "Знания"]
        },
        {
            "name": "📚 Книги",
            "description": "Обзоры литературы, рекомендации по чтению, рецензии и цитаты из художественных и научных произведений.",
            "synonyms": ["Литература", "Рецензии", "Чтение", "Библиотека", "Классика"]
        },
        {
            "name": "🏋️ Здоровье и фитнес",
            "description": "Советы по питанию, тренировкам, здоровому образу жизни, восстановлению и спортивной мотивации.",
            "synonyms": ["Фитнес", "Питание", "Спорт", "ЗОЖ", "Тренировки"]
        },
        {
            "name": "🍽️ Еда и кулинария",
            "description": "Рецепты, советы по готовке, ресторанные обзоры и фото блюд. Часто включает лайфхаки и видеоуроки.",
            "synonyms": ["Кулинария", "Рецепты", "Еда", "Готовка", "Рестораны"]
        },
        {
            "name": "🎮 Игры",
            "description": "Новости игровой индустрии, обзоры игр, киберспорт, стриминг и игровая культура.",
            "synonyms": ["Гейминг", "Игровая индустрия", "Киберспорт", "Консоли", "PC игры"]
        },
        {
            "name": "📱 Telegram",
            "description": "Информация и новости о Telegram, подборки каналов, инструкции, обновления и полезные функции приложения.",
            "synonyms": ["Телеграм", "Мессенджеры", "Чаты", "Каналы", "Социальные сети"]
        },
        {
            "name": "🌿 Природа",
            "description": "Материалы о флоре, фауне, экологии, природе, животном мире и охране окружающей среды.",
            "synonyms": ["Экология", "Животные", "Растения", "Природные ресурсы", "Охрана природы"]
        },
        {
            "name": "🏡 Интерьер и строительство",
            "description": "Темы ремонта, дизайна, архитектуры, благоустройства и обустройства жилья. Часто встречаются слова 'ремонт', 'интерьер', 'дизайн', 'планировка', 'совет строителя'.",
            "synonyms": ["Дизайн интерьера", "Ремонт", "Строительство", "Благоустройство", "Архитектура"]
        },
        {
            "name": "⛪ Религия",
            "description": "Публикации о вере, духовности, религиозных праздниках, философии, традициях разных конфессий. Тон уважительный, часто содержит цитаты и размышления о смысле жизни.",
            "synonyms": ["Духовность", "Вера", "Религиозные традиции", "Философия", "Праздники"]
        },
        {
            "name": "🎬 Видео и фильмы",
            "description": "Обзоры фильмов, рецензии, трейлеры, рекомендации по просмотру, обсуждения актёров, режиссёров, жанров и киноиндустрии.",
            "synonyms": ["Кино", "Фильмы", "Рецензии", "Трейлеры", "Кинематограф"]
        },
        {
            "name": "🧳 Карьерa",
            "description": "Материалы о профессиональном росте, поиске работы, карьерных возможностях, навыках и личностном развитии в профессиональной сфере.",
            "synonyms": ["Работа", "Карьерный рост", "Профессии", "Рабочие навыки", "HR"]
        }
    ]
    
    config = get_config()
    conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
    
    try:
        added_topics = []
        skipped_topics = []
        
        for topic in default_topics:
            name = topic['name']
            description = topic['description']
            synonyms = topic.get('synonyms', [])
            
            # Проверяем, не существует ли уже такая тема
            existing = await conn.fetchval(
                "SELECT id FROM topics WHERE name = $1",
                name
            )
            
            if existing:
                skipped_topics.append(name)
                continue
            
            # Добавляем новую тему с синонимами
            topic_id = await conn.fetchval(
                "INSERT INTO topics (name, description, synonyms, created_at) VALUES ($1, $2, $3, NOW()) RETURNING id",
                name, description, synonyms
            )
            
            added_topics.append({
                "id": topic_id,
                "name": name,
                "description": description,
                "synonyms": synonyms
            })
        
        return {
            "added_count": len(added_topics),
            "skipped_count": len(skipped_topics),
            "added_topics": added_topics,
            "skipped_topics": skipped_topics
        }
        
    finally:
        await conn.close()


# API endpoints старого функционала экспорта кластеризации удалены - используется только тематическое моделирование

@pro_bp.route('/api/model/info', methods=['GET'])
def get_model_info():
    """Получить информацию о текущей модели эмбеддингов"""
    try:
        from pro_mode.embedding_service import embedding_service
        
        model_name = embedding_service.provider.model_name
        dimension = embedding_service.provider.get_dimension()
        
        # Статистика модели
        model_stats = {
            'sberbank-ai/sbert_large_nlu_ru': {
                'name': 'sberbank-ai/sbert_large_nlu_ru',
                'display_name': 'SBERT Large NLU Russian',
                'dimension': 1024,
                'avg_similarity': 0.77,
                'clustering_quality': 'Плохое',
                'single_clusters': '30%',
                'performance': 'Медленная',
                'description': 'Русскоязычная модель с высокой размерностью, но плохим качеством кластеризации'
            },
        }
        
        # Используем FRIDA как модель по умолчанию
        current_model = model_stats.get(model_name, {
            'name': 'ai-forever/FRIDA',
            'display_name': 'FRIDA (ai-forever)',
            'dimension': 1536,
            'avg_similarity': 0.0,
            'clustering_quality': 'Хорошее',
            'single_clusters': '0%',
            'performance': 'Быстрая',
            'description': 'Русскоязычная модель для поиска и классификации'
        })
        
        return jsonify({
            "status": "ok",
            "current_model": current_model,
            "available_models": list(model_stats.values())
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о модели: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@pro_bp.route('/api/model/switch', methods=['POST'])
def switch_model():
    """Переключить модель эмбеддингов (устаревший эндпоинт - теперь используется только FRIDA)"""
    try:
        # Этот эндпоинт больше не используется, так как теперь используется только FRIDA
        return jsonify({
            "status": "deprecated",
            "message": "Переключение моделей больше не поддерживается. Используется только FRIDA (ai-forever/FRIDA)",
            "current_model": "ai-forever/FRIDA",
            "dimension": 1536
        })
        
    except Exception as e:
        logger.error(f"Ошибка переключения модели: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ============================================================================
# TOPIC MODELING API ENDPOINTS
# ============================================================================

@pro_bp.route('/api/topic-modeling/run', methods=['POST'])
def run_topic_modeling():
    """
    Запустить пайплайн тематического моделирования через Huey
    
    Параметры (JSON):
        - limit (int, optional): Лимит постов для обработки
        - days_back (int, default=30): Количество дней назад для загрузки постов
        - async (bool, default=True): Запустить асинхронно через Huey
    
    Returns:
        JSON с task_id (если async=True) или результатом выполнения
    """
    try:
        if not TOPIC_MODELING_AVAILABLE:
            return jsonify({
                "status": "error",
                "error": "Topic modeling tasks не доступны. Проверьте настройку Huey."
            }), 500
        
        data = request.get_json() or {}
        limit = data.get('limit')
        days_back = data.get('days_back', 30)
        run_async = data.get('async', True)
        run_classification = data.get('run_classification', True)  # По умолчанию включено
        
        logger.info(f"Запрос на запуск topic modeling: limit={limit}, days_back={days_back}, async={run_async}, run_classification={run_classification}")
        
        if run_async:
            # Запускаем через Huey (асинхронно)
            task = run_topic_modeling_pipeline(limit=limit, days_back=days_back, run_classification=run_classification)
            task_id = task.id if hasattr(task, 'id') else str(task)
            
            logger.info(f"Задача topic modeling поставлена в очередь Huey: {task_id}")
            
            return jsonify({
                "status": "ok",
                "message": "Задача тематического моделирования поставлена в очередь",
                "task_id": task_id,
                "async": True
            })
        else:
            # Запускаем синхронно (не рекомендуется для больших объемов)
            from pro_mode.topic_modeling_service import TopicModelingService
            
            async def _run_sync():
                service = TopicModelingService()
                return await service.run_full_pipeline(
                    fetch_from_db=True,
                    run_classification=run_classification
                )
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_run_sync())
                return jsonify({
                    "status": "ok",
                    "message": "Тематическое моделирование завершено",
                    "result": result,
                    "async": False
                })
            finally:
                loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка запуска topic modeling: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@pro_bp.route('/api/topic-modeling/classification/run', methods=['POST'])
def run_classification():
    """
    Ручной запуск классификации сообщений по темам
    
    Параметры (JSON):
        - limit (int, optional): Лимит сообщений для классификации
        - message_ids (list, optional): Список ID сообщений для классификации
    
    Returns:
        JSON с результатом классификации
    """
    try:
        from pro_mode.classification_service import ClassificationService
        
        data = request.get_json() or {}
        limit = data.get('limit')
        message_ids = data.get('message_ids')
        
        logger.info(f"Запрос на запуск классификации: limit={limit}, message_ids={message_ids}")
        
        async def _run_classification():
            service = ClassificationService()
            result = await service.classify_all_messages_in_pipeline(
                message_ids=message_ids,
                limit=limit
            )
            return result
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_run_classification())
            return jsonify({
                "status": "ok",
                "message": "Классификация завершена",
                "result": result
            })
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка запуска классификации: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@pro_bp.route('/api/topics/replace-universal', methods=['POST'])
def replace_topics_universal():
    """
    Заменить все темы на универсальный список из 12 тем (автоматически, без подтверждения)
    
    Returns:
        JSON с результатом операции
    """
    try:
        import sys
        import os
        import importlib.util
        
        # Добавляем путь к проекту для импорта миграции
        # __file__ = pro_mode/api.py, нужно получить корень проекта (telegram_parser)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Импортируем функцию из правильной миграции (используем importlib для файлов с цифрами в начале)
        migration_file = os.path.join(project_root, 'migrations', '006_replace_topics_with_universal.py')
        spec = importlib.util.spec_from_file_location("migration_006", migration_file)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)
        
        # Вызываем функцию замены тем
        # Перехватываем SystemExit, если функция вызывает sys.exit()
        try:
            migration_module.replace_topics()
        except SystemExit as e:
            if e.code != 0:
                raise Exception(f"Миграция завершилась с ошибкой: {e.code}")
        
        # Инвалидируем кеш классификации
        try:
            from pro_mode.classification_service import ClassificationService
            service = ClassificationService()
            service.invalidate_cache()
        except Exception:
            pass
        
        return jsonify({
            "status": "ok",
            "message": "Темы успешно заменены на универсальный список",
            "result": {
                "success": True,
                "message": "Замена тем выполнена успешно"
            }
        })
        
    except Exception as e:
        logger.error(f"Ошибка замены тем: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@pro_bp.route('/api/topic-modeling/classification/invalidate-cache', methods=['POST'])
def invalidate_classification_cache():
    """
    Инвалидировать кеш эталонов тем для классификации
    
    Returns:
        JSON с результатом операции
    """
    try:
        from pro_mode.classification_service import ClassificationService
        
        service = ClassificationService()
        service.invalidate_cache()
        
        logger.info("Кеш эталонов тем инвалидирован через API")
        
        return jsonify({
            "status": "ok",
            "message": "Кеш эталонов тем успешно инвалидирован"
        })
        
    except Exception as e:
        logger.error(f"Ошибка инвалидации кеша: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@pro_bp.route('/api/topic-modeling/titles/regenerate', methods=['POST'])
def regenerate_topic_titles():
    """
    Перегенерация заголовков через Qwen (без индексации/BERTopic).
    """
    try:
        data = request.get_json() or {}
        limit = data.get('limit')
        limit_value = limit if isinstance(limit, int) and limit > 0 else None

        service = TopicModelingService()
        result = asyncio.run(service.regenerate_titles(limit=limit_value))

        return jsonify({
            "status": "ok",
            "message": "Заголовки обновлены",
            "result": result
        })
    except Exception as e:
        logger.error(f"Ошибка обновления заголовков: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@pro_bp.route('/api/topic-modeling/status', methods=['GET'])
def get_topic_modeling_status():
    """
    Получить статус последнего запуска тематического моделирования
    
    Returns:
        JSON с информацией о последних кластерах и статистикой
    """
    try:
        import asyncpg
        from config_utils import get_config
        
        async def _get_status():
            config = get_config()
            conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
            
            # Получаем статистику по кластерам
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_clusters,
                    SUM(size) as total_posts,
                    MAX(created_at) as last_update
                FROM dedup_clusters
            """)
            
            # Получаем последние кластеры
            recent_clusters = await conn.fetch("""
                SELECT id, title, keywords, size, created_at
                FROM dedup_clusters
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            await conn.close()
            
            return {
                "total_clusters": stats['total_clusters'] or 0,
                "total_posts": stats['total_posts'] or 0,
                "last_update": stats['last_update'].isoformat() if stats['last_update'] else None,
                "recent_clusters": [
                    {
                        "id": r['id'],
                        "title": r['title'],
                        "keywords": r['keywords'],
                        "size": r['size'],
                        "created_at": r['created_at'].isoformat() if r['created_at'] else None
                    }
                    for r in recent_clusters
                ]
            }
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            status = loop.run_until_complete(_get_status())
            return jsonify({
                "status": "ok",
                "data": status
            })
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса topic modeling: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@pro_bp.route('/api/topic-modeling/settings', methods=['GET'])
def get_topic_modeling_settings():
    """Получить текущие настройки Topic Modeling Pipeline."""
    try:
        from pro_mode.topic_modeling_service import TopicModelingConfig
        config = TopicModelingConfig.from_config_file()
        settings = load_topic_modeling_settings()
        specs = get_setting_specs()
        groups = get_setting_groups()
        return jsonify({
            "status": "ok",
            "data": {
                "values": settings,
                "effective": asdict(config),
                "specs": specs,
                "groups": groups
            }
        })
    except Exception as e:
        logger.error(f"Ошибка получения настроек topic modeling: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@pro_bp.route('/api/topic-modeling/settings', methods=['POST'])
def update_topic_modeling_settings():
    """Обновить настройки Topic Modeling через UI."""
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"status": "error", "error": "Нет данных для обновления"}), 400
        settings = save_topic_modeling_settings(data)
        from pro_mode.topic_modeling_service import TopicModelingConfig
        config = TopicModelingConfig.from_config_file()
        return jsonify({
            "status": "ok",
            "message": "Настройки сохранены",
            "data": {
                "values": settings,
                "effective": asdict(config)
            }
        })
    except RuntimeError as e:
        logger.error(f"Ошибка сохранения настроек topic modeling: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500
    except Exception as e:
        logger.error(f"Неожиданная ошибка сохранения настроек topic modeling: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@pro_bp.route('/api/topic-modeling/progress', methods=['GET'])
def topic_modeling_progress():
    """Возвращает текущее состояние пайплайна (для stepper/логов)."""
    try:
        progress = get_current_progress()
        return jsonify({
            "status": "ok",
            "data": progress
        })
    except Exception as e:
        logger.error(f"Ошибка получения прогресса topic modeling: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@pro_bp.route('/api/topic-modeling/cancel', methods=['POST'])
def cancel_topic_modeling():
    """Запросить отмену текущего пайплайна."""
    data = request.get_json() or {}
    task_id = data.get("task_id")
    if request_cancel(task_id):
        return jsonify({
            "status": "ok",
            "message": "Отмена пайплайна запрошена"
        })
    return jsonify({
        "status": "error",
        "error": "Активный пайплайн не найден"
    }), 404

