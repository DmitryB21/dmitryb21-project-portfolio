"""
Тесты для UC-2: Уточнение контекста (Agent Reasoning)

Given: Агент получает неоднозначный или слишком общий запрос
When: Пользователь задаёт вопрос без достаточного контекста
Then: Агент запрашивает уточнение без вызова retrieval и генерации ответа
"""

import pytest
from app.agent.agent import AgentController, AgentResponse
from app.agent.query_validator import QueryValidator
from app.retrieval.retriever import Retriever
from app.retrieval.metadata_filter import MetadataFilter
from app.generation.prompt_builder import PromptBuilder
from app.generation.gigachat_client import LLMClient
from app.evaluation.metrics import MetricsCollector
from app.evaluation.ragas_evaluator import RAGASEvaluator
from unittest.mock import MagicMock


@pytest.fixture
def agent_controller():
    """Фикстура для AgentController с моками"""
    retriever = MagicMock(spec=Retriever)
    metadata_filter = MetadataFilter()
    prompt_builder = PromptBuilder()
    llm_client = MagicMock(spec=LLMClient)
    metrics_collector = MetricsCollector()
    ragas_evaluator = RAGASEvaluator(mock_mode=True)
    
    controller = AgentController(
        retriever=retriever,
        metadata_filter=metadata_filter,
        prompt_builder=prompt_builder,
        llm_client=llm_client,
        metrics_collector=metrics_collector,
        ragas_evaluator=ragas_evaluator
    )
    
    return controller


class TestUC2Clarification:
    """Тесты для UC-2: Уточнение контекста"""
    
    def test_uc2_ambiguous_query_requests_clarification(self, agent_controller):
        """
        UC-2: Неоднозначный запрос должен привести к запросу уточнения
        
        Given: Агент инициализирован
        When: Пользователь задаёт неоднозначный вопрос "Какие есть лимиты?"
        Then: Агент возвращает уточняющий вопрос без вызова retrieval
        """
        query = "Какие есть лимиты?"
        
        response = agent_controller.ask(query)
        
        # Проверяем, что ответ содержит уточняющий вопрос
        assert response.metrics.get("needs_clarification") is True
        assert "уточните" in response.answer.lower() or "каких" in response.answer.lower()
        assert len(response.answer) > 20  # Должен быть развернутый вопрос
        
        # Проверяем, что retrieval не был вызван
        agent_controller.retriever.retrieve.assert_not_called()
        
        # Проверяем, что LLM не был вызван для генерации ответа
        agent_controller.llm_client.generate_answer.assert_not_called()
    
    def test_uc2_specific_query_proceeds_normally(self, agent_controller):
        """
        UC-2: Конкретный запрос должен обрабатываться нормально
        
        Given: Агент инициализирован
        When: Пользователь задаёт конкретный вопрос "Какой SLA у сервиса платежей?"
        Then: Агент обрабатывает запрос через полный pipeline (retrieval + generation)
        """
        query = "Какой SLA у сервиса платежей?"
        
        # Настраиваем моки для нормальной обработки
        agent_controller.retriever.retrieve.return_value = []
        agent_controller.llm_client.generate_answer.return_value = "SLA составляет 99.9%"
        
        response = agent_controller.ask(query)
        
        # Проверяем, что retrieval был вызван
        agent_controller.retriever.retrieve.assert_called_once()
        
        # Проверяем, что не требуется уточнение
        assert response.metrics.get("needs_clarification") is not True
    
    def test_uc2_empty_query_requests_clarification(self, agent_controller):
        """
        UC-2: Пустой запрос должен привести к запросу уточнения
        
        Given: Агент инициализирован
        When: Пользователь отправляет пустой запрос
        Then: Агент возвращает сообщение с просьбой уточнить вопрос
        """
        query = ""
        
        response = agent_controller.ask(query)
        
        # Проверяем, что ответ содержит просьбу уточнить
        assert "уточните" in response.answer.lower() or "вопрос" in response.answer.lower()
        
        # Проверяем, что retrieval не был вызван
        agent_controller.retriever.retrieve.assert_not_called()
    
    def test_uc2_very_short_query_requests_clarification(self, agent_controller):
        """
        UC-2: Очень короткий запрос должен привести к запросу уточнения
        
        Given: Агент инициализирован
        When: Пользователь задаёт очень короткий вопрос "Лимиты"
        Then: Агент возвращает уточняющий вопрос
        """
        query = "Лимиты"
        
        response = agent_controller.ask(query)
        
        # Проверяем, что требуется уточнение
        assert response.metrics.get("needs_clarification") is True
        assert len(response.answer) > 10
        
        # Проверяем, что retrieval не был вызван
        agent_controller.retriever.retrieve.assert_not_called()

