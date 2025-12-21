"""
Тесты для QueryValidator - валидация запросов и определение необходимости уточнения контекста (UC-2)
"""

import pytest
from app.agent.query_validator import QueryValidator, QueryValidationResult


class TestQueryValidator:
    """Тесты для QueryValidator"""
    
    @pytest.fixture
    def validator(self):
        """Фикстура для QueryValidator"""
        return QueryValidator()
    
    def test_validate_specific_query(self, validator):
        """Тест: валидация конкретного запроса (не требует уточнения)"""
        query = "Какой SLA у сервиса платежей?"
        result = validator.validate(query)
        
        assert result.needs_clarification is False
        assert result.is_valid is True
        assert result.clarification_question is None
    
    def test_validate_ambiguous_query(self, validator):
        """Тест: валидация неоднозначного запроса (требует уточнения)"""
        query = "Какие есть лимиты?"
        result = validator.validate(query)
        
        assert result.needs_clarification is True
        assert result.is_valid is True
        assert result.clarification_question is not None
        assert "лимит" in result.clarification_question.lower() or "какой" in result.clarification_question.lower()
    
    def test_validate_too_general_query(self, validator):
        """Тест: валидация слишком общего запроса"""
        query = "Что есть?"
        result = validator.validate(query)
        
        assert result.needs_clarification is True
        assert result.clarification_question is not None
    
    def test_validate_very_short_query(self, validator):
        """Тест: валидация очень короткого запроса"""
        query = "Лимиты"
        result = validator.validate(query)
        
        assert result.needs_clarification is True
    
    def test_validate_query_with_context(self, validator):
        """Тест: валидация запроса с достаточным контекстом"""
        query = "Какие лимиты на количество запросов к API платежей в секунду?"
        result = validator.validate(query)
        
        assert result.needs_clarification is False
    
    def test_validate_empty_query(self, validator):
        """Тест: валидация пустого запроса"""
        query = ""
        result = validator.validate(query)
        
        assert result.is_valid is False
        assert result.needs_clarification is True
    
    def test_validate_query_with_multiple_ambiguous_terms(self, validator):
        """Тест: валидация запроса с несколькими неоднозначными терминами"""
        query = "Какие правила?"
        result = validator.validate(query)
        
        assert result.needs_clarification is True
    
    def test_clarification_question_format(self, validator):
        """Тест: формат уточняющего вопроса"""
        query = "Лимиты"
        result = validator.validate(query)
        
        if result.needs_clarification:
            assert result.clarification_question is not None
            assert len(result.clarification_question) > 10  # Должен быть развернутый вопрос
            assert "?" in result.clarification_question or "уточните" in result.clarification_question.lower()

