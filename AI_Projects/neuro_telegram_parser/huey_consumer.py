import os
import sys
import logging
from huey.consumer import Consumer
from dotenv import load_dotenv
load_dotenv()

# Добавляем путь к проекту
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('huey_consumer.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Глобальный клиент Telegram для всех задач
telegram_client = None

def initialize_telegram_client():
    """Инициализирует глобальный клиент Telegram для всех задач"""
    global telegram_client
    
    try:
        # Импорт конфигурации
        from config_utils import get_config
        config = get_config()
        
        API_ID = int(config['telegram']['api_id'])
        API_HASH = config['telegram']['api_hash']
        PHONE_NUMBER = config['telegram'].get('phone_number', '')
        
        # Создание основной сессии для воркера
        logger.info("📱 Инициализация общего Telegram клиента для воркера...")
        
        # Используем основную сессию вместо создания новой
        session_name = "telegram_parser"
        
        logger.info("🔄 Проверяем существование файла сессии...")
        session_file = f"{session_name}.session"
        if not os.path.exists(session_file):
            logger.error(f"❌ Файл сессии {session_file} не найден! Запустите setup_main_session.py")
            return False
            
        logger.info(f"✅ Файл сессии {session_file} найден")
        
        # Вместо создания и тестирования клиента здесь, мы просто сохраняем параметры
        # Реальный клиент будет создаваться в задачах через TelegramClientManager
        logger.info("✅ Параметры для Telegram клиента успешно сохранены")
        return True
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при инициализации Telegram клиента: {e}")
        import traceback
        logger.error(f"📍 Трассировка: {traceback.format_exc()}")
        return False

def shutdown_telegram_client():
    """Останавливает Telegram клиент при завершении работы"""
    global telegram_client
    
    # В новой реализации нам не нужно останавливать клиент здесь,
    # так как он будет создаваться и останавливаться в каждой задаче
    logger.info("✅ Завершение работы Telegram клиента не требуется (клиенты управляются в задачах)")

try:
    # Импорт конфигурации Huey
    from huey_config import huey
    logger.info("✅ Huey конфигурация успешно импортирована")
    
    # Инициализация Telegram клиента перед импортом задач
    logger.info("🚀 Инициализация Telegram клиента...")
    client_initialized = initialize_telegram_client()
    
    if client_initialized:
        logger.info("✅ Telegram клиент успешно инициализирован")
    else:
        logger.warning("⚠️ Не удалось инициализировать Telegram клиент. Задачи могут работать некорректно.")
    
    # Импорт всех задач (это важно!)
    import tasks
    
    # Устанавливаем глобальный клиент в модуле tasks
    # Теперь tasks будет использовать TelegramClientManager вместо глобального клиента
    logger.info("✅ Задачи успешно импортированы")
    
    # Проверка доступных команд
    # Адаптируем код для работы с объектом Registry
    try:
        # Пробуем получить список задач разными способами
        if hasattr(huey, '_registry') and hasattr(huey._registry, 'tasks'):
            available_commands = list(huey._registry.tasks.keys())
        elif hasattr(huey, '_registry') and hasattr(huey._registry, '_registry'):
            available_commands = list(huey._registry._registry.keys())
        elif hasattr(huey, 'tasks'):
            available_commands = list(huey.tasks.keys())
        elif hasattr(huey, '_tasks'):
            available_commands = list(huey._tasks.keys())
        else:
            # Если не удалось получить список задач, просто продолжаем без этой проверки
            logger.warning("⚠️ Не удалось получить список задач. Структура Huey изменилась.")
            available_commands = ["<не удалось определить>"]
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при получении списка задач: {e}")
        available_commands = ["<не удалось определить>"]
    
    logger.info(f"📋 Доступные команды ({len(available_commands)}):")
    for cmd in available_commands:
        logger.info(f"   + {cmd}")
    
    if not available_commands or available_commands == ["<не удалось определить>"]:
        logger.warning("⚠️ Не удалось определить список команд. Продолжаем работу.")
    
    # Регистрация функции для выполнения при завершении работы
    import atexit
    atexit.register(shutdown_telegram_client)
    
    # Создание и запуск consumer
    logger.info("🚀 Запуск Huey Consumer...")
    
    consumer = Consumer(
        huey=huey, 
        workers=1,  
        worker_type='thread',
        max_delay=10.0,
        initial_delay=0.1,
        backoff=1.15
    )
    
    logger.info("✅ Huey Consumer инициализирован")
    logger.info(f"   👷 Воркеров: 1")
    logger.info(f"   📊 Максимальная задержка: 10.0 сек")
    
    # Запуск consumer
    consumer.run()
    
except ImportError as e:
    logger.error(f"❌ Ошибка импорта: {e}")
    logger.error("Проверьте структуру проекта и пути импорта")
    sys.exit(1)
except Exception as e:
    logger.error(f"❌ Критическая ошибка: {e}")
    import traceback
    logger.error(f"📍 Трассировка: {traceback.format_exc()}")
    sys.exit(1)

if __name__ == '__main__':
    logger.info("🎯 Запуск huey_consumer.py как главного модуля")
    print("Huey Consumer запущен. Для остановки нажмите Ctrl+C")
    try:
        pass  # Consumer уже запущен выше
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
        print("\nHuey Consumer остановлен")
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)