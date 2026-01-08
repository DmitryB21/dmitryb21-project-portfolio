"""
Inline-клавиатуры для сделок

Given: У пользователя есть сделки
When: Пользователь запрашивает просмотр сделок
Then: Бот показывает список сделок с Inline-кнопками для каждой сделки
"""

from typing import List
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.models.deal import Deal


def get_deal_keyboard(deal_id: int) -> InlineKeyboardMarkup:
    """
    Inline-клавиатура для одной сделки
    
    Given: Сделка существует
    When: Формируется клавиатура для сделки
    Then: Возвращается клавиатура с кнопкой изменения статуса
    
    Args:
        deal_id: ID сделки
        
    Returns:
        InlineKeyboardMarkup с кнопкой "Изменить статус сделки"
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="Изменить статус сделки",
        callback_data=f"deal_change_status_{deal_id}"
    )
    
    builder.adjust(1)
    
    return builder.as_markup()


def get_deals_list_keyboard(deals: List[Deal]) -> List[InlineKeyboardMarkup]:
    """
    Список Inline-клавиатур для списка сделок
    
    Args:
        deals: Список сделок
        
    Returns:
        Список InlineKeyboardMarkup, каждая для соответствующей сделки
    """
    return [get_deal_keyboard(deal.id) for deal in deals]

