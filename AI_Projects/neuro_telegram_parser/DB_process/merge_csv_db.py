import pandas as pd
import psycopg2
import os
import sys
import glob
import logging
import csv
import json
from typing import Dict, Optional, List, Any, Union, Tuple
from psycopg2.extras import execute_values
from telegram_parser.config_utils import get_config

### --- ЛОГИРОВАНИЕ --- ###
def setup_logging() -> None:
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('tele_db.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

### --- ПОИСК CSV --- ###
def find_csv_files() -> Dict[str, Optional[str]]:
    """Поиск CSV файлов в директории скрипта"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_files = {
        'channels': None,
        'channel_descriptions': None,
        'enhanced_messages': None,
        'reactions_detailed': None,
        'comments_detailed': None
    }
    all_csv_files = glob.glob(os.path.join(script_dir, '*.csv'))
    
    for file in all_csv_files:
        filename_lower = os.path.basename(file).lower()
        if '_channels.csv' in filename_lower and 'description' not in filename_lower and 'merged' not in filename_lower:
            csv_files['channels'] = file
        elif '_channel_descriptions.csv' in filename_lower:
            csv_files['channel_descriptions'] = file
        elif 'enhanced_messages_with_stats' in filename_lower:
            csv_files['enhanced_messages'] = file
        elif '_reactions_detailed' in filename_lower:
            csv_files['reactions_detailed'] = file
        elif '_comments_detailed' in filename_lower:
            csv_files['comments_detailed'] = file
    
    return csv_files

### --- ЗАГРУЗКА CSV С БЕЗОПАСНОЙ КОДИРОВКОЙ --- ###
def load_csv_safely(file_path: str) -> Optional[pd.DataFrame]:
    """Загрузка CSV файла с определением правильной кодировки"""
    if not os.path.exists(file_path):
        logging.error(f"Файл {file_path} не найден")
        return None
    
    if 'comments_detailed' in file_path:
        return load_comments_file(file_path)
    
    encodings = ['utf-8', 'cp1251', 'latin-1']
    for encoding in encodings:
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            logging.info(f"Успешно загружен {os.path.basename(file_path)} с кодировкой {encoding}")
            return df
        except Exception as e:
            continue
    
    logging.error(f"Не удалось загрузить {file_path}")
    return pd.DataFrame()

def load_comments_file(file_path: str) -> pd.DataFrame:
    """Специальная обработка файла с комментариями"""
    columns = ['Channel_Name', 'Channel_ID', 'Message_ID', 'Message_Date',
               'Comment_Text', 'Comment_Author_ID', 'Comment_Date', 'Comment_Order']
    comments_df = pd.DataFrame(columns=columns)
    
    # Определение кодировки файла
    encoding_used = detect_file_encoding(file_path)
    if not encoding_used:
        logging.error(f"Не удалось определить кодировку {file_path}")
        return comments_df
    
    try:
        with open(file_path, 'r', encoding=encoding_used) as f:
            header_line = f.readline()
            records = []
            
            for line in f:
                if not line.strip():
                    continue
                try:
                    reader = csv.reader([line])
                    row = next(reader)
                    record = {
                        'Channel_Name': row[0] if len(row) > 0 else '',
                        'Channel_ID': row[1] if len(row) > 1 else '',
                        'Message_ID': row[2] if len(row) > 2 else '',
                        'Message_Date': row[3] if len(row) > 3 else '',
                        'Comment_Text': row[4] if len(row) > 4 else '',
                        'Comment_Author_ID': row[5] if len(row) > 5 else '',
                        'Comment_Date': row[6] if len(row) > 6 else '',
                        'Comment_Order': row[7] if len(row) > 7 else ''
                    }
                    records.append(record)
                except Exception as e:
                    continue
            
            if records:
                comments_df = pd.DataFrame(records)
        
        return comments_df
    except Exception as e:
        logging.error(f"Ошибка при чтении файла комментариев: {e}")
        return pd.DataFrame(columns=columns)

def detect_file_encoding(file_path: str) -> Optional[str]:
    """Определение кодировки файла"""
    encodings = ['utf-8', 'cp1251', 'latin-1']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.readline()
            return encoding
        except UnicodeDecodeError:
            continue
    return None

### --- CREATION OF FINAL TABLES --- ###
def create_channels_table(dataframes: Dict[str, Optional[pd.DataFrame]]) -> pd.DataFrame:
    """Создание итоговой таблицы каналов из разных источников"""
    channels_table = pd.DataFrame(columns=['ID', 'Folder_Title', 'Name', 'Description'])
    
    # Обработка данных из channels.csv
    if dataframes['channels'] is not None and not dataframes['channels'].empty \
        and all(col in dataframes['channels'].columns for col in ['Folder_Title', 'Chats_IDs']):
        channels_df = dataframes['channels'][['Folder_Title', 'Chats_IDs']].copy()
        channels_df.rename(columns={'Chats_IDs': 'ID'}, inplace=True)
        channels_df['ID'] = channels_df['ID'].astype(str)
        channels_table = pd.concat([channels_table, channels_df], ignore_index=True)
    
    # Обработка данных из channel_descriptions.csv
    if dataframes['descriptions'] is not None and not dataframes['descriptions'].empty \
        and all(c in dataframes['descriptions'].columns for c in ['Name', 'ID', 'Description']):
        process_channel_data(
            channels_table, 
            dataframes['descriptions'][['Name', 'ID', 'Description']].copy(),
            ['Name', 'Description']
        )
    
    # Обработка данных из enhanced_messages.csv
    if dataframes['messages'] is not None and not dataframes['messages'].empty \
        and all(col in dataframes['messages'].columns for col in ['Name', 'ID']):
        process_channel_data(
            channels_table, 
            dataframes['messages'][['Name', 'ID']].drop_duplicates().copy(),
            ['Name']
        )
    
    # Обработка данных из reactions_detailed.csv
    if dataframes['reactions'] is not None and not dataframes['reactions'].empty \
        and all(col in dataframes['reactions'].columns for col in ['Channel_Name', 'Channel_ID']):
        reactions_channels = dataframes['reactions'][['Channel_Name', 'Channel_ID']].drop_duplicates().copy()
        reactions_channels.rename(columns={'Channel_Name': 'Name', 'Channel_ID': 'ID'}, inplace=True)
        process_channel_data(channels_table, reactions_channels, ['Name'])
    
    # Обработка данных из comments_detailed.csv
    if dataframes['comments'] is not None and not dataframes['comments'].empty \
        and all(col in dataframes['comments'].columns for col in ['Channel_Name', 'Channel_ID']):
        comments_channels = dataframes['comments'][['Channel_Name', 'Channel_ID']].drop_duplicates().copy()
        comments_channels.rename(columns={'Channel_Name': 'Name', 'Channel_ID': 'ID'}, inplace=True)
        process_channel_data(channels_table, comments_channels, ['Name'])
    
    # Заполнение пустых значений и удаление дубликатов
    channels_table['Folder_Title'].fillna('Unknown', inplace=True)
    channels_table['Name'].fillna('', inplace=True)
    channels_table['Description'].fillna('', inplace=True)
    channels_table = channels_table.drop_duplicates(subset=['ID']).reset_index(drop=True)
    
    return channels_table

def process_channel_data(channels_table: pd.DataFrame, source_df: pd.DataFrame, fields: List[str]) -> None:
    """Обновление таблицы каналов данными из источника"""
    source_df['ID'] = source_df['ID'].astype(str)
    
    for _, row in source_df.iterrows():
        mask = channels_table['ID'] == row['ID']
        if mask.any():
            # Обновляем только если поля пустые
            for field in fields:
                if pd.isna(channels_table.loc[mask, field]).any() or channels_table.loc[mask, field].iloc[0] == '':
                    channels_table.loc[mask, field] = row[field]
        else:
            # Добавляем новую запись
            new_row = {'ID': row['ID'], 'Folder_Title': 'Unknown'}
            for field in fields:
                new_row[field] = row[field]
            # Добавляем отсутствующие поля со значениями по умолчанию
            for col in channels_table.columns:
                if col not in new_row:
                    new_row[col] = ''
            channels_table = pd.concat([channels_table, pd.DataFrame([new_row])], ignore_index=True)

def create_messages_table(dataframes: Dict[str, Optional[pd.DataFrame]]) -> pd.DataFrame:
    """Создание итоговой таблицы сообщений из разных источников"""
    messages_table = pd.DataFrame(columns=[
        'Message_ID', 'Original', 'Date', 'Content_Type', 'Views', 'Forwards',
        'Reactions', 'Reactions_Count', 'Total_Reactions', 'Comments',
        'Comments_Count', 'Replies_Count_Meta', 'Has_Comments_Support', 'Channel_ID',
        'Reaction_Emoji', 'Reaction_Count', 'Message_Date_Reactions',
        'Comment_Text', 'Comment_Author_ID', 'Comment_Date', 'Comment_Order', 'Message_Date_Comments'
    ])
    
    # Обработка данных из enhanced_messages.csv
    if dataframes['messages'] is not None and not dataframes['messages'].empty \
        and all(c in dataframes['messages'].columns for c in [
            'Message_ID','Original','Date','Content_Type','Views','Forwards','Reactions','Reactions_Count',
            'Total_Reactions','Comments','Comments_Count','Replies_Count_Meta','Has_Comments_Support','ID'
        ]):
        msgs_df = dataframes['messages'][[
            'Message_ID','Original','Date','Content_Type','Views','Forwards','Reactions','Reactions_Count',
            'Total_Reactions','Comments','Comments_Count','Replies_Count_Meta','Has_Comments_Support','ID'
        ]].copy()
        msgs_df.rename(columns={'ID':'Channel_ID'}, inplace=True)
        msgs_df['Message_ID'] = msgs_df['Message_ID'].astype(str)
        messages_table = pd.concat([messages_table, msgs_df], ignore_index=True)
    
    # Обработка данных из reactions_detailed.csv
    if dataframes['reactions'] is not None and not dataframes['reactions'].empty:
        process_reactions_data(messages_table, dataframes['reactions'])
    
    # Обработка данных из comments_detailed.csv
    if dataframes['comments'] is not None and not dataframes['comments'].empty:
        process_comments_data(messages_table, dataframes['comments'])
    
    # Удаление дубликатов
    messages_table = messages_table.drop_duplicates(subset=['Message_ID']).reset_index(drop=True)
    return messages_table

def process_reactions_data(messages_table: pd.DataFrame, reactions_df: pd.DataFrame) -> None:
    """Обработка данных о реакциях и добавление их в таблицу сообщений"""
    if reactions_df.empty or not all(col in reactions_df.columns for col in 
                                     ['Message_ID', 'Channel_ID', 'Reaction_Emoji', 'Reaction_Count', 'Message_Date']):
        return
    
    # Группировка реакций по Message_ID
    grouped_reactions = reactions_df.groupby('Message_ID').agg({
        'Channel_ID': 'first',
        'Reaction_Emoji': lambda x: list(x),
        'Reaction_Count': lambda x: list(x),
        'Message_Date': 'first'
    }).reset_index()
    
    # Добавление или обновление данных в таблице сообщений
    for _, row in grouped_reactions.iterrows():
        message_id = str(row['Message_ID'])
        mask = messages_table['Message_ID'] == message_id
        
        if mask.any():
            # Обновление существующей записи
            messages_table.loc[mask, 'Reaction_Emoji'] = str(row['Reaction_Emoji'])
            messages_table.loc[mask, 'Reaction_Count'] = str(row['Reaction_Count'])
            messages_table.loc[mask, 'Message_Date_Reactions'] = row['Message_Date']
            # Если Channel_ID не заполнен, заполняем его
            if pd.isna(messages_table.loc[mask, 'Channel_ID']).any():
                messages_table.loc[mask, 'Channel_ID'] = row['Channel_ID']
        else:
            # Добавление новой записи
            new_row = {
                'Message_ID': message_id,
                'Channel_ID': row['Channel_ID'],
                'Reaction_Emoji': str(row['Reaction_Emoji']),
                'Reaction_Count': str(row['Reaction_Count']),
                'Message_Date_Reactions': row['Message_Date']
            }
            # Заполнение остальных полей значениями по умолчанию
            for col in messages_table.columns:
                if col not in new_row:
                    new_row[col] = None
            messages_table = pd.concat([messages_table, pd.DataFrame([new_row])], ignore_index=True)

def process_comments_data(messages_table: pd.DataFrame, comments_df: pd.DataFrame) -> None:
    """Обработка данных о комментариях и добавление их в таблицу сообщений"""
    if comments_df.empty or not all(col in comments_df.columns for col in 
                                   ['Message_ID', 'Channel_ID', 'Comment_Text', 'Comment_Author_ID', 
                                    'Comment_Date', 'Comment_Order', 'Message_Date']):
        return
    
    # Группировка комментариев по Message_ID
    grouped_comments = comments_df.groupby('Message_ID').agg({
        'Channel_ID': 'first',
        'Comment_Text': lambda x: list(x),
        'Comment_Author_ID': lambda x: list(x),
        'Comment_Date': lambda x: list(x),
        'Comment_Order': lambda x: list(x),
        'Message_Date': 'first'
    }).reset_index()
    
    # Добавление или обновление данных в таблице сообщений
    for _, row in grouped_comments.iterrows():
        message_id = str(row['Message_ID'])
        mask = messages_table['Message_ID'] == message_id
        
        if mask.any():
            # Обновление существующей записи
            messages_table.loc[mask, 'Comment_Text'] = str(row['Comment_Text'])
            messages_table.loc[mask, 'Comment_Author_ID'] = str(row['Comment_Author_ID'])
            messages_table.loc[mask, 'Comment_Date'] = str(row['Comment_Date'])
            messages_table.loc[mask, 'Comment_Order'] = str(row['Comment_Order'])
            messages_table.loc[mask, 'Message_Date_Comments'] = row['Message_Date']
            # Если Channel_ID не заполнен, заполняем его
            if pd.isna(messages_table.loc[mask, 'Channel_ID']).any():
                messages_table.loc[mask, 'Channel_ID'] = row['Channel_ID']
        else:
            # Добавление новой записи
            new_row = {
                'Message_ID': message_id,
                'Channel_ID': row['Channel_ID'],
                'Comment_Text': str(row['Comment_Text']),
                'Comment_Author_ID': str(row['Comment_Author_ID']),
                'Comment_Date': str(row['Comment_Date']),
                'Comment_Order': str(row['Comment_Order']),
                'Message_Date_Comments': row['Message_Date']
            }
            # Заполнение остальных полей значениями по умолчанию
            for col in messages_table.columns:
                if col not in new_row:
                    new_row[col] = None
            messages_table = pd.concat([messages_table, pd.DataFrame([new_row])], ignore_index=True)

### --- DATABASE PART --- ###
def load_config() -> str:
    """Загрузка конфигурации подключения к базе данных"""
    config = get_config()
    if 'postgresql_customer' not in config or 'dsn' not in config['postgresql_customer']:
        logging.error("Нет секции [postgresql_customer] или dsn в config.ini.")
        sys.exit(1)
    return {
        'dsn': config['postgresql_customer']['dsn'],
        'display_dsn': config['postgresql_customer']['dsn'].split('@')[1] if '@' in config['postgresql_customer']['dsn'] else config['postgresql_customer']['dsn']
    }        
            

def sanitize_dsn(dsn_string: Union[str, bytes]) -> str:
    """Безопасное преобразование строки DSN"""
    try:
        if isinstance(dsn_string, bytes):
            dsn_string = dsn_string.decode('utf-8', errors='replace')
        dsn_string.encode('ascii', errors='replace').decode('ascii')
        return dsn_string
    except Exception:
        return ''.join([c if ord(c) < 128 else '_' for c in dsn_string])

def create_connection(postgres_dsn: str) -> psycopg2.extensions.connection:
    """Создание подключения к базе данных"""
    postgres_dsn = sanitize_dsn(postgres_dsn)
    try:
        return psycopg2.connect(postgres_dsn)
    except Exception as e:
        logging.error(f"Ошибка подключения: {e}")
        sys.exit(1)

def create_database(conn: psycopg2.extensions.connection, db_name: str = "telegram_data_customer") -> None:
    """Создание базы данных, если она не существует"""
    conn.autocommit = True  # Для создания базы данных нужен autocommit
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(f'CREATE DATABASE "{db_name}"')
            logging.info(f"База данных {db_name} успешно создана")
    except Exception as e:
        logging.error(f"Ошибка при создании базы: {e}")
        raise
    finally:
        cur.close()

def create_tables(conn: psycopg2.extensions.connection) -> None:
    """Создание таблиц в базе данных"""
    cur = conn.cursor()
    try:
        channels_sql = """
        CREATE TABLE IF NOT EXISTS channels (
            id BIGINT PRIMARY KEY,
            folder_title VARCHAR(255),
            name TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        messages_sql = """
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
        );
        """
        cur.execute(channels_sql)
        cur.execute(messages_sql)
        conn.commit()
        logging.info("Таблицы успешно созданы или уже существуют")
    except Exception as e:
        conn.rollback()
        logging.error(f"Ошибка при создании таблиц: {e}")
        raise
    finally:
        cur.close()

def safe_parse_json(value: Any) -> Optional[Any]:
    """Безопасное преобразование строки в JSON"""
    if pd.isna(value) or value == '[]' or value == '':
        return None
    try:
        if isinstance(value, str):
            value = value.replace("'", '"')
            return json.loads(value)
        return value
    except Exception as e:
        logging.warning(f"Ошибка при парсинге JSON: {e}, значение: {value}")
        return None

def safe_parse_list(value: Any) -> Optional[List]:
    """Безопасное преобразование строки в список"""
    if pd.isna(value) or value == '[]' or value == '':
        return None
    try:
        if isinstance(value, str):
            if value.startswith('[') and value.endswith(']'):
                # Безопасная альтернатива eval
                return json.loads(value.replace("'", '"'))
        return value
    except Exception as e:
        logging.warning(f"Ошибка при парсинге списка: {e}, значение: {value}")
        return None

def insert_channels_data(conn: psycopg2.extensions.connection, channels_df: pd.DataFrame) -> None:
    """Вставка данных о каналах в базу данных"""
    cur = conn.cursor()
    try:
        channels_data = []
        for _, row in channels_df.iterrows():
            try:
                channel_id = int(row['ID']) if pd.notna(row['ID']) and row['ID'] != '' else None
                if not channel_id:
                    continue
                channels_data.append((
                    channel_id,
                    str(row['Folder_Title']) if pd.notna(row['Folder_Title']) else None,
                    str(row['Name']) if pd.notna(row['Name']) else None,
                    str(row['Description']) if pd.notna(row['Description']) else None
                ))
            except Exception as e:
                logging.warning(f"Ошибка при обработке канала {row['ID']}: {e}")
                continue
        
        if not channels_data:
            logging.warning("Нет данных для вставки в таблицу channels")
            return
        
        insert_q = """
        INSERT INTO channels (id, folder_title, name, description)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
          folder_title = EXCLUDED.folder_title,
          name = EXCLUDED.name,
          description = EXCLUDED.description,
          updated_at = CURRENT_TIMESTAMP
        """
        execute_values(cur, insert_q, channels_data)
        conn.commit()
        logging.info(f"Вставлено/обновлено {len(channels_data)} записей в таблицу channels")
    except Exception as e:
        conn.rollback()
        logging.error(f"Ошибка при вставке данных о каналах: {e}")
        raise
    finally:
        cur.close()

def insert_messages_data(conn: psycopg2.extensions.connection, messages_df: pd.DataFrame) -> None:
    """Вставка данных о сообщениях в базу данных"""
    if messages_df.empty:
        logging.warning("Нет данных для вставки в таблицу messages")
        return
    
    cur = conn.cursor()
    try:
        messages_data = []
        batch_size = 1000  # Обработка по частям для больших датасетов
        
        for i in range(0, len(messages_df), batch_size):
            batch = messages_df.iloc[i:i+batch_size]
            
            for _, row in batch.iterrows():
                try:
                    message_id = int(row['Message_ID']) if pd.notna(row['Message_ID']) and row['Message_ID'] != '' else None
                    if not message_id:
                        continue
                    
                    channel_id = int(row['Channel_ID']) if 'Channel_ID' in row and pd.notna(row['Channel_ID']) and row['Channel_ID'] != '' else None
                    date = pd.to_datetime(row['Date']) if 'Date' in row and pd.notna(row['Date']) else None
                    
                    # Парсинг JSON и списков
                    reactions = safe_parse_json(row.get('Reactions'))
                    comments = safe_parse_json(row.get('Comments'))
                    reaction_emoji = safe_parse_list(row.get('Reaction_Emoji'))
                    reaction_count = safe_parse_list(row.get('Reaction_Count'))
                    comment_text = safe_parse_list(row.get('Comment_Text'))
                    comment_author_id = safe_parse_list(row.get('Comment_Author_ID'))
                    comment_date_list = safe_parse_list(row.get('Comment_Date'))
                    comment_order = safe_parse_list(row.get('Comment_Order'))
                    
                    # Преобразование дат реакций и комментариев
                    message_date_reactions = pd.to_datetime(row.get('Message_Date_Reactions')) if 'Message_Date_Reactions' in row and pd.notna(row.get('Message_Date_Reactions')) else None
                    message_date_comments = pd.to_datetime(row.get('Message_Date_Comments')) if 'Message_Date_Comments' in row and pd.notna(row.get('Message_Date_Comments')) else None
                    
                    messages_data.append((
                        message_id, 
                        channel_id,
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
                except Exception as e:
                    logging.warning(f"Ошибка при обработке сообщения {row.get('Message_ID', 'unknown')}: {e}")
                    continue
        
        if not messages_data:
            logging.warning("Нет данных для вставки в таблицу messages после обработки")
            return
        
        insert_q = """
        INSERT INTO messages (
            message_id, channel_id, original, date, content_type, views, forwards, reactions,
            reactions_count, total_reactions, comments, comments_count, replies_count_meta, has_comments_support,
            reaction_emoji, reaction_count, message_date_reactions, comment_text, comment_author_id,
            comment_date, comment_order, message_date_comments
        ) VALUES %s
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
        
        # Вставка данных пакетами для оптимизации
        batch_size = 500
        for i in range(0, len(messages_data), batch_size):
            batch = messages_data[i:i+batch_size]
            execute_values(cur, insert_q, batch)
            conn.commit()
            logging.info(f"Вставлено/обновлено {len(batch)} записей в таблицу messages (пакет {i//batch_size + 1})")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Ошибка при вставке данных о сообщениях: {e}")
        raise
    finally:
        cur.close()

def get_target_dsn(postgres_dsn: str, db_name: str = "telegram_data_customer") -> str:
    """Получение строки подключения к целевой базе данных"""
    if 'dbname=' in postgres_dsn.lower():
        # Для строки подключения в формате ключ=значение
        parts = []
        found_dbname = False
        for part in postgres_dsn.split():
            if part.lower().startswith('dbname='):
                parts.append(f"dbname={db_name}")
                found_dbname = True
            else:
                parts.append(part)
        if not found_dbname:
            parts.append(f"dbname={db_name}")
        return ' '.join(parts)
    elif '/' in postgres_dsn:
        # Для URI формата
        base_uri = postgres_dsn.split('/')[0]
        if '@' in base_uri:
            # postgresql://user:password@host:port/dbname
            return f"{base_uri}/{db_name}"
        else:
            # Другие форматы URI
            parts = postgres_dsn.split('/')
            return '/'.join(parts[:-1] + [db_name])
    else:
        # Добавляем базу данных в конец
        return f"{postgres_dsn}/{db_name}"

### --- ОСНОВНОЙ MAIN --- ###
def main() -> None:
    """Основная функция программы"""
    setup_logging()
    logging.info("=== Начало загрузки данных в PostgreSQL ===")
    
    try:
        # Поиск и загрузка CSV файлов
        csv_files = find_csv_files()
        dataframes = {
            'channels': load_csv_safely(csv_files['channels']) if csv_files['channels'] else None,
            'descriptions': load_csv_safely(csv_files['channel_descriptions']) if csv_files['channel_descriptions'] else None,
            'messages': load_csv_safely(csv_files['enhanced_messages']) if csv_files['enhanced_messages'] else None,
            'reactions': load_csv_safely(csv_files['reactions_detailed']) if csv_files['reactions_detailed'] else None,
            'comments': load_csv_safely(csv_files['comments_detailed']) if csv_files['comments_detailed'] else None,
        }
        
        # Создание итоговых таблиц
        channels_table = create_channels_table(dataframes)
        messages_table = create_messages_table(dataframes)
        
        # Загрузка конфигурации
        config = load_config()
        postgres_dsn = config['dsn']
        
        # Подключение к базе PostgreSQL и создание новой базы данных
        conn = create_connection(postgres_dsn)
        db_name = "telegram_data_customer"  # Используем то же имя базы, что и в init_db.py
        create_database(conn, db_name)
        conn.close()
        
        # Подключение к созданной базе данных
        target_dsn = get_target_dsn(postgres_dsn, db_name)
        conn = create_connection(target_dsn)
        
        # Создание таблиц и вставка данных
        create_tables(conn)
        
        # Использование транзакций для вставки данных
        try:
            conn.autocommit = False
            insert_channels_data(conn, channels_table)
            insert_messages_data(conn, messages_table)
            conn.commit()
            logging.info(f"Каналов {len(channels_table)}, сообщений {len(messages_table)} успешно загружены в БД!")
        except Exception as e:
            conn.rollback()
            logging.error(f"Ошибка при вставке данных: {e}")
            raise
        finally:
            conn.close()
            
    except Exception as e:
        logging.error(f"Ошибка: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()