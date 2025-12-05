import pandas as pd
import os
import glob
import sys
import logging
import csv

def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('csv_merger.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def find_csv_files():
    """Поиск CSV файлов в директории скрипта"""
    # Получаем директорию, в которой находится скрипт
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    csv_files = {
        'channels': None,
        'channel_descriptions': None,
        'enhanced_messages': None,
        'reactions_detailed': None,
        'comments_detailed': None
    }

    # Поиск всех CSV файлов в директории скрипта
    all_csv_files = glob.glob(os.path.join(script_dir, '*.csv'))
    
    logging.info(f"Поиск CSV файлов в директории: {script_dir}")
    logging.info(f"Найдено CSV файлов: {len(all_csv_files)}")
    
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

def load_csv_safely(file_path):
    """Безопасная загрузка CSV файла с различными параметрами"""
    if not os.path.exists(file_path):
        logging.error(f"Файл {file_path} не найден")
        return None
    
    # Если это файл комментариев, используем специальный подход сразу
    if 'comments_detailed' in file_path:
        return load_comments_file(file_path)
    
    # Определяем кодировку файла
    encodings = ['utf-8', 'cp1251', 'latin-1']
    for encoding in encodings:
        try:
            # Пробуем прочитать файл с текущей кодировкой
            with open(file_path, 'r', encoding=encoding) as f:
                # Читаем первые несколько строк для анализа
                sample_lines = [next(f) for _ in range(5) if f]
                break
        except UnicodeDecodeError:
            continue
        except StopIteration:
            # Файл слишком короткий
            sample_lines = []
            break
    
    # Выводим первые строки для отладки
    logging.info(f"Анализ файла {os.path.basename(file_path)}:")
    for i, line in enumerate(sample_lines[:3]):
        logging.info(f"Строка {i+1}: {line.strip()}")
    
    # Пробуем различные комбинации параметров для чтения CSV
    for encoding in encodings:
        try:
            # Стандартный способ чтения CSV
            df = pd.read_csv(file_path, encoding=encoding)
            logging.info(f"Успешно загружен файл {os.path.basename(file_path)} с кодировкой {encoding}")
            return df
        except Exception as e1:
            logging.debug(f"Не удалось загрузить с обычными параметрами: {str(e1)}")
            
            try:
                # Пробуем с экранированием кавычек
                df = pd.read_csv(file_path, encoding=encoding, escapechar='\\', quoting=csv.QUOTE_NONE)
                logging.info(f"Успешно загружен файл {os.path.basename(file_path)} с экранированием кавычек")
                return df
            except Exception as e2:
                logging.debug(f"Не удалось загрузить с экранированием кавычек: {str(e2)}")
                
                try:
                    # Пробуем с игнорированием ошибок
                    df = pd.read_csv(file_path, encoding=encoding, error_bad_lines=False, warn_bad_lines=True)
                    logging.info(f"Успешно загружен файл {os.path.basename(file_path)} с игнорированием ошибок")
                    return df
                except Exception as e3:
                    logging.debug(f"Не удалось загрузить с игнорированием ошибок: {str(e3)}")
    
    logging.error(f"Не удалось загрузить файл {file_path}")
    return pd.DataFrame()  # Возвращаем пустой DataFrame

def load_comments_file(file_path):
    """Специальная функция для загрузки файла комментариев"""
    logging.info(f"Загрузка файла комментариев {os.path.basename(file_path)} специальным методом...")
    
    # Создаем пустой DataFrame с нужными столбцами
    columns = ['Channel_Name', 'Channel_ID', 'Message_ID', 'Message_Date', 
              'Comment_Text', 'Comment_Author_ID', 'Comment_Date', 'Comment_Order']
    comments_df = pd.DataFrame(columns=columns)
    
    # Пробуем разные кодировки
    encodings = ['utf-8', 'cp1251', 'latin-1']
    encoding_used = None
    
    for encoding in encodings:
        try:
            # Проверяем, что файл можно открыть с этой кодировкой
            with open(file_path, 'r', encoding=encoding) as f:
                f.readline()
                encoding_used = encoding
                break
        except UnicodeDecodeError:
            continue
    
    if encoding_used is None:
        logging.error(f"Не удалось определить кодировку для файла {file_path}")
        return comments_df
    
    try:
        # Читаем файл построчно с ограничением количества строк для безопасности
        max_rows = 10000  # Ограничиваем количество строк для обработки
        row_count = 0
        
        with open(file_path, 'r', encoding=encoding_used) as f:
            # Пропускаем первую строку (заголовок)
            header_line = f.readline().strip()
            
            # Если первая строка пустая, читаем следующую
            if not header_line:
                header_line = f.readline().strip()
            
            # Обрабатываем строки данных
            for line in f:
                if row_count >= max_rows:
                    logging.warning(f"Достигнут лимит в {max_rows} строк при обработке файла комментариев")
                    break
                
                if not line.strip():
                    continue  # Пропускаем пустые строки
                
                # Разбиваем строку по запятым, учитывая кавычки
                try:
                    # Используем csv.reader для корректной обработки кавычек
                    reader = csv.reader([line])
                    row = next(reader)
                    
                    # Проверяем, что строка содержит достаточно элементов
                    if len(row) >= 7:  # Минимум 7 столбцов нужно
                        # Формируем запись для DataFrame
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
                        
                        # Добавляем запись в DataFrame
                        comments_df = pd.concat([comments_df, pd.DataFrame([record])], ignore_index=True)
                        row_count += 1
                except Exception as e:
                    logging.debug(f"Ошибка при обработке строки: {str(e)}")
                    continue
        
        logging.info(f"Загружено {row_count} комментариев из файла")
        return comments_df
    
    except Exception as e:
        logging.error(f"Ошибка при загрузке файла комментариев: {str(e)}")
        return pd.DataFrame(columns=columns)

def create_channels_table(dataframes):
    """Создание таблицы channels с уникальными ID"""
    logging.info("Создание таблицы channels...")
    
    # Создаем пустую таблицу с нужными столбцами
    channels_table = pd.DataFrame(columns=['ID', 'Folder_Title', 'Name', 'Description'])
    
    # 1. Обработка данных из channels.csv (Folder_Title, Chats_IDs -> ID)
    if dataframes['channels'] is not None and not dataframes['channels'].empty:
        if all(col in dataframes['channels'].columns for col in ['Folder_Title', 'Chats_IDs']):
            channels_df = dataframes['channels'][['Folder_Title', 'Chats_IDs']].copy()
            channels_df.rename(columns={'Chats_IDs': 'ID'}, inplace=True)
            
            # Проверяем и преобразуем ID к строковому типу для унификации
            channels_df['ID'] = channels_df['ID'].astype(str)
            
            # Добавляем данные в общую таблицу
            channels_table = pd.concat([channels_table, channels_df], ignore_index=True)
            logging.info(f"Добавлено {len(channels_df)} записей из channels.csv")
    
    # 2. Обработка данных из channel_descriptions.csv (Name, ID, Description)
    if dataframes['descriptions'] is not None and not dataframes['descriptions'].empty:
        if all(col in dataframes['descriptions'].columns for col in ['Name', 'ID', 'Description']):
            descriptions_df = dataframes['descriptions'][['Name', 'ID', 'Description']].copy()
            
            # Проверяем и преобразуем ID к строковому типу для унификации
            descriptions_df['ID'] = descriptions_df['ID'].astype(str)
            
            # Обновляем существующие записи или добавляем новые
            for _, row in descriptions_df.iterrows():
                # Проверяем, есть ли уже такой ID в таблице
                mask = channels_table['ID'] == row['ID']
                if mask.any():
                    # Обновляем существующую запись
                    channels_table.loc[mask, 'Name'] = row['Name']
                    channels_table.loc[mask, 'Description'] = row['Description']
                else:
                    # Добавляем новую запись
                    new_row = pd.DataFrame({
                        'ID': [row['ID']],
                        'Name': [row['Name']],
                        'Description': [row['Description']],
                        'Folder_Title': ['Unknown']
                    })
                    channels_table = pd.concat([channels_table, new_row], ignore_index=True)
            
            logging.info(f"Обработано {len(descriptions_df)} записей из channel_descriptions.csv")
    
    # 3. Обработка данных из enhanced_messages.csv (Name, ID)
    if dataframes['messages'] is not None and not dataframes['messages'].empty:
        if all(col in dataframes['messages'].columns for col in ['Name', 'ID']):
            messages_channels = dataframes['messages'][['Name', 'ID']].drop_duplicates().copy()
            
            # Проверяем и преобразуем ID к строковому типу для унификации
            messages_channels['ID'] = messages_channels['ID'].astype(str)
            
            # Обновляем существующие записи или добавляем новые
            for _, row in messages_channels.iterrows():
                mask = channels_table['ID'] == row['ID']
                if mask.any():
                    # Обновляем только если поле Name пустое
                    if pd.isna(channels_table.loc[mask, 'Name']).any() or channels_table.loc[mask, 'Name'].iloc[0] == '':
                        channels_table.loc[mask, 'Name'] = row['Name']
                else:
                    # Добавляем новую запись
                    new_row = pd.DataFrame({
                        'ID': [row['ID']],
                        'Name': [row['Name']],
                        'Description': [''],
                        'Folder_Title': ['Unknown']
                    })
                    channels_table = pd.concat([channels_table, new_row], ignore_index=True)
            
            logging.info(f"Обработано {len(messages_channels)} уникальных каналов из enhanced_messages.csv")
    
    # 4. Обработка данных из reactions_detailed.csv (Channel_Name, Channel_ID)
    if dataframes['reactions'] is not None and not dataframes['reactions'].empty:
        if all(col in dataframes['reactions'].columns for col in ['Channel_Name', 'Channel_ID']):
            reactions_channels = dataframes['reactions'][['Channel_Name', 'Channel_ID']].drop_duplicates().copy()
            reactions_channels.rename(columns={'Channel_Name': 'Name', 'Channel_ID': 'ID'}, inplace=True)
            
            # Проверяем и преобразуем ID к строковому типу для унификации
            reactions_channels['ID'] = reactions_channels['ID'].astype(str)
            
            # Обновляем существующие записи или добавляем новые
            for _, row in reactions_channels.iterrows():
                mask = channels_table['ID'] == row['ID']
                if mask.any():
                    # Обновляем только если поле Name пустое
                    if pd.isna(channels_table.loc[mask, 'Name']).any() or channels_table.loc[mask, 'Name'].iloc[0] == '':
                        channels_table.loc[mask, 'Name'] = row['Name']
                else:
                    # Добавляем новую запись
                    new_row = pd.DataFrame({
                        'ID': [row['ID']],
                        'Name': [row['Name']],
                        'Description': [''],
                        'Folder_Title': ['Unknown']
                    })
                    channels_table = pd.concat([channels_table, new_row], ignore_index=True)
            
            logging.info(f"Обработано {len(reactions_channels)} уникальных каналов из reactions_detailed.csv")
    
    # 5. Обработка данных из comments_detailed.csv (Channel_Name, Channel_ID)
    if dataframes['comments'] is not None and not dataframes['comments'].empty:
        if all(col in dataframes['comments'].columns for col in ['Channel_Name', 'Channel_ID']):
            comments_channels = dataframes['comments'][['Channel_Name', 'Channel_ID']].drop_duplicates().copy()
            comments_channels.rename(columns={'Channel_Name': 'Name', 'Channel_ID': 'ID'}, inplace=True)
            
            # Проверяем и преобразуем ID к строковому типу для унификации
            comments_channels['ID'] = comments_channels['ID'].astype(str)
            
            # Обновляем существующие записи или добавляем новые
            for _, row in comments_channels.iterrows():
                mask = channels_table['ID'] == row['ID']
                if mask.any():
                    # Обновляем только если поле Name пустое
                    if pd.isna(channels_table.loc[mask, 'Name']).any() or channels_table.loc[mask, 'Name'].iloc[0] == '':
                        channels_table.loc[mask, 'Name'] = row['Name']
                else:
                    # Добавляем новую запись
                    new_row = pd.DataFrame({
                        'ID': [row['ID']],
                        'Name': [row['Name']],
                        'Description': [''],
                        'Folder_Title': ['Unknown']
                    })
                    channels_table = pd.concat([channels_table, new_row], ignore_index=True)
            
            logging.info(f"Обработано {len(comments_channels)} уникальных каналов из comments_detailed.csv")
    
    # Заполняем пустые значения
    channels_table['Folder_Title'].fillna('Unknown', inplace=True)
    channels_table['Name'].fillna('', inplace=True)
    channels_table['Description'].fillna('', inplace=True)
    
    # Удаляем дубликаты по ID
    channels_table = channels_table.drop_duplicates(subset=['ID']).reset_index(drop=True)
    
    logging.info(f"Создана таблица channels с {len(channels_table)} уникальными записями")
    return channels_table

def create_messages_table(dataframes):
    """Создание таблицы messages с уникальными Message_ID"""
    logging.info("Создание таблицы messages...")
    
    # Создаем пустую таблицу с нужными столбцами
    messages_table = pd.DataFrame(columns=[
        'Message_ID', 'Original', 'Date', 'Content_Type', 'Views', 'Forwards',
        'Reactions', 'Reactions_Count', 'Total_Reactions', 'Comments',
        'Comments_Count', 'Replies_Count_Meta', 'Has_Comments_Support',
        'Channel_ID'  # Добавляем Channel_ID для связи с таблицей channels
    ])
    
    # 1. Обработка данных из enhanced_messages.csv
    if dataframes['messages'] is not None and not dataframes['messages'].empty:
        required_columns = [
            'Message_ID', 'Original', 'Date', 'Content_Type', 'Views', 'Forwards',
            'Reactions', 'Reactions_Count', 'Total_Reactions', 'Comments',
            'Comments_Count', 'Replies_Count_Meta', 'Has_Comments_Support', 'ID'
        ]
        
        # Проверяем наличие всех необходимых столбцов
        available_columns = [col for col in required_columns if col in dataframes['messages'].columns]
        missing_columns = set(required_columns) - set(available_columns)
        
        if missing_columns:
            logging.warning(f"В таблице messages отсутствуют столбцы: {missing_columns}")
            # Создаем пустые столбцы для отсутствующих
            for col in missing_columns:
                dataframes['messages'][col] = None
        
        # Выбираем нужные столбцы и переименовываем ID в Channel_ID
        messages_df = dataframes['messages'][available_columns].copy()
        messages_df.rename(columns={'ID': 'Channel_ID'}, inplace=True)
        
        # Проверяем и преобразуем Message_ID к строковому типу для унификации
        messages_df['Message_ID'] = messages_df['Message_ID'].astype(str)
        
        # Добавляем данные в общую таблицу
        messages_table = pd.concat([messages_table, messages_df], ignore_index=True)
        logging.info(f"Добавлено {len(messages_df)} записей из enhanced_messages.csv")
    
    # 2. Обработка данных из reactions_detailed.csv
    if dataframes['reactions'] is not None and not dataframes['reactions'].empty:
        required_columns = ['Message_ID', 'Date', 'Reaction_Emoji', 'Reaction_Count', 'Channel_ID']
        
        # Проверяем наличие необходимых столбцов
        if all(col in dataframes['reactions'].columns for col in ['Message_ID', 'Date', 'Reaction_Emoji', 'Reaction_Count']):
            reactions_df = dataframes['reactions'][['Message_ID', 'Date', 'Reaction_Emoji', 'Reaction_Count']].copy()
            
            # Добавляем Channel_ID, если он есть
            if 'Channel_ID' in dataframes['reactions'].columns:
                reactions_df['Channel_ID'] = dataframes['reactions']['Channel_ID']
            
            # Проверяем и преобразуем Message_ID к строковому типу для унификации
            reactions_df['Message_ID'] = reactions_df['Message_ID'].astype(str)
            
            # Группировка реакций по Message_ID
            reactions_grouped = reactions_df.groupby('Message_ID').agg({
                'Date': 'first',
                'Reaction_Emoji': lambda x: list(x),
                'Reaction_Count': lambda x: list(x),
                'Channel_ID': 'first' if 'Channel_ID' in reactions_df.columns else None
            }).reset_index()
            
            # Обновляем существующие записи или добавляем новые
            for _, row in reactions_grouped.iterrows():
                mask = messages_table['Message_ID'] == row['Message_ID']
                if mask.any():
                    # Обновляем существующую запись
                    messages_table.loc[mask, 'Date'] = row['Date'] if pd.isna(messages_table.loc[mask, 'Date']).any() else messages_table.loc[mask, 'Date']
                    messages_table.loc[mask, 'Reactions'] = str(row['Reaction_Emoji']) if 'Reaction_Emoji' in row else messages_table.loc[mask, 'Reactions']
                    messages_table.loc[mask, 'Reactions_Count'] = str(row['Reaction_Count']) if 'Reaction_Count' in row else messages_table.loc[mask, 'Reactions_Count']
                    
                    # Обновляем Channel_ID, если он пустой
                    if 'Channel_ID' in row and pd.notna(row['Channel_ID']):
                        if pd.isna(messages_table.loc[mask, 'Channel_ID']).any() or messages_table.loc[mask, 'Channel_ID'].iloc[0] == '':
                            messages_table.loc[mask, 'Channel_ID'] = row['Channel_ID']
                else:
                    # Создаем новую запись
                    new_row = {
                        'Message_ID': row['Message_ID'],
                        'Date': row['Date'],
                        'Reactions': str(row['Reaction_Emoji']) if 'Reaction_Emoji' in row else None,
                        'Reactions_Count': str(row['Reaction_Count']) if 'Reaction_Count' in row else None,
                        'Channel_ID': row['Channel_ID'] if 'Channel_ID' in row else None
                    }
                    # Заполняем остальные поля пустыми значениями
                    for col in messages_table.columns:
                        if col not in new_row:
                            new_row[col] = None
                    
                    messages_table = pd.concat([messages_table, pd.DataFrame([new_row])], ignore_index=True)
            
            logging.info(f"Обработано {len(reactions_grouped)} уникальных сообщений из reactions_detailed.csv")
    
    # 3. Обработка данных из comments_detailed.csv
    if dataframes['comments'] is not None and not dataframes['comments'].empty:
        required_columns = ['Message_ID', 'Message_Date', 'Comment_Text', 'Comment_Author_ID', 'Comment_Date', 'Comment_Order', 'Channel_ID']
        
        # Проверяем наличие необходимых столбцов
        if all(col in dataframes['comments'].columns for col in ['Message_ID', 'Message_Date', 'Comment_Text', 'Comment_Author_ID', 'Comment_Date']):
            comments_df = dataframes['comments'][['Message_ID', 'Message_Date', 'Comment_Text', 'Comment_Author_ID', 'Comment_Date']].copy()
            
            # Добавляем Comment_Order, если он есть
            if 'Comment_Order' in dataframes['comments'].columns:
                comments_df['Comment_Order'] = dataframes['comments']['Comment_Order']
            
            # Добавляем Channel_ID, если он есть
            if 'Channel_ID' in dataframes['comments'].columns:
                comments_df['Channel_ID'] = dataframes['comments']['Channel_ID']
            
            # Проверяем и преобразуем Message_ID к строковому типу для унификации
            comments_df['Message_ID'] = comments_df['Message_ID'].astype(str)
            
            try:
                # Группировка комментариев по Message_ID
                comments_grouped = comments_df.groupby('Message_ID').agg({
                    'Message_Date': 'first',
                    'Comment_Text': lambda x: list(x),
                    'Comment_Author_ID': lambda x: list(x),
                    'Comment_Date': lambda x: list(x),
                    'Comment_Order': lambda x: list(x) if 'Comment_Order' in comments_df.columns else None,
                    'Channel_ID': 'first' if 'Channel_ID' in comments_df.columns else None
                }).reset_index()
                
                # Обновляем существующие записи или добавляем новые
                for _, row in comments_grouped.iterrows():
                    mask = messages_table['Message_ID'] == row['Message_ID']
                    if mask.any():
                        # Обновляем существующую запись
                        messages_table.loc[mask, 'Date'] = row['Message_Date'] if pd.isna(messages_table.loc[mask, 'Date']).any() else messages_table.loc[mask, 'Date']
                        messages_table.loc[mask, 'Comments'] = str(row['Comment_Text']) if 'Comment_Text' in row else messages_table.loc[mask, 'Comments']
                        messages_table.loc[mask, 'Comments_Count'] = len(row['Comment_Text']) if 'Comment_Text' in row else messages_table.loc[mask, 'Comments_Count']
                        
                        # Обновляем Channel_ID, если он пустой
                        if 'Channel_ID' in row and pd.notna(row['Channel_ID']):
                            if pd.isna(messages_table.loc[mask, 'Channel_ID']).any() or messages_table.loc[mask, 'Channel_ID'].iloc[0] == '':
                                messages_table.loc[mask, 'Channel_ID'] = row['Channel_ID']
                    else:
                        # Создаем новую запись
                        new_row = {
                            'Message_ID': row['Message_ID'],
                            'Date': row['Message_Date'],
                            'Comments': str(row['Comment_Text']) if 'Comment_Text' in row else None,
                            'Comments_Count': len(row['Comment_Text']) if 'Comment_Text' in row else 0,
                            'Channel_ID': row['Channel_ID'] if 'Channel_ID' in row else None
                        }
                        # Заполняем остальные поля пустыми значениями
                        for col in messages_table.columns:
                            if col not in new_row:
                                new_row[col] = None
                        
                        messages_table = pd.concat([messages_table, pd.DataFrame([new_row])], ignore_index=True)
                
                logging.info(f"Обработано {len(comments_grouped)} уникальных сообщений из comments_detailed.csv")
            except Exception as e:
                logging.error(f"Ошибка при группировке комментариев: {str(e)}")
    
    # Заполняем пустые значения
    for col in messages_table.columns:
        if col not in ['Original', 'Comments', 'Reactions']:
            messages_table[col].fillna('', inplace=True)
    
    # Удаляем дубликаты по Message_ID
    messages_table = messages_table.drop_duplicates(subset=['Message_ID']).reset_index(drop=True)
    
    logging.info(f"Создана таблица messages с {len(messages_table)} уникальными записями")
    return messages_table

def main():
    """Основная функция"""
    setup_logging()
    logging.info("Начало объединения CSV файлов...")

    try:
        # Получаем директорию, в которой находится скрипт
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Поиск CSV файлов
        csv_files = find_csv_files()

        # Проверка наличия файлов
        missing_files = [k for k, v in csv_files.items() if v is None]
        if missing_files:
            logging.warning(f"Не найдены файлы для: {missing_files}")

        found_files = {k: v for k, v in csv_files.items() if v is not None}
        logging.info(f"Найдены файлы: {found_files}")

        # Загрузка данных
        dataframes = {}
        
        # Используем новую функцию загрузки для каждого файла
        dataframes['channels'] = load_csv_safely(csv_files['channels']) if csv_files['channels'] else None
        dataframes['descriptions'] = load_csv_safely(csv_files['channel_descriptions']) if csv_files['channel_descriptions'] else None
        dataframes['messages'] = load_csv_safely(csv_files['enhanced_messages']) if csv_files['enhanced_messages'] else None
        dataframes['reactions'] = load_csv_safely(csv_files['reactions_detailed']) if csv_files['reactions_detailed'] else None
        dataframes['comments'] = load_csv_safely(csv_files['comments_detailed']) if csv_files['comments_detailed'] else None

        # Создание итоговых таблиц с новой логикой
        channels_table = create_channels_table(dataframes)
        messages_table = create_messages_table(dataframes)

        # Сохранение результатов в директории скрипта
        channels_output = os.path.join(script_dir, 'merged_channels.csv')
        messages_output = os.path.join(script_dir, 'merged_messages.csv')

        channels_table.to_csv(channels_output, index=False, encoding='utf-8')
        messages_table.to_csv(messages_output, index=False, encoding='utf-8')

        logging.info(f"Таблица channels сохранена в {channels_output}")
        logging.info(f"Таблица messages сохранена в {messages_output}")

        # Вывод статистики
        logging.info("Статистика объединения:")
        logging.info(f"Каналов: {len(channels_table)}")
        logging.info(f"Сообщений: {len(messages_table)}")

        print("\nОбъединение завершено успешно!")
        print(f"Создано файлов: {channels_output}, {messages_output}")

    except Exception as e:
        logging.error(f"Ошибка при объединении файлов: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()