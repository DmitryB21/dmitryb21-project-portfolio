"""
FSM состояния для получения совета по маркетингу

Given: Пользователь нажал кнопку "Получить совет по маркетингу"
When: Начинается процесс получения совета
Then: Пользователь переходит в состояние waiting_for_problem
"""

from aiogram.fsm.state import StatesGroup, State


class MarketingAdviceStates(StatesGroup):
    """
    Группа состояний для получения совета по маркетингу
    
    Состояния:
        waiting_for_problem: Ожидание описания проблемы
    """
    waiting_for_problem = State()  # Ожидание описания проблемы

