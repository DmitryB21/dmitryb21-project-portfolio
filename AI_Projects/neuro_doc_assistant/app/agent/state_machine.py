"""
@file: state_machine.py
@description: AgentStateMachine - детерминированная state machine для агента
@dependencies: enum
@created: 2024-12-19
"""

from enum import Enum
from typing import List, Optional


class AgentState(Enum):
    """
    Состояния агента.
    
    Соответствуют состояниям из docs/agent_flow.md
    """
    IDLE = "IDLE"
    VALIDATE_QUERY = "VALIDATE_QUERY"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    RETRIEVE = "RETRIEVE"
    METADATA_FILTER = "METADATA_FILTER"
    RERANK = "RERANK"
    GENERATE = "GENERATE"
    VALIDATE_ANSWER = "VALIDATE_ANSWER"
    LOG_METRICS = "LOG_METRICS"
    RETURN_RESPONSE = "RETURN_RESPONSE"


class AgentStateMachine:
    """
    Конечный автомат состояний для агента.
    
    Отвечает за:
    - Управление состояниями агента
    - Детерминированные переходы между состояниями
    - Валидацию переходов
    - Сохранение истории состояний
    """
    
    def __init__(self):
        """Инициализация AgentStateMachine"""
        self.current_state = AgentState.IDLE
        self.state_history: List[AgentState] = [AgentState.IDLE]
    
    def transition_to(self, new_state: AgentState) -> None:
        """
        Выполняет переход в новое состояние.
        
        Args:
            new_state: Новое состояние для перехода
            
        Raises:
            ValueError: Если переход недопустим (опционально, в зависимости от требований)
        """
        # В текущей реализации разрешаем любые переходы
        # В будущем можно добавить валидацию допустимых переходов
        self.current_state = new_state
        self.state_history.append(new_state)
    
    def get_history(self) -> List[AgentState]:
        """
        Возвращает историю состояний.
        
        Returns:
            Список состояний в порядке их прохождения
        """
        return self.state_history.copy()
    
    def reset(self) -> None:
        """
        Сбрасывает state machine в начальное состояние.
        """
        self.current_state = AgentState.IDLE
        self.state_history = [AgentState.IDLE]

