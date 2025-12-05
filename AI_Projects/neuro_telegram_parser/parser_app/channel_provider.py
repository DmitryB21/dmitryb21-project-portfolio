import pandas as pd
import json
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def load_channels_from_file(file_path: str) -> Optional[List[Dict[str, Any]]]:
    """
    Загружает каналы из CSV или JSON файла
    
    Args:
        file_path: Путь к CSV или JSON файлу
    
    Returns:
        Список каналов или None при ошибке
    """
    try:
        file_ext = file_path.lower().split('.')[-1]
        
        if file_ext == 'json':
            return _load_channels_from_json(file_path)
        else:
            # По умолчанию обрабатываем как CSV
            return _load_channels_from_csv(file_path)
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла {file_path}: {e}")
        return None


def _load_channels_from_csv(file_path: str) -> Optional[List[Dict[str, Any]]]:
    """Загружает каналы из CSV файла"""
    try:
        df = pd.read_csv(file_path)
        logger.info(f"Загружен CSV файл {file_path}, строк: {len(df)}")
        
        # Заполняем пустые значения
        df = df.fillna("")
        
        # Нормализуем имена колонок (без пробелов/нижних подчёркиваний, в нижнем регистре)
        original_columns = [ (col.lstrip('\ufeff') if isinstance(col, str) else col) for col in list(df.columns) ]
        normalized_map = {col: str(col).lstrip('\ufeff').strip().lower().replace(" ", "").replace("_", "") for col in original_columns}
        df.columns = [normalized_map[col] for col in original_columns]

        # Поддерживаем варианты названий колонок с ID (не обязательно, если есть username)
        id_column_candidates = [
            "chatsids", "chatsid", "chatids", "chatid",
            "channelids", "channelid",
            "ids", "id",
            "chats_ids", "chats_id", "channel_id"
        ]
        id_col = next((c for c in id_column_candidates if c in df.columns), None)

        # Преобразуем ID в числовой формат, если колонка есть
        if id_col:
            df[id_col] = pd.to_numeric(df[id_col], errors="coerce")

        # Поддержка username в CSV
        username_col_candidates = ["username", "user", "channelusername"]
        username_col = next((c for c in username_col_candidates if c in df.columns), None)

        # Колонки для названия/категории
        name_col_candidates = ["channelname", "name", "title", "foldertitle", "folder_title"]
        name_col = next((c for c in name_col_candidates if c in df.columns), None)
        folder_col_candidates = ["category", "foldertitle", "folder_title", "folder", "foldername"]
        folder_col = next((c for c in folder_col_candidates if c in df.columns), None)

        # Создаём список каналов: принимаем строки с username ИЛИ валидным ID
        channel_list = []
        for _, row in df.iterrows():
            username_val = str(row.get(username_col, "")).strip() if username_col else ""
            chan_id_val = None
            if id_col and pd.notna(row.get(id_col)):
                try:
                    chan_id_val = int(row.get(id_col))
                except (ValueError, TypeError):
                    chan_id_val = None

            if not username_val and chan_id_val is None:
                # Ни username, ни валидный ID — пропускаем строку
                continue

            folder_title = row.get(folder_col, "CHANNELS") if folder_col else "CHANNELS"
            raw_name = str(row.get(name_col, "")).strip() if name_col else ""
            title_val = raw_name or (f"Channel_{chan_id_val}" if chan_id_val is not None else (f"@{username_val}" if username_val else "Channel"))

            channel_info = {
                "id": chan_id_val,  # может быть None
                "title": title_val,
                "description": "",
                "folder_title": folder_title,
                "username": username_val or None
            }
            channel_list.append(channel_info)
        
        logger.info(f"Обработано {len(channel_list)} каналов из CSV файла {file_path}")
        return channel_list
        
    except FileNotFoundError:
        logger.error(f"CSV файл не найден: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при загрузке CSV файла {file_path}: {e}")
        return None


