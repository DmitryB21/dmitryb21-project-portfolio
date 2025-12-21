"""
@file: test_decision_log.py
@description: Тесты для DecisionLog - трассировка решений агента
@dependencies: app.agent.decision_log
@created: 2024-12-19
"""

import pytest
from app.agent.decision_log import DecisionLog, DecisionEntry


class TestDecisionLog:
    """
    Тесты для DecisionLog компонента.
    
    DecisionLog отвечает за:
    - Трассировку каждого шага агента
    - Логирование решений и переходов состояний
    - Сохранение истории для анализа и отладки
    """
    
    @pytest.fixture
    def decision_log(self):
        """Фикстура для создания экземпляра DecisionLog"""
        return DecisionLog()
    
    def test_log_decision(self, decision_log):
        """
        UC-6 Agent: Логирование решения
        
        Given:
            - DecisionLog создан
        When:
            - Вызывается log_decision()
        Then:
            - Решение добавляется в лог
            - Лог доступен для получения
        """
        decision_log.log_decision(
            state="RETRIEVE",
            action="retrieve_chunks",
            input_data="query: Какой SLA?",
            output_data="3 chunks retrieved",
            metadata={"k": 3, "latency_ms": 150}
        )
        
        assert len(decision_log.get_log()) > 0
    
    def test_log_contains_state_transitions(self, decision_log):
        """
        UC-1 Agent: Лог содержит переходы состояний
        
        Given:
            - DecisionLog создан
        When:
            - Логируются переходы состояний
        Then:
            - Лог содержит все переходы
            - Порядок переходов сохранён
        """
        decision_log.log_decision("IDLE", "receive_query", "query", None, {})
        decision_log.log_decision("VALIDATE_QUERY", "validate", "query", "valid", {})
        decision_log.log_decision("RETRIEVE", "retrieve", "query", "chunks", {})
        
        log = decision_log.get_log()
        assert len(log) == 3
        assert log[0].state == "IDLE"
        assert log[1].state == "VALIDATE_QUERY"
        assert log[2].state == "RETRIEVE"
    
    def test_log_contains_metadata(self, decision_log):
        """
        UC-6 Agent: Лог содержит метаданные
        
        Given:
            - DecisionLog создан
        When:
            - Логируется решение с метаданными
        Then:
            - Метаданные сохраняются в логе
            - Метаданные доступны для анализа
        """
        decision_log.log_decision(
            state="RETRIEVE",
            action="retrieve_chunks",
            input_data="query",
            output_data="chunks",
            metadata={"k": 3, "latency_ms": 150, "experiment_id": "exp_001"}
        )
        
        log = decision_log.get_log()
        assert len(log) > 0
        assert "k" in log[0].metadata
        assert "latency_ms" in log[0].metadata
        assert log[0].metadata["k"] == 3
    
    def test_log_clear(self, decision_log):
        """
        UC-6 Agent: Очистка лога
        
        Given:
            - DecisionLog с записями
        When:
            - Вызывается clear()
        Then:
            - Лог очищается
            - get_log() возвращает пустой список
        """
        decision_log.log_decision("RETRIEVE", "retrieve", "query", "chunks", {})
        assert len(decision_log.get_log()) > 0
        
        decision_log.clear()
        assert len(decision_log.get_log()) == 0
    
    def test_log_export(self, decision_log):
        """
        UC-6 Agent: Экспорт лога для анализа
        
        Given:
            - DecisionLog с записями
        When:
            - Вызывается export_log()
        Then:
            - Лог экспортируется в структурированном формате (JSON или dict)
            - Экспорт может быть использован для анализа экспериментов
        """
        decision_log.log_decision("RETRIEVE", "retrieve", "query", "chunks", {"k": 3})
        decision_log.log_decision("GENERATE", "generate", "prompt", "answer", {})
        
        exported = decision_log.export_log()
        
        assert exported is not None
        assert isinstance(exported, (list, dict))
        assert len(exported) > 0

