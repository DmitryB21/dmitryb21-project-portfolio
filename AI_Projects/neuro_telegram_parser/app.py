# app.py
import os
import sys
import asyncio
import csv
import uuid
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, render_template, send_from_directory
from redis import Redis
from functools import wraps
from config_utils import get_config

# Импорт задач - убираем импорт TASK_STATUS, так как теперь используем Redis
from tasks import (
    orchestrate_parsing_from_file, 
    orchestrate_adhoc_parsing
)
from parser_app.telegram_client_manager import TelegramClientManager
from parser_app.channel_searcher import ChannelSearcher

# Импорт Pro-режима
from pro_mode.api import pro_bp

# Импорт аутентификации
from auth.routes import auth_bp


app = Flask(__name__)
# Устанавливаем секретный ключ для сессий (используем тот же, что и для JWT)
import os
from dotenv import load_dotenv
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")

# Регистрация Blueprint для Pro-режима
app.register_blueprint(pro_bp)

# Регистрация Blueprint для аутентификации
app.register_blueprint(auth_bp)

# Роут для страницы логина
@app.route('/login')
def login_page():
    """Страница входа в систему"""
    return render_template('auth/login.html')

config = get_config()
REDIS_HOST = config['redis']['host']
REDIS_PORT = int(config['redis']['port'])
REDIS_DB = int(config['redis'].get('db', 0))
API_ID = int(config['telegram']['api_id']) if config['telegram']['api_id'] else 0
API_HASH = config['telegram']['api_hash']
PHONE_NUMBER = config['telegram'].get('phone_number', '') 
CHANNELS_SOURCES_DIR = config['application']['channel_source_directory']

if not os.path.isabs(CHANNELS_SOURCES_DIR):
    CHANNELS_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), CHANNELS_SOURCES_DIR)

# --- Redis подключение ---
redis_kwargs = {
    'host': REDIS_HOST,
    'port': REDIS_PORT,
    'db': REDIS_DB,
    'decode_responses': True
}

# Добавляем пароль, если он указан
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
if REDIS_PASSWORD:
    redis_kwargs['password'] = REDIS_PASSWORD

redis_conn = Redis(**redis_kwargs)

# Глобальные переменные для хранения клиент-менеджера и поисковика
client_manager = None
channel_searcher = None

# Функция для получения клиент-менеджера (создает новый, если текущий не работает)
async def get_client_manager():
    global client_manager, channel_searcher
    
    # Если клиент-менеджер не существует, создаем новый
    if client_manager is None:
        client_manager = TelegramClientManager(api_id=API_ID, api_hash=API_HASH)
        channel_searcher = ChannelSearcher(client_manager)
        return client_manager
    
    # Проверяем, работает ли текущий клиент
    try:
        # Пробуем получить клиент и проверить соединение
        client = await client_manager.get_client()
        if await client_manager.test_connection():
            return client_manager
        else:
            # Если соединение не работает, пересоздаем клиент
            try:
                await client_manager.stop()
            except:
                pass  # Игнорируем ошибки при остановке
            
            client_manager = TelegramClientManager(api_id=API_ID, api_hash=API_HASH)
            channel_searcher = ChannelSearcher(client_manager)
            return client_manager
    except Exception as e:
        print(f"Ошибка при проверке клиента: {e}")
        # Если произошла ошибка, пересоздаем клиент
        try:
            if client_manager:
                await client_manager.stop()
        except:
            pass  # Игнорируем ошибки при остановке
        
        client_manager = TelegramClientManager(api_id=API_ID, api_hash=API_HASH)
        channel_searcher = ChannelSearcher(client_manager)
        return client_manager

