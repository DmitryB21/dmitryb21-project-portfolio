"""
Тесты для AdminAPI (GET /metrics, GET /logs)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, status
from datetime import datetime

from app.agent.agent import AgentController
from app.agent.decision_log import DecisionLog, DecisionEntry
from app.api.admin import create_admin_router


@pytest.fixture
def mock_agent_controller():
    """Фикстура для мокирования AgentController"""
    controller = Mock(spec=AgentController)
    controller.decision_log = DecisionLog()
    # Добавляем тестовые записи в лог
    controller.decision_log.log_decision(
        state="RETRIEVE",
        action="retrieve_chunks",
        input_data={"query": "test", "k": 3},
        output_data={"chunks": ["chunk1", "chunk2"]},
        metadata={"latency_ms": 150}
    )
    return controller


@pytest.fixture
def app(mock_agent_controller):
    """Фикстура для FastAPI приложения с AdminAPI"""
    app = FastAPI()
    admin_router = create_admin_router(agent_controller=mock_agent_controller)
    app.include_router(admin_router, prefix="/admin", tags=["admin"])
    return app


@pytest.fixture
def client(app):
    """Фикстура для тестового клиента"""
    return TestClient(app)


class TestAdminAPI:
    """Тесты для AdminAPI endpoints"""
    
    def test_get_metrics(self, client, mock_agent_controller):
        """Тест GET /admin/metrics endpoint"""
        response = client.get("/admin/metrics")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "system" in data
        assert "agent" in data
        # Проверяем наличие базовых метрик
        assert "timestamp" in data["system"]
    
    def test_get_logs(self, client, mock_agent_controller):
        """Тест GET /admin/logs endpoint"""
        response = client.get("/admin/logs")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "logs" in data
        assert isinstance(data["logs"], list)
        assert len(data["logs"]) > 0
        # Проверяем структуру записи лога
        log_entry = data["logs"][0]
        assert "timestamp" in log_entry
        assert "state" in log_entry
        assert "action" in log_entry
    
    def test_get_logs_with_limit(self, client, mock_agent_controller):
        """Тест GET /admin/logs с параметром limit"""
        response = client.get("/admin/logs?limit=1")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["logs"]) <= 1
    
    def test_get_logs_empty(self, client):
        """Тест GET /admin/logs с пустым логом"""
        empty_controller = Mock(spec=AgentController)
        empty_controller.decision_log = DecisionLog()
        
        app = FastAPI()
        admin_router = create_admin_router(agent_controller=empty_controller)
        app.include_router(admin_router, prefix="/admin", tags=["admin"])
        client = TestClient(app)
        
        response = client.get("/admin/logs")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["logs"] == []

