"""
Модель задачи

Given: Модель задачи существует в системе
When: Создается новая задача
Then: Задача содержит все необходимые поля (id, user_id, title, time, status, created_at)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Task:
    """
    Модель задачи
    
    Attributes:
        id: Уникальный идентификатор задачи
        user_id: ID пользователя Telegram, которому принадлежит задача
        title: Название задачи
        time: Время выполнения задачи
        status: Статус задачи ("В работе" или "Выполнена")
        created_at: Дата и время создания задачи
    """
    id: int
    user_id: int
    title: str
    time: datetime
    status: str = "Не выполнена"
    created_at: Optional[datetime] = None

    def __post_init__(self):
        """Инициализация после создания объекта"""
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> dict:
        """Преобразование задачи в словарь"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "time": self.time.isoformat(),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Создание задачи из словаря"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            title=data["title"],
            time=datetime.fromisoformat(data["time"]),
            status=data.get("status", "Не выполнена"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
        )

