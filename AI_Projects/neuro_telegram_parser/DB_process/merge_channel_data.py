#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import json
import os
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('channel_merge.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def load_channels_from_csv(file_path: str, id_field: str = "Chats_IDs") -> List[Dict[str, Any]]:
    """
    Загружает каналы из CSV файла с ID.
    
    Args:
        file_path: Путь к CSV файлу
        id_field: Название поля с ID каналов
        
    Returns:
        Список словарей с информацией о каналах
    """
    channels = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if id_field in row:
                    channel_id = row[id_field].strip()
                    try:
                        channel_id = int(channel_id)
                        channel_data = {
                            'id': channel_id,
                            'title': f"Channel_{channel_id}",
                            'folder': row.get('Folder_Title', '').strip()
                        }
                        channels.append(channel_data)
                    except (ValueError, TypeError):
                        logger.warning(f"Пропуск строки с некорректным ID: {row}")
                else:
                    logger.warning(f"Поле {id_field} не найдено в строке: {row}")
        
        logger.info(f"Загружено {len(channels)} каналов из {file_path}")
        return channels
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла {file_path}: {e}")
        return []

def load_channel_descriptions(file_path: str) -> Dict[int, Dict[str, Any]]:
    """
    Загружает описания каналов из CSV файла.
    
    Args:
        file_path: Путь к CSV файлу с описаниями
        
    Returns:
        Словарь, где ключ - ID канала, значение - информация о канале
    """
    channel_descriptions = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if 'ID' in row:
                    try:
                        channel_id = int(row['ID'].strip())
                        channel_descriptions[channel_id] = {
                            'id': channel_id,
                            'title': row.get('Name', '').strip(),
                            'description': row.get('Description', '').strip()
                        }
                    except (ValueError, TypeError):
                        logger.warning(f"Пропуск строки с некорректным ID: {row}")
                else:
                    logger.warning(f"Поле ID не найдено в строке: {row}")
        
        logger.info(f"Загружено {len(channel_descriptions)} описаний каналов из {file_path}")
        return channel_descriptions
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла {file_path}: {e}")
        return {}

def extract_usernames_from_description(description: str) -> List[str]:
    """
    Извлекает username из текста описания канала.
    
    Args:
        description: Текст описания
        
    Returns:
        Список найденных username
    """
    if not description:
        return []
        
    usernames = []
    words = description.split()
    
    for word in words:
        # Ищем слова, начинающиеся с @
        if word.startswith('@'):
            username = word.strip('@.,!?():;"\'')
            if username and len(username) >= 3:  # Минимальная длина username в Telegram
                usernames.append(username)
    
    return usernames

def merge_channel_data(channels: List[Dict[str, Any]], descriptions: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Объединяет данные о каналах из двух источников.
    
    Args:
        channels: Список каналов из первого источника
        descriptions: Словарь с описаниями каналов
        
    Returns:
        Список объединенных данных о каналах
    """
    merged_channels = []
    
    for channel in channels:
        channel_id = channel.get('id')
        if channel_id in descriptions:
            # Объединяем данные
            merged_data = {**channel, **descriptions[channel_id]}
            
            # Извлекаем username из описания
            if 'description' in merged_data:
                usernames = extract_usernames_from_description(merged_data['description'])
                if usernames:
                    merged_data['username'] = usernames[0]  # Берем первый найденный username
                    if len(usernames) > 1:
                        merged_data['additional_usernames'] = usernames[1:]
            
            merged_channels.append(merged_data)
        else:
            # Если описание не найдено, используем только базовые данные
            merged_channels.append(channel)
    
    logger.info(f"Объединено {len(merged_channels)} каналов")
    return merged_channels

def save_merged_data(channels: List[Dict[str, Any]], output_file: str):
    """
    Сохраняет объединенные данные в JSON файл.
    
    Args:
        channels: Список объединенных данных о каналах
        output_file: Путь для сохранения результата
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(channels, file, ensure_ascii=False, indent=2)
        logger.info(f"Данные сохранены в {output_file}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла {output_file}: {e}")

def save_csv_for_parsing(channels: List[Dict[str, Any]], output_file: str):
    """
    Сохраняет данные в CSV формате для последующего парсинга.
    
    Args:
        channels: Список объединенных данных о каналах
        output_file: Путь для сохранения результата
    """
    try:
        with open(output_file, 'w', encoding='utf-8', newline='') as file:
            fieldnames = ['id', 'username', 'title', 'description', 'folder']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            
            for channel in channels:
                # Подготавливаем строку для записи
                row = {
                    'id': channel.get('id', ''),
                    'username': channel.get('username', ''),
                    'title': channel.get('title', ''),
                    'description': channel.get('description', '')[:100],  # Ограничиваем длину описания
                    'folder': channel.get('folder', '')
                }
                writer.writerow(row)
                
        logger.info(f"CSV для парсинга сохранен в {output_file}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении CSV файла {output_file}: {e}")

def main():
    """
    Основная функция для объединения данных о каналах.
    """
    # Пути к файлам
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    channels_csv = os.path.join(base_dir, 'telegram_parser', 'channel_sources', 'IT_channels.csv')
    descriptions_csv = os.path.join(base_dir, 'telegram_parser', 'channel_sources', 'IT_channel_descriptions.csv')
    
    # Создаем директорию для результатов, если она не существует
    output_dir = os.path.join(base_dir, 'telegram_parser', 'channel_sources', 'merged')
    os.makedirs(output_dir, exist_ok=True)
    
    output_json = os.path.join(output_dir, 'merged_channels.json')
    output_csv = os.path.join(output_dir, 'channels_for_parsing.csv')
    
    # Загружаем данные
    channels = load_channels_from_csv(channels_csv)
    descriptions = load_channel_descriptions(descriptions_csv)
    
    # Объединяем данные
    merged_channels = merge_channel_data(channels, descriptions)
    
    # Сохраняем результаты
    save_merged_data(merged_channels, output_json)
    save_csv_for_parsing(merged_channels, output_csv)
    
    logger.info("Объединение данных завершено успешно")
    
    # Выводим статистику
    channels_with_username = sum(1 for ch in merged_channels if 'username' in ch)
    logger.info(f"Статистика:")
    logger.info(f"  - Всего каналов: {len(merged_channels)}")
    logger.info(f"  - Каналов с username: {channels_with_username}")
    logger.info(f"  - Каналов только с ID: {len(merged_channels) - channels_with_username}")

if __name__ == "__main__":
    main()