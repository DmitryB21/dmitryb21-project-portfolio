"""
Inline-клавиатуры для задач

Given: У пользователя есть задачи
When: Пользователь запрашивает просмотр задач
Then: Бот показывает список задач с Inline-кнопками для каждой задачи
"""

from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.models.task import Task


def get_task_keyboard(task_id: int, status: str) -> InlineKeyboardMarkup:
    """
    Inline-клавиатура для одной задачи
    
    Given: Задача существует со статусом
    When: Формируется клавиатура для задачи
    Then: Возвращается клавиатура с соответствующими кнопками
    
    Args:
        task_id: ID задачи
        status: Статус задачи ("В работе" или "Выполнена")
        
    Returns:
        InlineKeyboardMarkup с кнопками:
        - Для "В работе": "✅ Выполнена" и "🗑 Удалить"
        - Для "Выполнена": только "🗑 Удалить"
    """
    builder = InlineKeyboardBuilder()
    
    # Если задача не выполнена, показываем кнопку "Выполнена"
    if status == "Не выполнена":
        builder.button(
            text="✅ Выполнена",
            callback_data=f"task_complete_{task_id}"
        )
    
    # Кнопка удаления всегда доступна
    builder.button(
        text="🗑 Удалить",
        callback_data=f"task_delete_{task_id}"
    )
    
    builder.adjust(1)
    
    return builder.as_markup()


def get_tasks_list_keyboard(tasks: List[Task]) -> List[InlineKeyboardMarkup]:
    """
    Список Inline-клавиатур для списка задач
    
    Given: Список задач пользователя
    When: Формируются клавиатуры для отображения списка
    Then: Возвращается список клавиатур, по одной на каждую задачу
    
    Args:
        tasks: Список задач
        
    Returns:
        Список InlineKeyboardMarkup, каждая для соответствующей задачи
    """
    return [get_task_keyboard(task.id, task.status) for task in tasks]

