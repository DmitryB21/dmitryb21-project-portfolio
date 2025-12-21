"""
Тесты для QueryAPI (POST /ask, GET /health)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, status

from app.agent.agent import AgentController, AgentResponse, Source
from app.api.chat import create_app, QueryRequest, QueryResponse


@pytest.fixture
def mock_agent_controller():
    """Фикстура для мокирования AgentController"""
    async def mock_ask(query: str, k: int = 3, ground_truth_relevant=None):
        return AgentResponse(
            answer="SLA сервиса платежей составляет 99.9%",
            sources=[
                Source(
                    text="SLA сервиса платежей: 99.9%",
                    id="chunk_1",
                    metadata={"doc_id": "doc_1", "category": "it", "file_path": "it/payments.md"}
                )
            ],
            metrics={"precision_at_3": 0.85, "latency_ms": 1200}
        )
    
    controller = Mock(spec=AgentController)
    controller.ask = mock_ask
    return controller


@pytest.fixture
def app(mock_agent_controller):
    """Фикстура для FastAPI приложения"""
    app = create_app(agent_controller=mock_agent_controller)
    return app


@pytest.fixture
def client(app):
    """Фикстура для тестового клиента"""
    return TestClient(app)


class TestQueryAPI:
    """Тесты для QueryAPI endpoints"""
    
    def test_post_ask_success(self, client, mock_agent_controller):
        """Тест успешного запроса через POST /ask"""
        request_data = {
            "query": "Какой SLA у сервиса платежей?",
            "k": 3,
            "ground_truth_relevant": None
        }
        
        response = client.post("/ask", json=request_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "metrics" in data
        assert data["answer"] == "SLA сервиса платежей составляет 99.9%"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "SLA сервиса платежей: 99.9%"
        assert "precision_at_3" in data["metrics"]
        
        # Проверка вызова AgentController (async функции вызываются через call_soon)
        # В тестах с TestClient async функции выполняются синхронно
    
    def test_post_ask_with_ground_truth(self, client, mock_agent_controller):
        """Тест запроса с ground_truth_relevant"""
        request_data = {
            "query": "Какой SLA у сервиса платежей?",
            "k": 5,
            "ground_truth_relevant": ["chunk_1", "chunk_2"]
        }
        
        response = client.post("/ask", json=request_data)
        
        assert response.status_code == status.HTTP_200_OK
        # Проверяем, что ответ содержит корректные данные
        data = response.json()
        assert "answer" in data
    
    def test_post_ask_missing_query(self, client):
        """Тест запроса без обязательного поля query"""
        request_data = {"k": 3}
        
        response = client.post("/ask", json=request_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_post_ask_empty_query(self, client):
        """Тест запроса с пустым query"""
        request_data = {"query": "", "k": 3}
        
        response = client.post("/ask", json=request_data)
        
        # Pydantic валидация возвращает 422 для пустых строк
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_post_ask_agent_error(self, client, mock_agent_controller):
        """Тест обработки ошибки от AgentController"""
        async def mock_ask_error(*args, **kwargs):
            raise Exception("Agent error")
        
        mock_agent_controller.ask = mock_ask_error
        
        request_data = {
            "query": "Какой SLA у сервиса платежей?",
            "k": 3
        }
        
        response = client.post("/ask", json=request_data)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data
        assert "Agent error" in data["detail"]
    
    def test_get_health(self, client):
        """Тест GET /health endpoint"""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_post_ask_default_k(self, client, mock_agent_controller):
        """Тест запроса с дефолтным значением k"""
        request_data = {
            "query": "Какой SLA у сервиса платежей?"
        }
        
        response = client.post("/ask", json=request_data)
        
        assert response.status_code == status.HTTP_200_OK
        # Проверяем, что ответ содержит корректные данные
        data = response.json()
        assert "answer" in data

