"""
Хранилище данных (In-memory)

Given: Хранилище инициализировано
When: Добавляется/изменяется/удаляется задача
Then: Данные сохраняются в памяти и доступны для чтения
"""

from typing import Dict, List, Optional
from bot.models.task import Task
from bot.models.deal import Deal


class InMemoryStorage:
    """
    In-memory хранилище задач и сделок
    
    В текущей реализации используется словарь для хранения данных.
    В будущем будет заменено на базу данных.
    """
    
    def __init__(self):
        """Инициализация хранилища"""
        # Словари для задач и сделок
        self._tasks: Dict[int, Task] = {}
        self._deals: Dict[int, Deal] = {}
        # Счетчики для генерации ID
        self._next_task_id: int = 1
        self._next_deal_id: int = 1

    def add_task(self, task: Task) -> Task:
        """
        Добавление задачи в хранилище
        
        Args:
            task: Задача для добавления
            
        Returns:
            Задача с присвоенным ID
        """
        task.id = self._next_task_id
        self._next_task_id += 1
        self._tasks[task.id] = task
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        """
        Получение задачи по ID
        
        Args:
            task_id: ID задачи
            
        Returns:
            Задача или None, если не найдена
        """
        return self._tasks.get(task_id)

    def get_user_tasks(self, user_id: int) -> List[Task]:
        """
        Получение всех задач пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список задач пользователя, отсортированный по времени
        """
        tasks = [task for task in self._tasks.values() if task.user_id == user_id]
        # Сортировка по времени выполнения
        tasks.sort(key=lambda t: t.time)
        return tasks

    def update_task(self, task_id: int, **kwargs) -> Optional[Task]:
        """
        Обновление задачи
        
        Args:
            task_id: ID задачи
            **kwargs: Поля для обновления
            
        Returns:
            Обновленная задача или None, если не найдена
        """
        task = self._tasks.get(task_id)
        if task:
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
        return task

    def delete_task(self, task_id: int) -> bool:
        """
        Удаление задачи
        
        Args:
            task_id: ID задачи
            
        Returns:
            True, если задача была удалена, False если не найдена
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    # Методы для работы со сделками
    def add_deal(self, deal: Deal) -> Deal:
        """
        Добавление сделки в хранилище
        
        Args:
            deal: Сделка для добавления
            
        Returns:
            Сделка с присвоенным ID
        """
        deal.id = self._next_deal_id
        self._next_deal_id += 1
        self._deals[deal.id] = deal
        return deal

    def get_deal(self, deal_id: int) -> Optional[Deal]:
        """
        Получение сделки по ID
        
        Args:
            deal_id: ID сделки
            
        Returns:
            Сделка или None, если не найдена
        """
        return self._deals.get(deal_id)

    def get_user_deals(self, user_id: int) -> List[Deal]:
        """
        Получение всех сделок пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список сделок пользователя, отсортированный по дате создания
        """
        deals = [deal for deal in self._deals.values() if deal.user_id == user_id]
        # Сортировка по дате создания (новые сначала)
        deals.sort(key=lambda d: d.created_at, reverse=True)
        return deals

    def update_deal(self, deal_id: int, **kwargs) -> Optional[Deal]:
        """
        Обновление сделки
        
        Args:
            deal_id: ID сделки
            **kwargs: Поля для обновления
            
        Returns:
            Обновленная сделка или None, если не найдена
        """
        deal = self._deals.get(deal_id)
        if deal:
            for key, value in kwargs.items():
                if hasattr(deal, key):
                    setattr(deal, key, value)
        return deal

    def delete_deal(self, deal_id: int) -> bool:
        """
        Удаление сделки
        
        Args:
            deal_id: ID сделки
            
        Returns:
            True, если сделка была удалена, False если не найдена
        """
        if deal_id in self._deals:
            del self._deals[deal_id]
            return True
        return False

    def clear(self):
        """Очистка хранилища (для тестов)"""
        self._tasks.clear()
        self._deals.clear()
        self._next_task_id = 1
        self._next_deal_id = 1


# Глобальный экземпляр хранилища
storage = InMemoryStorage()

