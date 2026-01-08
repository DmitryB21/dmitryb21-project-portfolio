"""
FSM состояния для добавления сделки

Given: Пользователь нажал кнопку "Добавить сделку"
When: Начинается процесс добавления сделки
Then: Пользователь переходит в состояние waiting_for_title
"""

from aiogram.fsm.state import StatesGroup, State


class DealAddStates(StatesGroup):
    """
    Группа состояний для добавления сделки
    
    Состояния:
        waiting_for_title: Ожидание ввода названия сделки
        waiting_for_amount: Ожидание ввода суммы сделки
        waiting_for_status: Ожидание выбора статуса сделки
    """
    waiting_for_title = State()    # Ожидание названия сделки
    waiting_for_amount = State()   # Ожидание суммы сделки
    waiting_for_status = State()   # Ожидание статуса сделки


class DealChangeStatusStates(StatesGroup):
    """
    Группа состояний для изменения статуса сделки
    
    Состояния:
        waiting_for_status: Ожидание выбора нового статуса сделки
    """
    waiting_for_status = State()   # Ожидание нового статуса сделки

