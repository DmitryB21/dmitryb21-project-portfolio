"""
FSM состояния для добавления задачи

Given: Пользователь нажал кнопку "Добавить задачу"
When: Начинается процесс добавления задачи
Then: Пользователь переходит в состояние waiting_for_title
"""

from aiogram.fsm.state import StatesGroup, State


class TaskAddStates(StatesGroup):
    """
    Группа состояний для добавления задачи
    
    Состояния:
        waiting_for_title: Ожидание ввода названия задачи
        waiting_for_time: Ожидание ввода времени выполнения задачи
    """
    waiting_for_title = State()  # Ожидание названия задачи
    waiting_for_time = State()   # Ожидание времени выполнения

