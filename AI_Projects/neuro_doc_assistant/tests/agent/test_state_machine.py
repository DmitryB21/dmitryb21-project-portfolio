"""
@file: test_state_machine.py
@description: Тесты для AgentStateMachine - детерминированная state machine
@dependencies: app.agent.state_machine
@created: 2024-12-19
"""

import pytest
from app.agent.state_machine import AgentStateMachine, AgentState


class TestAgentStateMachine:
    """
    Тесты для AgentStateMachine компонента.
    
    AgentStateMachine отвечает за:
    - Управление состояниями агента (IDLE → VALIDATE_QUERY → RETRIEVE → GENERATE → ...)
    - Детерминированные переходы между состояниями
    - Валидацию переходов
    """
    
    @pytest.fixture
    def state_machine(self):
        """Фикстура для создания экземпляра AgentStateMachine"""
        return AgentStateMachine()
    
    def test_initial_state_is_idle(self, state_machine):
        """
        UC-1 Agent: Начальное состояние IDLE
        
        Given:
            - AgentStateMachine создан
        When:
            - Проверяется текущее состояние
        Then:
            - Состояние = IDLE
        """
        assert state_machine.current_state == AgentState.IDLE
    
    def test_transition_idle_to_validate_query(self, state_machine):
        """
        UC-1 Agent: Переход IDLE → VALIDATE_QUERY
        
        Given:
            - Состояние IDLE
            - Получен запрос пользователя
        When:
            - Вызывается transition_to(AgentState.VALIDATE_QUERY)
        Then:
            - Состояние изменяется на VALIDATE_QUERY
        """
        state_machine.transition_to(AgentState.VALIDATE_QUERY)
        assert state_machine.current_state == AgentState.VALIDATE_QUERY
    
    def test_transition_validate_query_to_retrieve(self, state_machine):
        """
        UC-1 Agent: Переход VALIDATE_QUERY → RETRIEVE
        
        Given:
            - Состояние VALIDATE_QUERY
            - Запрос валиден (контекст достаточен)
        When:
            - Вызывается transition_to(AgentState.RETRIEVE)
        Then:
            - Состояние изменяется на RETRIEVE
        """
        state_machine.transition_to(AgentState.VALIDATE_QUERY)
        state_machine.transition_to(AgentState.RETRIEVE)
        assert state_machine.current_state == AgentState.RETRIEVE
    
    def test_transition_validate_query_to_request_clarification(self, state_machine):
        """
        UC-2 Agent: Переход VALIDATE_QUERY → REQUEST_CLARIFICATION
        
        Given:
            - Состояние VALIDATE_QUERY
            - Запрос неполный (недостаточно контекста)
        When:
            - Вызывается transition_to(AgentState.REQUEST_CLARIFICATION)
        Then:
            - Состояние изменяется на REQUEST_CLARIFICATION
        """
        state_machine.transition_to(AgentState.VALIDATE_QUERY)
        state_machine.transition_to(AgentState.REQUEST_CLARIFICATION)
        assert state_machine.current_state == AgentState.REQUEST_CLARIFICATION
    
    def test_transition_retrieve_to_metadata_filter(self, state_machine):
        """
        UC-3 Agent: Переход RETRIEVE → METADATA_FILTER
        
        Given:
            - Состояние RETRIEVE
            - Retrieved чанки получены
        When:
            - Вызывается transition_to(AgentState.METADATA_FILTER)
        Then:
            - Состояние изменяется на METADATA_FILTER
        """
        state_machine.transition_to(AgentState.RETRIEVE)
        state_machine.transition_to(AgentState.METADATA_FILTER)
        assert state_machine.current_state == AgentState.METADATA_FILTER
    
    def test_transition_metadata_filter_to_generate(self, state_machine):
        """
        UC-1 Agent: Переход METADATA_FILTER → GENERATE
        
        Given:
            - Состояние METADATA_FILTER
            - Чанки отфильтрованы
        When:
            - Вызывается transition_to(AgentState.GENERATE)
        Then:
            - Состояние изменяется на GENERATE
        """
        state_machine.transition_to(AgentState.METADATA_FILTER)
        state_machine.transition_to(AgentState.GENERATE)
        assert state_machine.current_state == AgentState.GENERATE
    
    def test_transition_generate_to_validate_answer(self, state_machine):
        """
        UC-1 Agent: Переход GENERATE → VALIDATE_ANSWER
        
        Given:
            - Состояние GENERATE
            - Ответ сгенерирован
        When:
            - Вызывается transition_to(AgentState.VALIDATE_ANSWER)
        Then:
            - Состояние изменяется на VALIDATE_ANSWER
        """
        state_machine.transition_to(AgentState.GENERATE)
        state_machine.transition_to(AgentState.VALIDATE_ANSWER)
        assert state_machine.current_state == AgentState.VALIDATE_ANSWER
    
    def test_transition_validate_answer_to_log_metrics(self, state_machine):
        """
        UC-1 Agent: Переход VALIDATE_ANSWER → LOG_METRICS
        
        Given:
            - Состояние VALIDATE_ANSWER
            - Ответ валиден
        When:
            - Вызывается transition_to(AgentState.LOG_METRICS)
        Then:
            - Состояние изменяется на LOG_METRICS
        """
        state_machine.transition_to(AgentState.VALIDATE_ANSWER)
        state_machine.transition_to(AgentState.LOG_METRICS)
        assert state_machine.current_state == AgentState.LOG_METRICS
    
    def test_transition_log_metrics_to_return_response(self, state_machine):
        """
        UC-1 Agent: Переход LOG_METRICS → RETURN_RESPONSE
        
        Given:
            - Состояние LOG_METRICS
            - Метрики залогированы
        When:
            - Вызывается transition_to(AgentState.RETURN_RESPONSE)
        Then:
            - Состояние изменяется на RETURN_RESPONSE
        """
        state_machine.transition_to(AgentState.LOG_METRICS)
        state_machine.transition_to(AgentState.RETURN_RESPONSE)
        assert state_machine.current_state == AgentState.RETURN_RESPONSE
    
    def test_transition_return_response_to_idle(self, state_machine):
        """
        UC-1 Agent: Переход RETURN_RESPONSE → IDLE
        
        Given:
            - Состояние RETURN_RESPONSE
            - Ответ отправлен пользователю
        When:
            - Вызывается transition_to(AgentState.IDLE)
        Then:
            - Состояние изменяется на IDLE
        """
        state_machine.transition_to(AgentState.RETURN_RESPONSE)
        state_machine.transition_to(AgentState.IDLE)
        assert state_machine.current_state == AgentState.IDLE
    
    def test_full_uc1_flow(self, state_machine):
        """
        UC-1 Agent: Полный flow для UC-1
        
        Given:
            - AgentStateMachine в состоянии IDLE
        When:
            - Выполняется полный flow: IDLE → VALIDATE_QUERY → RETRIEVE → METADATA_FILTER → GENERATE → VALIDATE_ANSWER → LOG_METRICS → RETURN_RESPONSE → IDLE
        Then:
            - Все переходы выполняются корректно
            - Финальное состояние = IDLE
        """
        # Полный flow для UC-1
        states = [
            AgentState.IDLE,
            AgentState.VALIDATE_QUERY,
            AgentState.RETRIEVE,
            AgentState.METADATA_FILTER,
            AgentState.GENERATE,
            AgentState.VALIDATE_ANSWER,
            AgentState.LOG_METRICS,
            AgentState.RETURN_RESPONSE,
            AgentState.IDLE
        ]
        
        for state in states:
            state_machine.transition_to(state)
            assert state_machine.current_state == state
    
    def test_state_history(self, state_machine):
        """
        UC-6 Agent: История состояний для трассировки
        
        Given:
            - AgentStateMachine выполняет переходы
        When:
            - Выполняются несколько переходов
        Then:
            - История состояний сохраняется
            - История доступна для DecisionLog
        """
        state_machine.transition_to(AgentState.VALIDATE_QUERY)
        state_machine.transition_to(AgentState.RETRIEVE)
        state_machine.transition_to(AgentState.GENERATE)
        
        # Проверяем, что история доступна
        assert hasattr(state_machine, 'state_history') or hasattr(state_machine, 'get_history')
        # История должна содержать пройденные состояния
        if hasattr(state_machine, 'state_history'):
            assert len(state_machine.state_history) >= 3

