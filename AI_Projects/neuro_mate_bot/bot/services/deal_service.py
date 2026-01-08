"""
Сервис для работы со сделками

Given: Сервис инициализирован и имеет доступ к хранилищу
When: Выполняются операции со сделками (создание, чтение, обновление, удаление)
Then: Операции выполняются корректно с валидацией данных
"""

from typing import List, Optional
from bot.models.deal import Deal
from bot.services.storage import storage


class DealService:
    """
    Сервис для работы со сделками
    
    Инкапсулирует бизнес-логику работы со сделками,
    валидацию данных и взаимодействие с хранилищем.
    """
    
    def __init__(self):
        """Инициализация сервиса"""
        self.storage = storage

    def create_deal(self, user_id: int, title: str, amount_str: str, status: str) -> Deal:
        """
        Создание новой сделки
        
        Given: Пользователь ввел название, сумму и статус
        When: Вызывается create_deal с валидными данными
        Then: Сделка создается и сохраняется в хранилище
        
        Args:
            user_id: ID пользователя Telegram
            title: Название сделки
            amount_str: Сумма сделки в виде строки
            status: Статус сделки ("Открыта", "В процессе", "Закрыта")
            
        Returns:
            Созданная сделка
            
        Raises:
            ValueError: Если данные невалидны
        """
        # Валидация названия
        title = title.strip()
        if not title:
            raise ValueError("Название сделки не может быть пустым")
        
        # Валидация суммы
        try:
            amount = float(amount_str.replace(",", ".").strip())
            if amount < 0:
                raise ValueError("Сумма сделки не может быть отрицательной")
        except ValueError:
            raise ValueError("Неверный формат суммы. Используйте число (например: 85000 или 85000.50)")
        
        # Валидация статуса
        valid_statuses = ["Открыта", "В процессе", "Закрыта"]
        if status not in valid_statuses:
            raise ValueError(f"Неверный статус. Используйте один из: {', '.join(valid_statuses)}")
        
        # Создание сделки
        deal = Deal(
            id=0,  # Будет присвоен при сохранении
            user_id=user_id,
            title=title,
            amount=amount,
            status=status
        )
        
        # Сохранение в хранилище
        return self.storage.add_deal(deal)

    def get_user_deals(self, user_id: int) -> List[Deal]:
        """
        Получение всех сделок пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список сделок пользователя
        """
        return self.storage.get_user_deals(user_id)

    def get_deal_by_id(self, deal_id: int) -> Optional[Deal]:
        """
        Получение сделки по ID
        
        Args:
            deal_id: ID сделки
            
        Returns:
            Сделка или None, если не найдена
        """
        return self.storage.get_deal(deal_id)

    def update_deal_status(self, deal_id: int, status: str) -> Optional[Deal]:
        """
        Обновление статуса сделки
        
        Args:
            deal_id: ID сделки
            status: Новый статус
            
        Returns:
            Обновленная сделка или None, если не найдена
            
        Raises:
            ValueError: Если статус невалиден
        """
        valid_statuses = ["Открыта", "В процессе", "Закрыта"]
        if status not in valid_statuses:
            raise ValueError(f"Неверный статус: {status}")
        
        return self.storage.update_deal(deal_id, status=status)

    def delete_deal(self, deal_id: int) -> bool:
        """
        Удаление сделки
        
        Args:
            deal_id: ID сделки
            
        Returns:
            True, если сделка была удалена, False если не найдена
        """
        return self.storage.delete_deal(deal_id)

    def get_closed_deals_statistics(self, user_id: int) -> dict:
        """
        Получение статистики по закрытым сделкам за сессию
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь со статистикой:
            {
                "count": количество закрытых сделок,
                "total_amount": общая сумма закрытых сделок
            }
        """
        deals = self.get_user_deals(user_id)
        closed_deals = [deal for deal in deals if deal.status == "Закрыта"]
        
        count = len(closed_deals)
        total_amount = sum(deal.amount for deal in closed_deals)
        
        return {
            "count": count,
            "total_amount": total_amount
        }


# Глобальный экземпляр сервиса
deal_service = DealService()