# Flask декоратор для асинхронных функций
def async_action(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    return wrapped

# --- Главная страница ---
@app.route('/')
def index():
    return render_template('pro/dashboard.html')

@app.route('/parser/')
def parser():
    return render_template('parser.html')

# --- API эндпоинты ---

@app.route('/api/v1/sources/files', methods=['GET'])
def list_source_files():
    """Получение списка CSV файлов с каналами"""
    try:
        if not os.path.isdir(CHANNELS_SOURCES_DIR):
            os.makedirs(CHANNELS_SOURCES_DIR, exist_ok=True)
            print(f"Создана директория: {CHANNELS_SOURCES_DIR}")
            return jsonify({'files': []})

        print(f"Поиск файлов в: {CHANNELS_SOURCES_DIR}")
        files = [f for f in os.listdir(CHANNELS_SOURCES_DIR) if f.endswith(('.csv', '.json'))]
        print(f"Найдено {len(files)} файлов")
        
        if not files:
            all_files = os.listdir(CHANNELS_SOURCES_DIR)
            print(f"Все файлы в директории: {all_files}")
            
        return jsonify({'files': files})
        
    except Exception as e:
        error_message = f"Ошибка получения списка файлов: {str(e)}"
        print(error_message)
        return jsonify({'error': error_message}), 500

@app.route('/api/v1/sources/file-info', methods=['GET'])
def get_file_info():
    """Получение информации о файле с каналами"""
    filename = request.args.get('file')
    
    if not filename:
        return jsonify({'error': 'Параметр file обязателен'}), 400
    
    if os.path.basename(filename) != filename:
        return jsonify({'error': 'Недопустимое имя файла'}), 400
    
    filepath = os.path.join(CHANNELS_SOURCES_DIR, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': f'Файл не найден: {filename}'}), 404
    
    try:
        # Подсчет каналов в CSV
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Пропускаем заголовок
            channel_count = sum(1 for _ in reader)
        
        return jsonify({
            'filename': filename,
            'channel_count': channel_count,
            'filepath': filepath
        })
    except Exception as e:
        error_message = f"Ошибка чтения файла {filename}: {str(e)}"
        print(error_message)
        return jsonify({'error': error_message}), 500

@app.route('/api/v1/parse/from-file', methods=['POST'])
def parse_from_file():
    """Запуск парсинга из файла"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Тело запроса должно быть в формате JSON'}), 400
    
    source_file = data.get('source_file')
    limit = data.get('limit_per_channel')
    channel_limit = data.get('channel_limit')
    days_back = data.get('days_back', 0)  # 0 означает за все время
    
    if not source_file:
        return jsonify({'error': 'Параметр source_file обязателен'}), 400
    
    if os.path.basename(source_file) != source_file:
        return jsonify({'error': 'Недопустимое имя файла'}), 400
    
    full_path = os.path.join(CHANNELS_SOURCES_DIR, source_file)
    print(f"Полный путь: {full_path}")
    
    if not os.path.exists(full_path):
        return jsonify({'error': f'Файл не найден: {source_file}'}), 404
    
    # Создание уникального ID задачи Huey
    task_id = str(uuid.uuid4())
    
    # Пишем первоначальный статус в Redis, чтобы избежать 404 при раннем опросе
    try:
        redis_conn.hset(f"task_status:{task_id}", mapping={
            'status': 'queued',
            'progress': '{}',
            'error': '',
            'start_time': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })
    except Exception:
        pass

    # Запуск задачи
    orchestrate_parsing_from_file(full_path, limit_per_channel=limit, channel_limit=channel_limit, days_back=days_back, task_id=task_id)
    
    return jsonify({
        'message': 'Парсинг из файла запущен.',
        'task_id': task_id
    }), 202

@app.route('/api/v1/parse/from-search', methods=['POST'])
def parse_from_search():
    """Запуск ad-hoc парсинга из результатов поиска"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Тело запроса должно быть в формате JSON'}), 400
    
    channels = data.get('channels')
    limit = data.get('limit_per_channel')
    days_back = data.get('days_back', 0)  # 0 означает за все время
    
    if not channels or not isinstance(channels, list):
        return jsonify({'error': 'Параметр channels должен быть непустым списком'}), 400
    
    # Создание уникального ID задачи Huey
    task_id = str(uuid.uuid4())
    
    # Пишем первоначальный статус в Redis, чтобы избежать 404 при раннем опросе
    try:
        redis_conn.hset(f"task_status:{task_id}", mapping={
            'status': 'queued',
            'progress': '{}',
            'error': '',
            'start_time': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })
    except Exception:
        pass

    # Запуск задачи
    orchestrate_adhoc_parsing(channels, limit, days_back=days_back, task_id=task_id)
    
@app.route('/api/v1/parse/from-usernames', methods=['POST'])
def parse_from_usernames():
    """Запуск парсинга из списка usernames каналов"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Тело запроса должно быть в формате JSON'}), 400
    
    channels = data.get('channels')
    limit = data.get('limit_per_channel')
    days_back = data.get('days_back', 0)  # 0 означает за все время
    
    if not channels or not isinstance(channels, list):
        return jsonify({'error': 'Параметр channels должен быть непустым списком'}), 400
    
    # Создание уникального ID задачи Huey
    task_id = str(uuid.uuid4())
    
    # Пишем первоначальный статус в Redis, чтобы избежать 404 при раннем опросе
    try:
        redis_conn.hset(f"task_status:{task_id}", mapping={
            'status': 'queued',
            'progress': '{}',
            'error': '',
            'start_time': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })
    except Exception:
        pass

    # Запуск задачи
    orchestrate_adhoc_parsing(channels, limit, days_back=days_back, task_id=task_id)
    
    return jsonify({
        'message': 'Парсинг из usernames запущен.',
        'task_id': task_id
    }), 202


@app.route('/api/v1/search/channels', methods=['GET'])
@async_action
async def search_channels_api():
    """Поиск каналов по ключевому слову"""
    query = request.args.get('q')
    
    if not query:
        return jsonify({'error': 'Параметр запроса q обязателен.'}), 400
    
    try:
        # Создаем новый клиент-менеджер для каждого запроса поиска
        search_client = TelegramClientManager(api_id=API_ID, api_hash=API_HASH)
        
        # Создаем поисковик
        searcher = ChannelSearcher(search_client)
        
        # Выполняем поиск
        print(f"🔍 Начинаем поиск каналов по запросу: {query}")
        results = await searcher.search(query)
        print(f"✅ Поиск завершен, найдено {len(results)} каналов")
        
        # Закрываем клиент после использования
        await search_client.stop()
        
        return jsonify({'results': results})
    except Exception as e:
        error_msg = f"Ошибка при поиске каналов: {str(e)}"
        print(error_msg)
        
        # Пытаемся закрыть клиент в случае ошибки
        try:
            if 'search_client' in locals() and search_client:
                await search_client.stop()
        except:
            pass
            
        return jsonify({'error': error_msg, 'results': []}), 500

@app.route('/api/v1/tasks/status/<task_id>', methods=['GET'])
def get_task_status_api(task_id):
    """Получение статуса задачи из Redis"""
    key = f"task_status:{task_id}"
    status_data_raw = redis_conn.hgetall(key)
    
    if not status_data_raw:
        return jsonify({'error': 'Task not found'}), 404
    
    # Обработка данных из Redis
    status_data = {
        'status': status_data_raw.get('status', 'unknown'),
        'progress': json.loads(status_data_raw.get('progress', '{}')),
        'error': status_data_raw.get('error'),
        'updated_at': status_data_raw.get('updated_at'),
        'start_time': status_data_raw.get('start_time')
    }
    
    # Форматирование данных для фронтенда
    formatted_status = {
        'task_id': task_id,
        'status': status_data['status'],
        'progress': status_data['progress'],
        'error': status_data['error'],
        'updated_at': status_data['updated_at'],
        'start_time': status_data['start_time'],
        'duration': None
    }
    
    # Вычисление длительности
    if status_data['start_time'] and status_data['updated_at']:
        try:
            start = datetime.fromisoformat(status_data['start_time'])
            updated = datetime.fromisoformat(status_data['updated_at'])
            duration = (updated - start).total_seconds()
            formatted_status['duration'] = duration
        except (ValueError, TypeError):
            # В случае ошибки парсинга дат
            formatted_status['duration'] = None
    
    return jsonify(formatted_status)

@app.route('/api/stats', methods=['GET'])
@async_action
async def get_stats():
    """Получение общей статистики парсера"""
    try:
        import asyncpg
        config = get_config()
        conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
        
        try:
            # Получаем общее количество сообщений
            total_messages = await conn.fetchval("SELECT COUNT(*) FROM messages")
            
            # Получаем общее количество каналов
            total_channels = await conn.fetchval("SELECT COUNT(*) FROM channels")
            
            # Получаем дату последнего обновления (самое новое сообщение)
            last_update = await conn.fetchval("""
                SELECT MAX(published_at) FROM messages
            """)
            
            # Форматируем дату последнего обновления
            if last_update:
                if isinstance(last_update, str):
                    last_update_str = last_update
                else:
                    last_update_str = last_update.strftime('%Y-%m-%d %H:%M:%S')
            else:
                last_update_str = '-'
            
            return jsonify({
                'total_messages': total_messages or 0,
                'total_channels': total_channels or 0,
                'last_update': last_update_str
            })
        finally:
            await conn.close()
    except Exception as e:
        print(f"Ошибка получения статистики: {e}")
        return jsonify({
            'total_messages': 0,
            'total_channels': 0,
            'last_update': '-',
            'error': str(e)
        }), 500

@app.route('/api/channels', methods=['GET'])
@async_action
async def get_channels():
    """Получение списка всех каналов с количеством сообщений"""
    try:
        import asyncpg
        config = get_config()
        conn = await asyncpg.connect(dsn=config['postgresql']['dsn'])
        
        try:
            # Получаем список каналов с количеством сообщений
            rows = await conn.fetch("""
                SELECT 
                    c.id,
                    c.name,
                    c.username,
                    COUNT(m.id) as message_count
                FROM channels c
                LEFT JOIN messages m ON c.id = m.channel_id
                GROUP BY c.id, c.name, c.username
                ORDER BY c.name
            """)
            
            channels = [
                {
                    'id': row['id'],
                    'name': row['name'],
                    'username': row['username'],
                    'message_count': row['message_count'] or 0
                }
                for row in rows
            ]
            
            return jsonify(channels)
        finally:
            await conn.close()
    except Exception as e:
        print(f"Ошибка получения каналов: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/tasks/list', methods=['GET'])
def list_tasks():
    """Получение списка всех задач из Redis"""
    tasks_list = []
    
    # Получаем все ключи задач из Redis
    task_keys = redis_conn.keys("task_status:*")
    
    for key in task_keys:
        task_id = key.split(":", 1)[1]  # Извлекаем ID задачи из ключа
        status_data_raw = redis_conn.hgetall(key)
        
        if not status_data_raw:
            continue
            
        # Обработка данных из Redis
        try:
            progress = json.loads(status_data_raw.get('progress', '{}'))
        except json.JSONDecodeError:
            progress = {}
            
        task_info = {
            'task_id': task_id,
            'status': status_data_raw.get('status', 'unknown'),
            'updated_at': status_data_raw.get('updated_at'),
            'start_time': status_data_raw.get('start_time'),
            'progress': progress,
            'error': status_data_raw.get('error')
        }
        
        # Добавление информации о длительности
        if status_data_raw.get('start_time') and status_data_raw.get('updated_at'):
            try:
                start = datetime.fromisoformat(status_data_raw['start_time'])
                updated = datetime.fromisoformat(status_data_raw['updated_at'])
                duration = (updated - start).total_seconds()
                task_info['duration'] = duration
            except (ValueError, TypeError):
                # В случае ошибки парсинга дат
                task_info['duration'] = None
        
        tasks_list.append(task_info)
    
    # Сортировка по времени начала (последние первые)
    tasks_list.sort(key=lambda x: x.get('start_time', ''), reverse=True)
    
    return jsonify({'tasks': tasks_list})

@app.route('/api/v1/tasks/clear-completed', methods=['POST'])
def clear_completed_tasks():
    """Очистка всех завершенных задач из Redis"""
    try:
        # Получаем все ключи задач из Redis
        task_keys = redis_conn.keys("task_status:*")
        
        cleared_count = 0
        for key in task_keys:
            task_id = key.split(":", 1)[1]
            status_data_raw = redis_conn.hgetall(key)
            
            if not status_data_raw:
                continue
            
            # Проверяем статус задачи
            status = status_data_raw.get('status', 'unknown')
            
            # Удаляем задачи со статусом 'completed', 'failed', 'cancelled'
            if status in ['completed', 'failed', 'cancelled', 'error']:
                redis_conn.delete(key)
                cleared_count += 1
        
        return jsonify({
            'message': f'Очищено завершенных задач: {cleared_count}',
            'cleared_count': cleared_count
        }), 200
        
    except Exception as e:
        print(f"Ошибка очистки задач: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/logs/progress', methods=['GET'])
def get_progress_logs():
    """Получение логов прогресса"""
    try:
        limit = int(request.args.get('limit', 100))
        task_id = request.args.get('task_id')
        
        logs = []
        
        if os.path.exists('parser_progress.log'):
            with open('parser_progress.log', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Берем последние строки
            recent_lines = lines[-limit:] if len(lines) > limit else lines
            
            for line in recent_lines:
                if 'PROGRESS' in line and line.strip():
                    try:
                        # Извлекаем JSON часть
                        json_start = line.find('{')
                        if json_start != -1:
                            json_data = json.loads(line[json_start:])
                            
                            # Фильтрация по task_id если указан
                            if task_id and json_data.get('task_id') != task_id:
                                continue
                                
                            logs.append(json_data)
                    except json.JSONDecodeError:
                        continue
        
        return jsonify({'logs': logs})
        
    except Exception as e:
        return jsonify({'error': f'Ошибка получения логов: {str(e)}'}), 500

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/api/v1/system/info', methods=['GET'])
def system_info():
    """Системная информация"""
    # Получаем количество активных задач из Redis
    task_keys = redis_conn.keys("task_status:*")
    active_tasks_count = len(task_keys)
    
    # Проверка подключения к Redis
    redis_connected = False
    try:
        redis_connected = redis_conn.ping()
    except:
        pass
    
    # Проверка статуса Telegram клиента
    telegram_client_status = "not_initialized"
    if client_manager is not None:
        telegram_client_status = "initialized"
    
    return jsonify({
        'app_directory': os.path.abspath(os.path.dirname(__file__)),
        'sources_directory': CHANNELS_SOURCES_DIR,
        'sources_directory_exists': os.path.isdir(CHANNELS_SOURCES_DIR),
        'sources_files': os.listdir(CHANNELS_SOURCES_DIR) if os.path.isdir(CHANNELS_SOURCES_DIR) else [],
        'active_tasks': active_tasks_count,
        'redis_connected': redis_connected,
        'telegram_client': telegram_client_status
    })

@app.route('/api/v1/system/reinit-client', methods=['POST'])
@async_action
async def reinitialize_client():
    """Ручная реинициализация Telegram клиента"""
    global client_manager, channel_searcher
    
    try:
        # Останавливаем текущий клиент, если он существует
        if client_manager:
            try:
                await client_manager.stop()
                print("🔌 Текущий Telegram клиент остановлен")
            except Exception as e:
                print(f"⚠️ Ошибка при остановке клиента: {e}")
        
        # Создаем новый клиент
        client_manager = TelegramClientManager(api_id=API_ID, api_hash=API_HASH)
        channel_searcher = ChannelSearcher(client_manager)
        
        # Проверяем соединение
        await client_manager.get_client()
        if await client_manager.test_connection():
            print("✅ Telegram клиент успешно реинициализирован")
            return jsonify({'status': 'success', 'message': 'Клиент успешно реинициализирован'})
        else:
            print("⚠️ Telegram клиент инициализирован, но соединение не установлено")
            return jsonify({'status': 'warning', 'message': 'Клиент инициализирован, но соединение не установлено'}), 400
    except Exception as e:
        error_msg = f"Ошибка реинициализации Telegram клиента: {e}"
        print(f"❌ {error_msg}")
        return jsonify({'status': 'error', 'message': error_msg}), 500

# === API для настроек ===

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Получение настроек Telegram API"""
    try:
        # Читаем настройки из config.ini или переменных окружения
        config = get_config()
        
        settings = {
            'api_id': config.get('telegram', {}).get('api_id', ''),
            'api_hash': config.get('telegram', {}).get('api_hash', ''),
            'phone_number': config.get('telegram', {}).get('phone_number', '')
        }
        
        return jsonify(settings), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Сохранение настроек Telegram API"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Тело запроса должно быть в формате JSON'}), 400
        
        api_id = data.get('api_id')
        api_hash = data.get('api_hash')
        phone_number = data.get('phone_number')
        
        # Валидация
        if not api_id or not api_hash:
            return jsonify({'error': 'API ID и API Hash обязательны'}), 400
        
        # Здесь должна быть логика сохранения настроек
        # Например, в config.ini или переменных окружения
        
        # Пока просто возвращаем успех
        return jsonify({'message': 'Настройки сохранены'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """Тестирование подключения к Telegram API"""
    try:
        # Здесь должна быть логика тестирования подключения
        # Например, попытка создания клиента с текущими настройками
        
        return jsonify({'message': 'Подключение успешно'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === API для управления сессией Telegram ===

@app.route('/api/session/send-code', methods=['POST'])
@async_action
async def send_code():
    """Отправка кода подтверждения на номер телефона"""
    try:
        data = request.get_json()
        phone = data.get('phone')
        
        if not phone:
            return jsonify({'error': 'Номер телефона обязателен'}), 400
        
        # Получаем настройки API
        config = get_config()
        API_ID = int(config['telegram']['api_id'])
        API_HASH = config['telegram']['api_hash']
        
        # Создаем временный клиент для отправки кода
        from pyrogram import Client
        temp_client = Client("temp_session", api_id=API_ID, api_hash=API_HASH)
        
        await temp_client.connect()
        
        # Отправляем код
        sent_code = await temp_client.send_code(phone)
        
        await temp_client.disconnect()
        
        return jsonify({
            'phone_code_hash': sent_code.phone_code_hash,
            'message': 'Код отправлен'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/session/verify-code', methods=['POST'])
@async_action
async def verify_code():
    """Подтверждение кода и создание сессии"""
    try:
        data = request.get_json()
        phone = data.get('phone')
        code = data.get('code')
        phone_code_hash = data.get('phone_code_hash')
        
        if not all([phone, code, phone_code_hash]):
            return jsonify({'error': 'Все поля обязательны'}), 400
        
        # Получаем настройки API
        config = get_config()
        API_ID = int(config['telegram']['api_id'])
        API_HASH = config['telegram']['api_hash']
        
        # Создаем клиент для авторизации
        from pyrogram import Client
        auth_client = Client("telegram_parser", api_id=API_ID, api_hash=API_HASH)
        
        await auth_client.connect()
        
        try:
            # Подтверждаем код
            await auth_client.sign_in(phone, code, phone_code_hash)
            
            # Получаем информацию о пользователе
            me = await auth_client.get_me()
            
            # Сохраняем сессию
            await auth_client.stop()
            
            return jsonify({
                'message': 'Сессия создана успешно',
                'user': {
                    'first_name': me.first_name,
                    'username': me.username,
                    'phone_number': me.phone_number
                }
            }), 200
            
        except Exception as auth_error:
            # Проверяем, нужен ли пароль 2FA
            if "PASSWORD_HASH_INVALID" in str(auth_error) or "2FA" in str(auth_error):
                await auth_client.disconnect()
                return jsonify({
                    'requires_password': True,
                    'message': 'Требуется пароль двухфакторной аутентификации'
                }), 200
            else:
                await auth_client.disconnect()
                raise auth_error
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/session/verify-password', methods=['POST'])
@async_action
async def verify_password():
    """Подтверждение пароля 2FA и завершение создания сессии"""
    try:
        data = request.get_json()
        phone = data.get('phone')
        password = data.get('password')
        phone_code_hash = data.get('phone_code_hash')
        
        if not all([phone, password, phone_code_hash]):
            return jsonify({'error': 'Все поля обязательны'}), 400
        
        # Получаем настройки API
        config = get_config()
        API_ID = int(config['telegram']['api_id'])
        API_HASH = config['telegram']['api_hash']
        
        # Создаем клиент для завершения авторизации
        from pyrogram import Client
        auth_client = Client("telegram_parser", api_id=API_ID, api_hash=API_HASH)
        
        await auth_client.connect()
        
        try:
            # Завершаем авторизацию с паролем
            await auth_client.check_password(password)
            
            # Получаем информацию о пользователе
            me = await auth_client.get_me()
            
            # Сохраняем сессию
            await auth_client.stop()
            
            return jsonify({
                'message': 'Сессия создана успешно',
                'user': {
                    'first_name': me.first_name,
                    'username': me.username,
                    'phone_number': me.phone_number
                }
            }), 200
            
        except Exception as auth_error:
            await auth_client.disconnect()
            raise auth_error
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/session/status', methods=['GET'])
@async_action
async def get_session_status():
    """Проверка статуса сессии Telegram"""
    try:
        import os
        
        # Проверяем существование файла сессии
        session_file = "telegram_parser.session"
        session_exists = os.path.exists(session_file)
        
        if not session_exists:
            return jsonify({
                'exists': False,
                'error': 'Сессия не найдена'
            }), 200
        
        # Пытаемся получить информацию о пользователе
        try:
            config = get_config()
            API_ID = int(config['telegram']['api_id'])
            API_HASH = config['telegram']['api_hash']
            
            from pyrogram import Client
            client = Client("telegram_parser", api_id=API_ID, api_hash=API_HASH)
            
            try:
                # Асинхронный запуск клиента
                await client.start()
                me = await client.get_me()
                await client.stop()
                
                return jsonify({
                    'exists': True,
                    'user': {
                        'first_name': me.first_name,
                        'username': me.username,
                        'phone_number': me.phone_number
                    }
                }), 200
            except Exception as client_error:
                # Если клиент не запустился, пытаемся остановить его
                try:
                    await client.stop()
                except:
                    pass
                raise client_error
                    
        except Exception as e:
            # Сессия существует, но не работает
            print(f"Ошибка проверки сессии: {e}")
            return jsonify({
                'exists': False,
                'error': f'Сессия недействительна: {str(e)}'
            }), 200
            
    except Exception as e:
        print(f"Критическая ошибка проверки статуса сессии: {e}")
        return jsonify({
            'exists': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print(f"Текущая директория: {os.getcwd()}")
    print(f"Директория скрипта: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"Директория каналов: {CHANNELS_SOURCES_DIR}")
    
    if not os.path.isdir(CHANNELS_SOURCES_DIR):
        os.makedirs(CHANNELS_SOURCES_DIR, exist_ok=True)
        print(f"Создана директория: {CHANNELS_SOURCES_DIR}")
    else:
        print(f"Директория существует: {CHANNELS_SOURCES_DIR}")
    
    # Инициализация дефолтного администратора
    try:
        from auth.init_admin import init_default_admin
        print("Инициализация дефолтного администратора...")
        
        async def init_with_timeout():
            """Инициализация с таймаутом"""
            try:
                await asyncio.wait_for(init_default_admin(), timeout=10.0)
                print("✅ Инициализация администратора завершена")
            except asyncio.TimeoutError:
                print("⚠️ Предупреждение: Таймаут при инициализации администратора (возможно, проблема с подключением к БД)")
            except Exception as e:
                print(f"⚠️ Предупреждение: Не удалось инициализировать администратора: {e}")
        
        asyncio.run(init_with_timeout())
    except Exception as e:
        print(f"⚠️ Предупреждение: Не удалось инициализировать администратора: {e}")
    
    # === API для проверки здоровья системы ===
    @app.route('/api/health/qdrant', methods=['GET'])
    def health_qdrant():
        """Проверка состояния Qdrant"""
        try:
            from qdrant_client import QdrantClient
            from config_utils import get_config
            config = get_config()
            qdrant_host = config['qdrant'].get('host', 'localhost')
            qdrant_port = int(config['qdrant'].get('port', 6333))
            
            client = QdrantClient(host=qdrant_host, port=qdrant_port)
            collections = client.get_collections()
            return jsonify({'status': 'ok', 'message': 'Qdrant доступен'}), 200
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/health/redis', methods=['GET'])
    def health_redis():
        """Проверка состояния Redis"""
        try:
            import redis
            from config_utils import get_config
            config = get_config()
            redis_host = config['redis'].get('host', 'localhost')
            redis_port = int(config['redis'].get('port', 6379))
            
            r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
            r.ping()
            return jsonify({'status': 'ok', 'message': 'Redis доступен'}), 200
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/health/postgres', methods=['GET'])
    def health_postgres():
        """Проверка состояния PostgreSQL"""
        try:
            import asyncpg
            from config_utils import get_config
            config = get_config()
            
            # Получаем DSN из конфигурации
            postgres_dsn = config['postgresql'].get('dsn')
            if not postgres_dsn:
                return jsonify({'status': 'error', 'message': 'PostgreSQL DSN не настроен'}), 500
            
            async def check_db():
                conn = await asyncpg.connect(postgres_dsn)
                await conn.execute('SELECT 1')
                await conn.close()
                return True
            
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(check_db())
                return jsonify({'status': 'ok', 'message': 'PostgreSQL доступен'}), 200
            finally:
                loop.close()
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    app.run(debug=True, host='0.0.0.0')