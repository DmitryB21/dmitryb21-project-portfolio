"""
@file: decision_log.py
@description: DecisionLog - трассировка решений агента
@dependencies: datetime, typing
@created: 2024-12-19
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class DecisionEntry:
    """
    Запись в логе решений.
    
    Attributes:
        timestamp: Время принятия решения
        state: Текущее состояние агента
        action: Выполненное действие
        input_data: Входные данные
        output_data: Выходные данные
        metadata: Дополнительные метаданные
    """
    timestamp: datetime
    state: str
    action: str
    input_data: Any
    output_data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)


class DecisionLog:
    """
    Лог решений агента.
    
    Отвечает за:
    - Трассировку каждого шага агента
    - Логирование решений и переходов состояний
    - Сохранение истории для анализа и отладки
    """
    
    def __init__(self):
        """Инициализация DecisionLog"""
        self.entries: List[DecisionEntry] = []
    
    def log_decision(
        self,
        state: str,
        action: str,
        input_data: Any,
        output_data: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Логирует решение агента.
        
        Args:
            state: Текущее состояние агента
            action: Выполненное действие
            input_data: Входные данные
            output_data: Выходные данные
            metadata: Дополнительные метаданные
        """
        entry = DecisionEntry(
            timestamp=datetime.now(),
            state=state,
            action=action,
            input_data=input_data,
            output_data=output_data,
            metadata=metadata or {}
        )
        self.entries.append(entry)
    
    def get_log(self) -> List[DecisionEntry]:
        """
        Возвращает все записи лога.
        
        Returns:
            Список DecisionEntry объектов
        """
        return self.entries.copy()
    
    def clear(self) -> None:
        """
        Очищает лог.
        """
        self.entries.clear()
    
    def export_log(self) -> List[Dict[str, Any]]:
        """
        Экспортирует лог в структурированном формате.
        
        Returns:
            Список словарей с записями лога
        """
        return [
            {
                "timestamp": entry.timestamp.isoformat(),
                "state": entry.state,
                "action": entry.action,
                "input_data": str(entry.input_data),
                "output_data": str(entry.output_data),
                "metadata": entry.metadata
            }
            for entry in self.entries
        ]

