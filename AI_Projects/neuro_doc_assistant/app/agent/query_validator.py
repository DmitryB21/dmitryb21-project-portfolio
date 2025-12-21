"""
@file: query_validator.py
@description: QueryValidator - валидация запросов и определение необходимости уточнения контекста (UC-2)
@dependencies: typing, re
@created: 2024-12-19
"""

from typing import Optional
from dataclasses import dataclass
import re


@dataclass
class QueryValidationResult:
    """
    Результат валидации запроса.
    
    Attributes:
        is_valid: Запрос валиден (не пустой)
        needs_clarification: Требуется ли уточнение контекста
        clarification_question: Уточняющий вопрос (если needs_clarification=True)
        reason: Причина необходимости уточнения (опционально)
    """
    is_valid: bool
    needs_clarification: bool
    clarification_question: Optional[str] = None
    reason: Optional[str] = None


class QueryValidator:
    """
    Валидатор запросов для определения необходимости уточнения контекста.
    
    Отвечает за:
    - Определение неоднозначных или слишком общих запросов
    - Генерацию уточняющих вопросов
    - Валидацию пустых или некорректных запросов
    """
    
    # Паттерны для определения неоднозначных запросов
    AMBIGUOUS_PATTERNS = [
        r'^какие\s+(есть|существуют|имеются)\s*\?*$',
        r'^что\s+(есть|такое|это)\s*\?*$',
        r'^какие\s+(лимиты|правила|политики|документы)\s*\?*$',
        r'^(лимиты|правила|политики|документы)\s*\?*$',
        r'^какие\s+есть\s+лимиты\s*\?*$',  # "Какие есть лимиты?"
    ]
    
    # Минимальная длина запроса для достаточного контекста
    MIN_CONTEXT_LENGTH = 20
    
    # Ключевые слова, указывающие на достаточный контекст
    CONTEXT_KEYWORDS = [
        'api', 'сервис', 'система', 'документ', 'процесс', 'процедура',
        'sla', 'лимит', 'ограничение', 'правило', 'политика',
        'платеж', 'запрос', 'секунда', 'минута', 'час', 'день'
    ]
    
    def __init__(self):
        """Инициализация QueryValidator"""
        self.ambiguous_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.AMBIGUOUS_PATTERNS]
    
    def validate(self, query: str) -> QueryValidationResult:
        """
        Валидирует запрос и определяет, требуется ли уточнение контекста.
        
        Args:
            query: Запрос пользователя
        
        Returns:
            QueryValidationResult с результатами валидации
        """
        # Проверка на пустой запрос
        if not query or not query.strip():
            return QueryValidationResult(
                is_valid=False,
                needs_clarification=True,
                clarification_question="Пожалуйста, уточните ваш вопрос.",
                reason="Пустой запрос"
            )
        
        query = query.strip()
        query_lower = query.lower()
        
        # Проверка на неоднозначные паттерны
        for pattern in self.ambiguous_patterns:
            if pattern.match(query_lower):
                clarification = self._generate_clarification_question(query)
                return QueryValidationResult(
                    is_valid=True,
                    needs_clarification=True,
                    clarification_question=clarification,
                    reason="Неоднозначный запрос"
                )
        
        # Дополнительная проверка: если запрос содержит только общие слова без контекста
        general_words = ['какие', 'что', 'есть', 'лимиты', 'правила', 'политики', 'документы']
        words = re.findall(r'\b\w+\b', query_lower)
        if len(words) <= 3 and all(word in general_words for word in words):
            clarification = self._generate_clarification_question(query)
            return QueryValidationResult(
                is_valid=True,
                needs_clarification=True,
                clarification_question=clarification,
                reason="Недостаточно контекста"
            )
        
        # Проверка на слишком короткий запрос
        if len(query) < self.MIN_CONTEXT_LENGTH:
            # Проверяем, есть ли ключевые слова контекста
            has_context = any(keyword in query.lower() for keyword in self.CONTEXT_KEYWORDS)
            if not has_context:
                clarification = self._generate_clarification_question(query)
                return QueryValidationResult(
                    is_valid=True,
                    needs_clarification=True,
                    clarification_question=clarification,
                    reason="Недостаточно контекста"
                )
        
        # Запрос валиден и не требует уточнения
        return QueryValidationResult(
            is_valid=True,
            needs_clarification=False,
            clarification_question=None,
            reason=None
        )
    
    def _generate_clarification_question(self, query: str) -> str:
        """
        Генерирует уточняющий вопрос на основе исходного запроса.
        
        Args:
            query: Исходный запрос пользователя
        
        Returns:
            Уточняющий вопрос
        """
        query_lower = query.lower()
        
        # Определяем тип уточнения на основе ключевых слов
        if 'лимит' in query_lower:
            return "Уточните, пожалуйста, о каких лимитах идет речь? Например, лимиты на количество запросов к API, лимиты на размер данных или другие ограничения?"
        
        if 'правил' in query_lower or 'политик' in query_lower:
            return "Уточните, пожалуйста, о каких правилах или политиках вы спрашиваете? Например, правила безопасности, политики работы с данными или другие?"
        
        if 'документ' in query_lower:
            return "Уточните, пожалуйста, о каких документах идет речь? Например, документы для оформления отпуска, документы для доступа к системе или другие?"
        
        if 'какие' in query_lower and 'есть' in query_lower:
            return "Уточните, пожалуйста, о чем именно вы спрашиваете? Например, какие сервисы, какие процессы, какие документы?"
        
        # Общий уточняющий вопрос
        return "Уточните, пожалуйста, ваш вопрос. Добавьте больше контекста, чтобы я мог дать точный ответ."

