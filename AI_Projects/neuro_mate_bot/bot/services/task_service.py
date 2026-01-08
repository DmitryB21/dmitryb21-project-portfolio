"""
Сервис для работы с задачами

Given: Сервис инициализирован и имеет доступ к хранилищу
When: Выполняются операции с задачами (создание, чтение, обновление, удаление)
Then: Операции выполняются корректно с валидацией данных
"""

from datetime import datetime
from typing import List, Optional
from bot.models.task import Task
from bot.services.storage import storage


class TaskService:
    """
    Сервис для работы с задачами
    
    Инкапсулирует бизнес-логику работы с задачами,
    валидацию данных и взаимодействие с хранилищем.
    """
    
    def __init__(self):
        """Инициализация сервиса"""
        self.storage = storage

    def create_task(self, user_id: int, title: str, time_str: str) -> Task:
        """
        Создание новой задачи
        
        Given: Пользователь ввел название и время
        When: Вызывается create_task с валидными данными
        Then: Задача создается и сохраняется в хранилище
        
        Args:
            user_id: ID пользователя Telegram
            title: Название задачи
            time_str: Время выполнения в формате "YYYY-MM-DD HH:MM"
            
        Returns:
            Созданная задача
            
        Raises:
            ValueError: Если данные невалидны
        """
        # Валидация названия
        title = title.strip()
        if not title:
            raise ValueError("Название задачи не может быть пустым")
        
        # Валидация и парсинг времени в формате HH:MM
        try:
            time_obj = datetime.strptime(time_str, "%H:%M")
            # Устанавливаем время на сегодня, но можно использовать только время
            # Для упрощения используем сегодняшнюю дату с указанным временем
            today = datetime.now().replace(hour=time_obj.hour, minute=time_obj.minute, second=0, microsecond=0)
            # Если время уже прошло сегодня, переносим на завтра
            if today < datetime.now():
                from datetime import timedelta
                today += timedelta(days=1)
            time_obj = today
        except ValueError:
            raise ValueError("Неверный формат времени. Используйте формат: HH:MM (например: 18:00)")
        
        # Создание задачи
        task = Task(
            id=0,  # Будет присвоен при сохранении
            user_id=user_id,
            title=title,
            time=time_obj,
            status="Не выполнена"
        )
        
        # Сохранение в хранилище
        return self.storage.add_task(task)

    def get_user_tasks(self, user_id: int) -> List[Task]:
        """
        Получение всех задач пользователя
        
        Given: У пользователя есть задачи в системе
        When: Вызывается get_user_tasks для пользователя
        Then: Возвращается список всех задач пользователя, отсортированный по времени
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список задач пользователя
        """
        return self.storage.get_user_tasks(user_id)

    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        """
        Получение задачи по ID
        
        Given: Задача существует в системе
        When: Вызывается get_task_by_id с существующим ID
        Then: Возвращается задача с указанным ID
        
        Args:
            task_id: ID задачи
            
        Returns:
            Задача или None, если не найдена
        """
        return self.storage.get_task(task_id)

    def update_task_status(self, task_id: int, status: str) -> Optional[Task]:
        """
        Обновление статуса задачи
        
        Given: Задача существует в системе
        When: Вызывается update_task_status с валидным статусом
        Then: Статус задачи обновляется
        
        Args:
            task_id: ID задачи
            status: Новый статус ("В работе" или "Выполнена")
            
        Returns:
            Обновленная задача или None, если не найдена
            
        Raises:
            ValueError: Если статус невалиден
        """
        if status not in ["Не выполнена", "Выполнена"]:
            raise ValueError(f"Неверный статус: {status}")
        
        return self.storage.update_task(task_id, status=status)

    def delete_task(self, task_id: int) -> bool:
        """
        Удаление задачи
        
        Given: Задача существует в системе
        When: Вызывается delete_task с существующим ID
        Then: Задача удаляется из хранилища
        
        Args:
            task_id: ID задачи
            
        Returns:
            True, если задача была удалена, False если не найдена
        """
        return self.storage.delete_task(task_id)

    def get_task_statistics(self, user_id: int) -> dict:
        """
        Получение статистики по задачам пользователя
        
        Given: У пользователя есть задачи в системе
        When: Вызывается get_task_statistics для пользователя
        Then: Возвращается словарь со статистикой
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь со статистикой:
            {
                "total": общее количество задач,
                "not_completed": количество задач "Не выполнена",
                "completed": количество задач "Выполнена"
            }
        """
        tasks = self.get_user_tasks(user_id)
        
        total = len(tasks)
        not_completed = sum(1 for task in tasks if task.status == "Не выполнена")
        completed = sum(1 for task in tasks if task.status == "Выполнена")
        
        return {
            "total": total,
            "not_completed": not_completed,
            "completed": completed
        }


# Глобальный экземпляр сервиса
task_service = TaskService()

