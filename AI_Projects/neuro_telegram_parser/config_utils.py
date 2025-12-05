"""
Модуль для работы с конфигурацией приложения.
Поддерживает чтение значений из config.ini и переменных окружения.
"""
import os
import configparser
from dotenv import load_dotenv, dotenv_values

# Гарантированно загружаем .env из корня проекта и по умолчанию из CWD
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)

# Пробуем несколько путей для .env файла (сначала текущая директория, потом родительская)
_env_paths = [
    os.path.join(_current_dir, '.env'),  # Текущая директория модуля (telegram_parser/.env)
    os.path.join(_project_root, '.env'),  # Родительская директория (PythonProject/.env)
    os.path.join(os.getcwd(), '.env'),    # Рабочая директория
]

_env_path = None
for path in _env_paths:
    if os.path.exists(path):
        _env_path = path
        load_dotenv(dotenv_path=path, override=True)
        break

# Дополнительно пробуем стандартный поиск (CWD и выше)
if not _env_path:
    load_dotenv()
    _env_path = os.path.join(os.getcwd(), '.env')

_raw_env_values = dotenv_values(_env_path) if _env_path and os.path.exists(_env_path) else {}
# Удаляем возможный BOM у первого ключа (Windows UTF-8 BOM)
_env_file_values = { (k.lstrip('\ufeff') if isinstance(k, str) else k): v for k, v in _raw_env_values.items() }

def get_config():
    """
    Читает и возвращает объект конфигурации.
    Поддерживает чтение значений из переменных окружения, если значение в config.ini
    начинается с 'ENV:'.
    """
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
    config.read(config_path)
    
    # Обрабатываем значения, которые должны быть взяты из переменных окружения
    for section in config.sections():
        for key in config[section]:
            value = config[section][key]
            if value is None:
                continue
            value_stripped = value.strip().strip('"').strip("'")
            if value_stripped.startswith('ENV:'):
                env_var = value_stripped.split('ENV:')[1].strip()
                env_value = os.environ.get(env_var)
                if env_value is None or env_value == "":
                    # Fallback: читаем прямо из файла .env
                    file_value = _env_file_values.get(env_var)
                    if file_value is not None and file_value != "":
                        config[section][key] = file_value
                    else:
                        print(f"Предупреждение: Переменная окружения {env_var} не найдена")
                else:
                    config[section][key] = env_value
    
    return config