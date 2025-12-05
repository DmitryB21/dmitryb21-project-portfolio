import psycopg2
import pandas as pd
import os
import sys
import logging
from psycopg2.extras import execute_values
import json
from telegram_parser.config_utils import get_config

def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('init_db_customer.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def load_config():
    """Загрузка конфигурации с использованием config_utils"""
    # Используем функцию get_config() из config_utils.py для получения конфигурации
    config = get_config()
    
    # Проверка наличия необходимых настроек для customer базы данных
    if 'postgresql_customer' not in config or 'dsn' not in config['postgresql_customer']:
        logging.error("В файле config.ini отсутствует секция [postgresql_customer] или параметр dsn.")
        logging.error("Пожалуйста, убедитесь, что файл содержит правильные настройки.")
        sys.exit(1)
        
    POSTGRES_CUSTOMER_DSN = config['postgresql_customer']['dsn']
    logging.info("Конфигурация успешно загружена")
    return POSTGRES_CUSTOMER_DSN

def sanitize_dsn(dsn_string):
    """Очистка и нормализация строки подключения к базе данных"""
    if not isinstance(dsn_string, str):
        try:
            dsn_string = str(dsn_string)
        except Exception as e:
            logging.error(f"Невозможно преобразовать DSN в строку: {e}")
            sys.exit(1)
    
    # Попытка исправить проблемы с кодировкой
    try:
        # Если строка уже в байтах, декодируем ее
        if isinstance(dsn_string, bytes):
            dsn_string = dsn_string.decode('utf-8', errors='replace')
        
        # Проверяем, что строка содержит только ASCII символы
        dsn_string.encode('ascii', errors='replace').decode('ascii')
    except Exception as e:
        logging.warning(f"Проблема с кодировкой DSN: {e}")
        # Попытка очистить строку от проблемных символов
        clean_dsn = ""
        for char in dsn_string:
            try:
                char.encode('ascii')
                clean_dsn += char
            except UnicodeEncodeError:
                clean_dsn += '_'  # Заменяем проблемные символы на подчеркивание
        dsn_string = clean_dsn
        logging.info("DSN был очищен от проблемных символов")
    
    return dsn_string

def create_connection(POSTGRES_DSN):
    """Создание подключения к базе данных"""
    try:
        # Очищаем строку подключения от проблемных символов
        POSTGRES_DSN = sanitize_dsn(POSTGRES_DSN)
        
        # Скрываем пароль при выводе строки подключения
        display_dsn = POSTGRES_DSN.split('@')[1] if '@' in POSTGRES_DSN else POSTGRES_DSN
        print(f"Подключение к PostgreSQL: {display_dsn}")
        
        # Используем параметры подключения вместо строки DSN
        if '@' in POSTGRES_DSN and '://' in POSTGRES_DSN:
            # Формат URI: postgresql://user:pass@host:port/dbname
            try:
                import urllib.parse
                parts = urllib.parse.urlparse(POSTGRES_DSN)
                username = parts.username
                password = parts.password
                hostname = parts.hostname
                port = parts.port or 5432
                database = parts.path.lstrip('/')
                
                conn = psycopg2.connect(
                    host=hostname,
                    port=port,
                    user=username,
                    password=password,
                    dbname=database if database else 'postgres'
                )
            except Exception as e:
                logging.error(f"Ошибка при разборе URI DSN: {e}")
                # Пробуем прямое подключение как запасной вариант
                conn = psycopg2.connect(POSTGRES_DSN)
        else:
            # Прямое подключение с использованием строки DSN
            conn = psycopg2.connect(POSTGRES_DSN)
            
        conn.autocommit = True
        logging.info("Подключение к базе данных установлено")
        return conn
    except psycopg2.Error as e:
        logging.error(f"Ошибка подключения к базе данных: {e}")
        sys.exit(1)

def create_database(conn, db_name="telegram_data_customer"):
    """Создание базы данных telegram_data_customer"""
    cursor = conn.cursor()

    try:
        # Проверка существования базы данных
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (db_name,))
        exists = cursor.fetchone()

        if not exists:
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            logging.info(f"База данных {db_name} создана")
        else:
            logging.info(f"База данных {db_name} уже существует")

    except psycopg2.Error as e:
        logging.error(f"Ошибка при создании базы данных: {e}")
        raise
    finally:
        cursor.close()

