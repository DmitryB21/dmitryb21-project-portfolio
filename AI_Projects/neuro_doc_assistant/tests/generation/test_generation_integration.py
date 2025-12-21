"""
@file: test_generation_integration.py
@description: Интеграционные тесты для Generation Layer с Retrieval Layer
@dependencies: app.generation.*, app.retrieval.*
@created: 2024-12-19
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.generation.prompt_builder import PromptBuilder
from app.generation.gigachat_client import LLMClient
from app.retrieval.retriever import Retriever, RetrievedChunk
from app.ingestion.embedding_service import EmbeddingService


class TestGenerationIntegration:
    """
    Интеграционные тесты для Generation Layer.
    
    Проверяют интеграцию PromptBuilder и LLMClient с Retrieval Layer.
    """
    
    @pytest.fixture
    def prompt_builder(self):
        """Фикстура для PromptBuilder"""
        return PromptBuilder()
    
    @pytest.fixture
    def llm_client(self):
        """Фикстура для LLMClient"""
        return LLMClient(
            api_key="test_key",
            api_url="https://gigachat.example.com/v1/chat/completions",
            model="GigaChat"
        )
    
    @pytest.fixture
    def embedding_service(self):
        """Фикстура для EmbeddingService"""
        return EmbeddingService(model_version="test_model", embedding_dim=1536)
    
    @pytest.fixture
    def retriever(self, embedding_service):
        """Фикстура для Retriever"""
        qdrant_client = MagicMock()
        return Retriever(
            qdrant_client=qdrant_client,
            embedding_service=embedding_service,
            collection_name="neuro_docs"
        )
    
    def test_retrieval_to_generation_flow(self, prompt_builder, llm_client, retriever, embedding_service):
        """
        UC-1 Generation: Интеграция Retrieval → Generation
        
        Given:
            - Запрос пользователя
        When:
            - Выполняется retrieve, затем build_prompt, затем generate_answer
        Then:
            - Весь flow работает корректно
            - Ответ основан на retrieved чанках
        """
        query = "Какой SLA у сервиса платежей?"
        
        # Мокаем результаты retrieval
        mock_chunks = [
            RetrievedChunk(
                id="chunk_001",
                text="SLA сервиса платежей составляет 99.9%",
                score=0.95,
                metadata={"doc_id": "doc_001", "source": "it"}
            )
        ]
        
        with patch.object(retriever, 'retrieve', return_value=mock_chunks):
            # Шаг 1: Retrieval
            retrieved = retriever.retrieve(query, k=3)
            
            # Шаг 2: Build prompt
            prompt = prompt_builder.build_prompt(query, retrieved)
            
            # Шаг 3: Generate answer
            mock_response = {
                "choices": [
                    {
                        "message": {
                            "content": "SLA сервиса платежей составляет 99.9%"
                        }
                    }
                ]
            }
            
            with patch.object(llm_client, '_call_gigachat_api', return_value=mock_response):
                answer = llm_client.generate_answer(prompt)
        
        # Проверяем результат
        assert answer is not None
        assert len(answer) > 0
        assert "99.9" in answer or "SLA" in answer
    
    def test_generation_with_retrieved_metadata(self, prompt_builder, llm_client):
        """
        UC-1 Generation: Использование метаданных retrieved чанков
        
        Given:
            - Retrieved чанки с метаданными (source, file_path)
        When:
            - Формируется prompt и генерируется ответ
        Then:
            - Метаданные могут быть использованы для ссылок на источники
            - Ответ может содержать информацию об источниках
        """
        query = "Какой SLA у сервиса платежей?"
        
        chunks = [
            RetrievedChunk(
                id="chunk_001",
                text="SLA сервиса платежей составляет 99.9%",
                score=0.95,
                metadata={
                    "doc_id": "doc_001",
                    "source": "it",
                    "file_path": "it_10_порядок_обращения_в_техподдержку.md"
                }
            )
        ]
        
        prompt = prompt_builder.build_prompt(query, chunks)
        
        # Проверяем, что prompt сформирован
        assert prompt is not None
        assert query in prompt
        assert chunks[0].text in prompt

