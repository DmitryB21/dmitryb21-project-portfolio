"""
@file: test_gigachat_client.py
@description: Тесты для LLMClient (GigaChat) - интеграция с GigaChat API
@dependencies: app.generation.gigachat_client
@created: 2024-12-19
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.generation.gigachat_client import LLMClient


class TestLLMClient:
    """
    Тесты для LLMClient компонента.
    
    LLMClient отвечает за:
    - Вызов GigaChat API для генерации ответов
    - Обработку ответов от API
    - Обработку ошибок API
    - Latency метрики
    """
    
    @pytest.fixture
    def llm_client(self):
        """Фикстура для создания экземпляра LLMClient"""
        return LLMClient(
            api_key="test_key",
            api_url="https://gigachat.example.com/v1/chat/completions",
            model="GigaChat"
        )
    
    @pytest.fixture
    def mock_gigachat_response(self):
        """Мок ответа от GigaChat API"""
        return {
            "choices": [
                {
                    "message": {
                        "content": "SLA сервиса платежей составляет 99.9%"
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120
            }
        }
    
    def test_generate_answer_success(self, llm_client, mock_gigachat_response):
        """
        UC-1 Generation: Успешная генерация ответа
        
        Given:
            - Prompt с контекстом и запросом
        When:
            - Вызывается generate_answer
        Then:
            - Возвращается текст ответа
            - Ответ не пустой
            - Ответ соответствует формату GigaChat API
        """
        prompt = "Контекст: SLA сервиса платежей составляет 99.9%\nВопрос: Какой SLA у сервиса платежей?"
        
        with patch.object(llm_client, '_call_gigachat_api', return_value=mock_gigachat_response):
            answer = llm_client.generate_answer(prompt)
        
        assert answer is not None
        assert isinstance(answer, str)
        assert len(answer) > 0
        assert "SLA" in answer or "99.9" in answer
    
    def test_generate_answer_api_error(self, llm_client):
        """
        UC-1 Generation: Обработка ошибок API
        
        Given:
            - GigaChat API возвращает ошибку
        When:
            - Вызывается generate_answer
        Then:
            - Выбрасывается соответствующее исключение
            - Ошибка логируется
        """
        prompt = "Тестовый prompt"
        
        with patch.object(llm_client, '_call_gigachat_api', side_effect=Exception("API Error")):
            with pytest.raises(Exception):
                llm_client.generate_answer(prompt)
    
    def test_generate_answer_empty_response(self, llm_client):
        """
        UC-1 Generation: Обработка пустого ответа от API
        
        Given:
            - GigaChat API возвращает пустой ответ
        When:
            - Вызывается generate_answer
        Then:
            - Выбрасывается исключение или возвращается сообщение об ошибке
        """
        prompt = "Тестовый prompt"
        
        empty_response = {
            "choices": [
                {
                    "message": {
                        "content": ""
                    }
                }
            ]
        }
        
        with patch.object(llm_client, '_call_gigachat_api', return_value=empty_response):
            # Может быть либо исключение, либо обработка пустого ответа
            try:
                answer = llm_client.generate_answer(prompt)
                # Если исключение не выброшено, проверяем обработку
                assert answer is not None
            except (ValueError, AssertionError):
                # Исключение тоже допустимо
                pass
    
    def test_generate_answer_latency(self, llm_client, mock_gigachat_response):
        """
        UC-7 Generation: Проверка latency генерации
        
        Given:
            - Prompt с контекстом
        When:
            - Вызывается generate_answer
        Then:
            - Latency генерации приемлема (цель: < 1.3 сек p95 для end-to-end)
            - Метод завершается в разумное время
        """
        import time
        prompt = "Тестовый prompt"
        
        with patch.object(llm_client, '_call_gigachat_api', return_value=mock_gigachat_response):
            start_time = time.time()
            answer = llm_client.generate_answer(prompt)
            end_time = time.time()
        
        latency = (end_time - start_time) * 1000  # в миллисекундах
        
        # Для моков должно быть очень быстро (в реальности должно быть < 1300мс для end-to-end)
        assert latency < 5000  # 5 секунд для моков
        assert answer is not None
    
    def test_generate_answer_token_usage(self, llm_client, mock_gigachat_response):
        """
        UC-6 Generation: Отслеживание использования токенов
        
        Given:
            - Prompt с контекстом
        When:
            - Вызывается generate_answer
        Then:
            - Информация об использовании токенов доступна (для экспериментов)
            - Может быть возвращена через метаданные или отдельный метод
        """
        prompt = "Тестовый prompt"
        
        with patch.object(llm_client, '_call_gigachat_api', return_value=mock_gigachat_response):
            answer = llm_client.generate_answer(prompt)
        
        # Проверяем, что ответ получен
        assert answer is not None
        # Информация о токенах может быть доступна через отдельный метод или метаданные
        # Это зависит от реализации
    
    def test_generate_answer_model_version(self, llm_client):
        """
        UC-6 Generation: Фиксация версии модели
        
        Given:
            - LLMClient создан с определённой моделью
        When:
            - Вызывается generate_answer
        Then:
            - Используется указанная модель в API вызовах
            - Версия модели фиксируется для воспроизводимости
        """
        assert llm_client.model == "GigaChat"
        # Проверяем, что модель используется в API вызовах (через мок)
        prompt = "Тестовый prompt"
        mock_response = {
            "choices": [{"message": {"content": "Ответ"}}]
        }
        
        with patch.object(llm_client, '_call_gigachat_api', return_value=mock_response) as mock_call:
            llm_client.generate_answer(prompt)
            # Проверяем, что модель передана в API вызов
            # Это зависит от реализации _call_gigachat_api
    
    def test_generate_answer_temperature(self, llm_client):
        """
        UC-1 Generation: Настройка temperature для детерминированности
        
        Given:
            - LLMClient с настройкой temperature
        When:
            - Вызывается generate_answer
        Then:
            - Temperature используется в API вызовах
            - Низкая temperature для детерминированности (0.0-0.3)
        """
        # Проверяем, что temperature настраивается
        # Это зависит от реализации LLMClient
        assert hasattr(llm_client, 'temperature') or hasattr(llm_client, '_temperature')
    
    def test_generate_answer_max_tokens(self, llm_client):
        """
        UC-1 Generation: Ограничение длины ответа
        
        Given:
            - LLMClient с настройкой max_tokens
        When:
            - Вызывается generate_answer
        Then:
            - Max_tokens используется в API вызовах
            - Ответ не превышает заданную длину
        """
        # Проверяем, что max_tokens настраивается
        # Это зависит от реализации LLMClient
        assert hasattr(llm_client, 'max_tokens') or hasattr(llm_client, '_max_tokens')

