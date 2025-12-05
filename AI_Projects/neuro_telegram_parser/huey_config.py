# huey_config.py
import os
import configparser
from huey import RedisHuey
from config_utils import get_config 

config = get_config()

# Получаем конфигурацию для подключения к Redis
config = get_config()
REDIS_HOST = config['redis']['host']
REDIS_PORT = int(config['redis']['port'])
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
REDIS_DB = int(config['redis'].get('db', 0))

# Создаем экземпляр Huey с подключением к Redis
huey_kwargs = {
    'host': REDIS_HOST,
    'port': REDIS_PORT,
    'db': REDIS_DB,
    'immediate': False,
    'utc': True
}

# Добавляем пароль, если он указан
if REDIS_PASSWORD:
    huey_kwargs['password'] = REDIS_PASSWORD

huey = RedisHuey('telegram-parser', **huey_kwargs)

print(f"Huey initialized with Redis at {REDIS_HOST}:{REDIS_PORT}")