def _load_channels_from_json(file_path: str) -> Optional[List[Dict[str, Any]]]:
    """Загружает каналы из JSON файла"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"Загружен JSON файл {file_path}")
        
        # Поддерживаем разные форматы JSON
        if isinstance(data, list):
            # Формат: [{"id": 123, "title": "...", "username": "..."}, ...]
            channels = data
        elif isinstance(data, dict):
            if 'channels' in data:
                # Формат: {"channels": [{"id": 123, ...}, ...]}
                channels = data['channels']
            elif 'data' in data:
                # Формат: {"data": [{"id": 123, ...}, ...]}
                channels = data['data']
            else:
                # Формат: {"channel_id": 123, "title": "...", ...} - один канал
                channels = [data]
        else:
            logger.error(f"Неподдерживаемый формат JSON в файле {file_path}")
            return None
        
        if not channels:
            logger.warning(f"JSON файл {file_path} не содержит каналов")
            return None
        
        # Обрабатываем каналы
        channel_list = []
        for i, channel_data in enumerate(channels):
            try:
                # Извлекаем ID канала
                channel_id = None
                for id_field in ['id', 'channel_id', 'chat_id', 'telegram_id']:
                    if id_field in channel_data and channel_data[id_field] is not None:
                        channel_id = int(channel_data[id_field])
                        break
                # Извлекаем username (может отсутствовать)
                username = (channel_data.get('username') or '').strip()
                # Принимаем канал, если есть username ИЛИ числовой ID
                if channel_id is None and not username:
                    logger.warning(f"Пропускаем канал #{i+1}: не найден ID и username")
                    continue
                
                # Формируем информацию о канале
                channel_info = {
                    "id": channel_id,  # может быть None, если парсим по username
                    "title": channel_data.get('title', channel_data.get('name', f"Channel_{channel_id}")),
                    "description": channel_data.get('description', ''),
                    "username": username or None,
                    "folder_title": channel_data.get('folder_title', channel_data.get('category', 'JSON_CHANNELS'))
                }
                
                channel_list.append(channel_info)
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Пропускаем канал #{i+1}: некорректные данные - {e}")
                continue
        
        logger.info(f"Обработано {len(channel_list)} каналов из JSON файла {file_path}")
        return channel_list
        
    except FileNotFoundError:
        logger.error(f"JSON файл не найден: {file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON в файле {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при загрузке JSON файла {file_path}: {e}")
        return None


def extract_channel_identifier(channel_info: Dict[str, Any]) -> int:
    """
    Извлекает ID канала из информации о канале.
    
    Args:
        channel_info: Словарь с информацией о канале
    
    Returns:
        ID канала (может быть отрицательным для каналов Telegram)
    """
    possible_fields = ["ID", "id", "ChatsIDs", "chat_id", "channel_id"]
    
    for field in possible_fields:
        value = channel_info.get(field)
        if value is not None:
            try:
                return int(value)
            except (ValueError, TypeError):
                continue
                
    raise ValueError(f"ID не найден в {channel_info}")


def validate_channel_data(channel_info: Dict[str, Any]) -> bool:
    """
    Проверяет корректность данных канала.
    
    Args:
        channel_info: Словарь с информацией о канале
    
    Returns:
        True если данные корректны, False иначе
    """
    try:
        # Поддержка двух вариантов: username или числовой ID
        username = (channel_info.get('username') or '').strip()
        if username:
            return True
        
        channel_id = extract_channel_identifier(channel_info)
        if not isinstance(channel_id, int):
            logger.error(f"ID канала не является целым числом: {channel_info}")
            return False
        if channel_id == 0:
            logger.error(f"ID канала равен нулю: {channel_info}")
            return False
        return True
        
    except (ValueError, TypeError) as e:
        logger.error(f"Некорректные данные канала: {channel_info}, ошибка: {e}")
        return False


def format_channel_for_search_result(search_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Форматирует результат поиска канала в стандартный формат.
    
    Args:
        search_result: Результат поиска канала
    
    Returns:
        Отформатированные данные канала
    """
    return {
        "id": search_result.get("id"),
        "title": search_result.get("title", ""),
        "username": search_result.get("username"),
        "description": search_result.get("description", ""),
        "members_count": search_result.get("members_count"),
    }