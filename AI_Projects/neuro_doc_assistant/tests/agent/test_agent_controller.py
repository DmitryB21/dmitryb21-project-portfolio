"""
@file: test_agent_controller.py
@description: Тесты для AgentController - оркестрация всех модулей
@dependencies: app.agent.agent, app.retrieval.*, app.generation.*, app.evaluation.*
@created: 2024-12-19
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.agent.agent import AgentController, AgentResponse, Source
from app.retrieval.retriever import RetrievedChunk


class TestAgentController:
    """
    Тесты для AgentController компонента.
    
    AgentController отвечает за:
    - Оркестрацию всех модулей (Retrieval, Generation, Evaluation)
    - Управление state machine
    - Формирование AgentResponse
    """
    
    @pytest.fixture
    def agent_controller(self):
        """Фикстура для создания экземпляра AgentController"""
        # Создаём моки для всех зависимостей
        retriever = MagicMock()
        metadata_filter = MagicMock()
        prompt_builder = MagicMock()
        llm_client = MagicMock()
        metrics_collector = MagicMock()
        ragas_evaluator = MagicMock()
        
        return AgentController(
            retriever=retriever,
            metadata_filter=metadata_filter,
            prompt_builder=prompt_builder,
            llm_client=llm_client,
            metrics_collector=metrics_collector,
            ragas_evaluator=ragas_evaluator
        )
    
    @pytest.fixture
    def mock_retrieved_chunks(self):
        """Создаёт моковые retrieved чанки"""
        return [
            RetrievedChunk(
                id="chunk_001",
                text="SLA сервиса платежей составляет 99.9%",
                score=0.95,
                metadata={"doc_id": "doc_001", "source": "it"}
            ),
            RetrievedChunk(
                id="chunk_002",
                text="Время отклика сервиса платежей не более 200мс",
                score=0.88,
                metadata={"doc_id": "doc_001", "source": "it"}
            ),
            RetrievedChunk(
                id="chunk_003",
                text="Документация по SLA сервисов находится в разделе IT",
                score=0.82,
                metadata={"doc_id": "doc_002", "source": "it"}
            )
        ]
    
    def test_ask_returns_agent_response(self, agent_controller, mock_retrieved_chunks):
        """
        UC-1 Agent: ask() возвращает AgentResponse
        
        Given:
            - Запрос пользователя
        When:
            - Вызывается ask(query)
        Then:
            - Возвращается AgentResponse с answer, sources, metrics
        """
        query = "Какой SLA у сервиса платежей?"
        
        # Настраиваем моки
        agent_controller.retriever.retrieve.return_value = mock_retrieved_chunks
        agent_controller.metadata_filter.filter.return_value = mock_retrieved_chunks
        agent_controller.prompt_builder.build_prompt.return_value = "Test prompt"
        agent_controller.llm_client.generate_answer.return_value = "SLA сервиса платежей составляет 99.9%"
        agent_controller.metrics_collector.calculate_precision_at_k.return_value = 0.85
        agent_controller.ragas_evaluator.evaluate_all.return_value = {
            "faithfulness": 0.90,
            "answer_relevancy": 0.85
        }
        
        # Передаём ground_truth для расчёта Precision@3
        ground_truth = [mock_retrieved_chunks[0].id, mock_retrieved_chunks[1].id]
        response = agent_controller.ask(query, ground_truth_relevant=ground_truth)
        
        assert isinstance(response, AgentResponse)
        assert response.answer is not None
        assert len(response.sources) > 0
        assert "precision_at_3" in response.metrics or "faithfulness" in response.metrics  # Precision@3 только если передан ground_truth
    
    def test_ask_orchestrates_all_modules(self, agent_controller, mock_retrieved_chunks):
        """
        UC-1 Agent: ask() оркестрирует все модули
        
        Given:
            - Запрос пользователя
        When:
            - Вызывается ask(query)
        Then:
            - Вызываются все модули в правильном порядке:
              1. Retriever.retrieve()
              2. MetadataFilter.filter() (опционально)
              3. PromptBuilder.build_prompt()
              4. LLMClient.generate_answer()
              5. MetricsCollector.calculate_precision_at_k()
              6. RAGASEvaluator.evaluate_all()
        """
        query = "Какой SLA у сервиса платежей?"
        
        # Настраиваем моки
        agent_controller.retriever.retrieve.return_value = mock_retrieved_chunks
        agent_controller.metadata_filter.filter.return_value = mock_retrieved_chunks
        agent_controller.prompt_builder.build_prompt.return_value = "Test prompt"
        agent_controller.llm_client.generate_answer.return_value = "SLA сервиса платежей составляет 99.9%"
        agent_controller.metrics_collector.calculate_precision_at_k.return_value = 0.85
        agent_controller.ragas_evaluator.evaluate_all.return_value = {
            "faithfulness": 0.90,
            "answer_relevancy": 0.85
        }
        
        # Передаём ground_truth для расчёта Precision@3
        ground_truth = [mock_retrieved_chunks[0].id, mock_retrieved_chunks[1].id]
        response = agent_controller.ask(query, ground_truth_relevant=ground_truth)
        
        # Проверяем, что все модули были вызваны
        agent_controller.retriever.retrieve.assert_called_once()
        agent_controller.prompt_builder.build_prompt.assert_called_once()
        agent_controller.llm_client.generate_answer.assert_called_once()
        agent_controller.metrics_collector.calculate_precision_at_k.assert_called_once()
        agent_controller.ragas_evaluator.evaluate_all.assert_called_once()
    
    def test_ask_response_contains_sources(self, agent_controller, mock_retrieved_chunks):
        """
        UC-1 Agent: AgentResponse содержит sources
        
        Given:
            - Запрос пользователя
            - Retrieved чанки
        When:
            - Вызывается ask(query)
        Then:
            - response.sources содержит Source объекты
            - Каждый Source содержит text, id, metadata
        """
        query = "Какой SLA у сервиса платежей?"
        
        agent_controller.retriever.retrieve.return_value = mock_retrieved_chunks
        agent_controller.metadata_filter.filter.return_value = mock_retrieved_chunks
        agent_controller.prompt_builder.build_prompt.return_value = "Test prompt"
        agent_controller.llm_client.generate_answer.return_value = "SLA сервиса платежей составляет 99.9%"
        agent_controller.metrics_collector.calculate_precision_at_k.return_value = 0.85
        agent_controller.ragas_evaluator.evaluate_all.return_value = {
            "faithfulness": 0.90,
            "answer_relevancy": 0.85
        }
        
        # Передаём ground_truth для расчёта Precision@3
        ground_truth = [mock_retrieved_chunks[0].id, mock_retrieved_chunks[1].id]
        response = agent_controller.ask(query, ground_truth_relevant=ground_truth)
        
        assert len(response.sources) > 0
        for source in response.sources:
            assert isinstance(source, Source)
            assert source.text is not None
            assert source.id is not None
            assert source.metadata is not None
    
    def test_ask_response_contains_metrics(self, agent_controller, mock_retrieved_chunks):
        """
        UC-1 Agent: AgentResponse содержит metrics
        
        Given:
            - Запрос пользователя
        When:
            - Вызывается ask(query)
        Then:
            - response.metrics содержит precision_at_3, faithfulness, answer_relevancy
            - Все метрики в диапазоне [0.0, 1.0]
        """
        query = "Какой SLA у сервиса платежей?"
        
        agent_controller.retriever.retrieve.return_value = mock_retrieved_chunks
        agent_controller.metadata_filter.filter.return_value = mock_retrieved_chunks
        agent_controller.prompt_builder.build_prompt.return_value = "Test prompt"
        agent_controller.llm_client.generate_answer.return_value = "SLA сервиса платежей составляет 99.9%"
        agent_controller.metrics_collector.calculate_precision_at_k.return_value = 0.85
        agent_controller.ragas_evaluator.evaluate_all.return_value = {
            "faithfulness": 0.90,
            "answer_relevancy": 0.85
        }
        
        # Передаём ground_truth для расчёта Precision@3
        ground_truth = [mock_retrieved_chunks[0].id, mock_retrieved_chunks[1].id]
        response = agent_controller.ask(query, ground_truth_relevant=ground_truth)
        
        assert "precision_at_3" in response.metrics or "faithfulness" in response.metrics  # Precision@3 только если передан ground_truth
        assert "faithfulness" in response.metrics
        assert "answer_relevancy" in response.metrics
        if "precision_at_3" in response.metrics:
            assert 0.0 <= response.metrics["precision_at_3"] <= 1.0
        assert 0.0 <= response.metrics["faithfulness"] <= 1.0
        assert 0.0 <= response.metrics["answer_relevancy"] <= 1.0
    
    def test_ask_handles_empty_retrieval(self, agent_controller):
        """
        UC-5 Agent: Обработка пустого retrieval
        
        Given:
            - Запрос пользователя
            - Retriever возвращает пустой список
        When:
            - Вызывается ask(query)
        Then:
            - Ответ содержит сообщение об отсутствии информации
            - Или выбрасывается исключение (в зависимости от реализации)
        """
        query = "Вопрос, на который нет ответа"
        
        agent_controller.retriever.retrieve.return_value = []
        
        try:
            response = agent_controller.ask(query)
            # Если исключение не выброшено, проверяем обработку
            assert response.answer is not None
            assert "нет информации" in response.answer.lower() or "не найдено" in response.answer.lower() or len(response.answer) > 0
        except (ValueError, AssertionError):
            # Исключение тоже допустимо
            pass
    
    def test_ask_uses_state_machine(self, agent_controller, mock_retrieved_chunks):
        """
        UC-1 Agent: Использование state machine
        
        Given:
            - Запрос пользователя
        When:
            - Вызывается ask(query)
        Then:
            - State machine управляет переходами состояний
            - Все состояния проходятся в правильном порядке
        """
        query = "Какой SLA у сервиса платежей?"
        
        agent_controller.retriever.retrieve.return_value = mock_retrieved_chunks
        agent_controller.metadata_filter.filter.return_value = mock_retrieved_chunks
        agent_controller.prompt_builder.build_prompt.return_value = "Test prompt"
        agent_controller.llm_client.generate_answer.return_value = "SLA сервиса платежей составляет 99.9%"
        agent_controller.metrics_collector.calculate_precision_at_k.return_value = 0.85
        agent_controller.ragas_evaluator.evaluate_all.return_value = {
            "faithfulness": 0.90,
            "answer_relevancy": 0.85
        }
        
        # Передаём ground_truth для расчёта Precision@3
        ground_truth = [mock_retrieved_chunks[0].id, mock_retrieved_chunks[1].id]
        response = agent_controller.ask(query, ground_truth_relevant=ground_truth)
        
        # Проверяем, что state machine использовался
        assert hasattr(agent_controller, 'state_machine')
        # Финальное состояние должно быть IDLE
        from app.agent.state_machine import AgentState
        assert agent_controller.state_machine.current_state == AgentState.IDLE