def create_tables(conn):
    """Создание таблиц channels и messages"""
    cursor = conn.cursor()

    try:
        # Создание таблицы channels
        create_channels_table = """
        CREATE TABLE IF NOT EXISTS channels (
            id BIGINT PRIMARY KEY,
            folder_title VARCHAR(255),
            name TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        # Создание таблицы messages с добавлением channel_id для связи с таблицей channels
        create_messages_table = """
        CREATE TABLE IF NOT EXISTS messages (
            message_id BIGINT PRIMARY KEY,
            channel_id BIGINT,
            original TEXT,
            date TIMESTAMP WITH TIME ZONE,
            content_type VARCHAR(50),
            views INTEGER,
            forwards INTEGER,
            reactions JSONB,
            reactions_count INTEGER,
            total_reactions INTEGER,
            comments JSONB,
            comments_count INTEGER,
            replies_count_meta INTEGER,
            has_comments_support BOOLEAN,
            reaction_emoji TEXT[],
            reaction_count INTEGER[],
            message_date_reactions TIMESTAMP WITH TIME ZONE,
            comment_text TEXT[],
            comment_author_id BIGINT[],
            comment_date TIMESTAMP WITH TIME ZONE[],
            comment_order INTEGER[],
            message_date_comments TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (channel_id) REFERENCES channels(id)
        )
        """

        cursor.execute(create_channels_table)
        cursor.execute(create_messages_table)

        logging.info("Таблицы channels и messages созданы")

        # Создание индексов для оптимизации
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_channels_name ON channels(name)",
            "CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date)",
            "CREATE INDEX IF NOT EXISTS idx_messages_content_type ON messages(content_type)",
            "CREATE INDEX IF NOT EXISTS idx_messages_views ON messages(views)",
            "CREATE INDEX IF NOT EXISTS idx_messages_channel_id ON messages(channel_id)"
        ]

        for index in indexes:
            cursor.execute(index)

        logging.info("Индексы созданы")

    except psycopg2.Error as e:
        logging.error(f"Ошибка при создании таблиц: {e}")
        raise
    finally:
        cursor.close()

def load_csv_data(script_dir):
    """Загрузка данных из CSV файлов"""
    # Ищем CSV файлы в директории скрипта и в родительской директории
    possible_dirs = [
        script_dir,
        os.path.dirname(script_dir),
        os.path.dirname(os.path.dirname(script_dir))  # Добавляем еще один уровень поиска
    ]
    
    channels_file = None
    messages_file = None
    
    for directory in possible_dirs:
        channels_path = os.path.join(directory, 'merged_channels.csv')
        messages_path = os.path.join(directory, 'merged_messages.csv')
        
        if os.path.exists(channels_path):
            channels_file = channels_path
        if os.path.exists(messages_path):
            messages_file = messages_path
        
        if channels_file and messages_file:
            break
    
    if not channels_file:
        logging.error(f"Файл merged_channels.csv не найден. Сначала запустите merge_csv_files.py")
        sys.exit(1)

    if not messages_file:
        logging.error(f"Файл merged_messages.csv не найден. Сначала запустите merge_csv_files.py")
        sys.exit(1)

    logging.info(f"Используются файлы: {channels_file}, {messages_file}")

    try:
        channels_df = pd.read_csv(channels_file, encoding='utf-8')
        messages_df = pd.read_csv(messages_file, encoding='utf-8')

        logging.info(f"Загружено {len(channels_df)} каналов и {len(messages_df)} сообщений")
        return channels_df, messages_df

    except Exception as e:
        logging.error(f"Ошибка при загрузке CSV файлов: {e}")
        sys.exit(1)

def insert_channels_data(conn, channels_df):
    """Вставка данных в таблицу channels"""
    cursor = conn.cursor()

    try:
        # Подготовка данных
        channels_data = []
        for _, row in channels_df.iterrows():
            try:
                # Преобразуем ID в целое число
                channel_id = int(row['ID']) if pd.notna(row['ID']) and row['ID'] != '' else None
                
                if channel_id is None:
                    logging.warning(f"Пропуск записи с пустым ID: {row}")
                    continue
                
                channels_data.append((
                    channel_id,
                    str(row['Folder_Title']) if pd.notna(row['Folder_Title']) else None,
                    str(row['Name']) if pd.notna(row['Name']) else None,
                    str(row['Description']) if pd.notna(row['Description']) else None
                ))
            except (ValueError, TypeError) as e:
                logging.warning(f"Ошибка при обработке записи канала: {row}. Ошибка: {e}")
                continue

        if not channels_data:
            logging.warning("Нет данных для вставки в таблицу channels")
            return

        # Вставка данных
        insert_query = """
        INSERT INTO channels (id, folder_title, name, description) 
        VALUES %s 
        ON CONFLICT (id) DO UPDATE SET
            folder_title = EXCLUDED.folder_title,
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            updated_at = CURRENT_TIMESTAMP
        """

        execute_values(cursor, insert_query, channels_data, template=None, page_size=1000)

        logging.info(f"Вставлено {len(channels_data)} записей в таблицу channels")

    except Exception as e:
        logging.error(f"Ошибка при вставке данных в таблицу channels: {e}")
        raise
    finally:
        cursor.close()

def safe_eval_json(value):
    """Безопасное преобразование строки в JSON"""
    if pd.isna(value) or value == '[]' or value == '':
        return None
    try:
        if isinstance(value, str):
            # Замена одинарных кавычек на двойные для корректного JSON
            value = value.replace("'", '"')
            return json.loads(value)
        return value
    except:
        return None

def safe_eval_list(value):
    """Безопасное преобразование строки в список"""
    if pd.isna(value) or value == '[]' or value == '':
        return None
    try:
        if isinstance(value, str):
            return eval(value)
        return value
    except:
        return None

def insert_messages_data(conn, messages_df):
    """Вставка данных в таблицу messages"""
    cursor = conn.cursor()

    try:
        # Подготовка данных
        messages_data = []
        for _, row in messages_df.iterrows():
            try:
                # Обработка Message_ID
                message_id = int(row['Message_ID']) if pd.notna(row['Message_ID']) and row['Message_ID'] != '' else None
                
                if message_id is None:
                    logging.warning(f"Пропуск записи с пустым Message_ID: {row}")
                    continue
                
                # Обработка Channel_ID
                channel_id = int(row['Channel_ID']) if 'Channel_ID' in row and pd.notna(row['Channel_ID']) and row['Channel_ID'] != '' else None
                
                # Обработка дат
                date = pd.to_datetime(row['Date']) if pd.notna(row['Date']) else None
                message_date_reactions = pd.to_datetime(row['Date_reactions']) if 'Date_reactions' in row and pd.notna(row['Date_reactions']) else None
                message_date_comments = pd.to_datetime(row['Message_Date']) if 'Message_Date' in row and pd.notna(row['Message_Date']) else None

                # Обработка JSON полей
                reactions = safe_eval_json(row['Reactions']) if 'Reactions' in row else None
                comments = safe_eval_json(row['Comments']) if 'Comments' in row else None

                # Обработка списков
                reaction_emoji = safe_eval_list(row['Reaction_Emoji']) if 'Reaction_Emoji' in row else None
                reaction_count = safe_eval_list(row['Reaction_Count']) if 'Reaction_Count' in row else None
                comment_text = safe_eval_list(row['Comment_Text']) if 'Comment_Text' in row else None
                comment_author_id = safe_eval_list(row['Comment_Author_ID']) if 'Comment_Author_ID' in row else None
                comment_date_list = None
                if 'Comment_Date' in row and pd.notna(row['Comment_Date']):
                    comment_date_raw = safe_eval_list(row['Comment_Date'])
                    if comment_date_raw:
                        comment_date_list = [pd.to_datetime(d) if pd.notna(d) else None for d in comment_date_raw]
                comment_order = safe_eval_list(row['Comment_Order']) if 'Comment_Order' in row else None

                messages_data.append((
                    message_id,
                    channel_id,  # Добавляем channel_id для связи с таблицей channels
                    str(row['Original']) if 'Original' in row and pd.notna(row['Original']) else None,
                    date,
                    str(row['Content_Type']) if 'Content_Type' in row and pd.notna(row['Content_Type']) else None,
                    int(row['Views']) if 'Views' in row and pd.notna(row['Views']) and row['Views'] != '' else None,
                    int(row['Forwards']) if 'Forwards' in row and pd.notna(row['Forwards']) and row['Forwards'] != '' else None,
                    reactions,
                    int(row['Reactions_Count']) if 'Reactions_Count' in row and pd.notna(row['Reactions_Count']) and row['Reactions_Count'] != '' else None,
                    int(row['Total_Reactions']) if 'Total_Reactions' in row and pd.notna(row['Total_Reactions']) and row['Total_Reactions'] != '' else None,
                    comments,
                    int(row['Comments_Count']) if 'Comments_Count' in row and pd.notna(row['Comments_Count']) and row['Comments_Count'] != '' else None,
                    int(row['Replies_Count_Meta']) if 'Replies_Count_Meta' in row and pd.notna(row['Replies_Count_Meta']) and row['Replies_Count_Meta'] != '' else None,
                    bool(row['Has_Comments_Support']) if 'Has_Comments_Support' in row and pd.notna(row['Has_Comments_Support']) else None,
                    reaction_emoji,
                    reaction_count,
                    message_date_reactions,
                    comment_text,
                    comment_author_id,
                    comment_date_list,
                    comment_order,
                    message_date_comments
                ))
            except (ValueError, TypeError) as e:
                logging.warning(f"Ошибка при обработке записи сообщения: {row}. Ошибка: {e}")
                continue

        if not messages_data:
            logging.warning("Нет данных для вставки в таблицу messages")
            return

        # Вставка данных
        insert_query = """
        INSERT INTO messages (
            message_id, channel_id, original, date, content_type, views, forwards,
            reactions, reactions_count, total_reactions, comments,
            comments_count, replies_count_meta, has_comments_support,
            reaction_emoji, reaction_count, message_date_reactions,
            comment_text, comment_author_id, comment_date, comment_order,
            message_date_comments
        ) 
        VALUES %s 
        ON CONFLICT (message_id) DO UPDATE SET
            channel_id = EXCLUDED.channel_id,
            original = EXCLUDED.original,
            date = EXCLUDED.date,
            content_type = EXCLUDED.content_type,
            views = EXCLUDED.views,
            forwards = EXCLUDED.forwards,
            reactions = EXCLUDED.reactions,
            reactions_count = EXCLUDED.reactions_count,
            total_reactions = EXCLUDED.total_reactions,
            comments = EXCLUDED.comments,
            comments_count = EXCLUDED.comments_count,
            replies_count_meta = EXCLUDED.replies_count_meta,
            has_comments_support = EXCLUDED.has_comments_support,
            reaction_emoji = EXCLUDED.reaction_emoji,
            reaction_count = EXCLUDED.reaction_count,
            message_date_reactions = EXCLUDED.message_date_reactions,
            comment_text = EXCLUDED.comment_text,
            comment_author_id = EXCLUDED.comment_author_id,
            comment_date = EXCLUDED.comment_date,
            comment_order = EXCLUDED.comment_order,
            message_date_comments = EXCLUDED.message_date_comments,
            updated_at = CURRENT_TIMESTAMP
        """

        execute_values(cursor, insert_query, messages_data, template=None, page_size=1000)

        logging.info(f"Вставлено {len(messages_data)} записей в таблицу messages")

    except Exception as e:
        logging.error(f"Ошибка при вставке данных в таблицу messages: {e}")
        raise
    finally:
        cursor.close()

def main():
    """Основная функция"""
    setup_logging()
    logging.info("Начало инициализации базы данных telegram_data_customer...")

    try:
        # Получаем директорию, в которой находится скрипт
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Загрузка конфигурации
        postgres_dsn = load_config()
        
        # Выводим DSN для отладки (скрывая пароль)
        display_dsn = postgres_dsn.split('@')[1] if '@' in postgres_dsn else postgres_dsn
        logging.info(f"Полученный DSN: {display_dsn}")
        
        # Создание подключения к PostgreSQL (к базе по умолчанию)
        conn = create_connection(postgres_dsn)

        # Создание базы данных telegram_data_customer
        create_database(conn)
        conn.close()

        # Подключение к созданной базе данных
        # Изменяем DSN для подключения к нашей БД
        target_dsn = postgres_dsn
        if 'dbname=' not in target_dsn.lower() and '/' not in target_dsn.split('@')[-1]:
            # Если DSN в формате URI (postgresql://user:pass@host:port)
            if target_dsn.endswith('/'):
                target_dsn += 'telegram_data_customer'
            else:
                target_dsn += '/telegram_data_customer'
        elif 'dbname=' in target_dsn.lower():
            # Если DSN в формате ключ-значение (host=localhost port=5432 dbname=postgres)
            import re
            target_dsn = re.sub(r'dbname=\w+', 'dbname=telegram_data_customer', target_dsn)

        conn = create_connection(target_dsn)

        # Создание таблиц
        create_tables(conn)

        # Загрузка данных из CSV
        channels_df, messages_df = load_csv_data(script_dir)

        # Вставка данных
        insert_channels_data(conn, channels_df)
        insert_messages_data(conn, messages_df)

        logging.info("Инициализация базы данных завершена успешно!")
        print("\nБаза данных telegram_data_customer успешно создана и заполнена!")
        print(f"Каналов: {len(channels_df)}")
        print(f"Сообщений: {len(messages_df)}")

    except Exception as e:
        logging.error(f"Ошибка при инициализации базы данных: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)
    finally:
        if 'conn' in locals() and conn is not None:
            conn.close()

if __name__ == "__main__":
    main()