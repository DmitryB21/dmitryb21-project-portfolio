"""
Reply-клавиатуры

Given: Пользователь в начальном состоянии
When: Бот отправляет сообщение
Then: Бот показывает Reply-клавиатуру с основными кнопками
"""

from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Главная Reply-клавиатура с основными кнопками
    
    Returns:
        ReplyKeyboardMarkup с кнопками:
        - "Добавить задачу"
        - "Добавить сделку"
        - "Просмотреть задачи"
        - "Просмотреть сделки"
        - "Получить совет по маркетингу"
        - "Получить мотивацию"
    """
    builder = ReplyKeyboardBuilder()
    
    builder.button(text="Добавить задачу")
    builder.button(text="Добавить сделку")
    builder.button(text="Просмотреть задачи")
    builder.button(text="Просмотреть сделки")
    builder.button(text="Получить совет по маркетингу")
    builder.button(text="Получить мотивацию")
    
    # Размещаем кнопки по две в ряд для более компактного вида
    builder.adjust(2, 2, 2)
    
    return builder.as_markup(resize_keyboard=True)

