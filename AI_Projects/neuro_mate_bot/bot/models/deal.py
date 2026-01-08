"""
Модель сделки

Given: Модель сделки существует в системе
When: Создается новая сделка
Then: Сделка содержит все необходимые поля (id, user_id, title, amount, status, created_at)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Deal:
    """
    Модель сделки
    
    Attributes:
        id: Уникальный идентификатор сделки
        user_id: ID пользователя Telegram, которому принадлежит сделка
        title: Название сделки
        amount: Сумма сделки (в рублях)
        status: Статус сделки ("Открыта", "В процессе", "Закрыта")
        created_at: Дата и время создания сделки
    """
    id: int
    user_id: int
    title: str
    amount: float
    status: str = "Открыта"
    created_at: Optional[datetime] = None

    def __post_init__(self):
        """Инициализация после создания объекта"""
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> dict:
        """Преобразование сделки в словарь"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "amount": self.amount,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Deal":
        """Создание сделки из словаря"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            title=data["title"],
            amount=data["amount"],
            status=data.get("status", "Открыта"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
        )

