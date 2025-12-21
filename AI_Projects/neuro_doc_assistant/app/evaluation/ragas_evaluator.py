"""
@file: ragas_evaluator.py
@description: RAGASEvaluator - интеграция с RAGAS для Faithfulness и Answer Relevancy
@dependencies: ragas (опционально, для production)
@created: 2024-12-19
"""

from typing import List, Dict, Any, Optional


class RAGASEvaluator:
    """
    Оценщик качества ответов через RAGAS.
    
    Отвечает за:
    - Расчёт Faithfulness (насколько ответ основан на контексте)
    - Расчёт Answer Relevancy (насколько ответ релевантен запросу)
    - Интеграция с RAGAS библиотекой
    """
    
    def __init__(self, mock_mode: bool = True):
        """
        Инициализация RAGASEvaluator.
        
        Args:
            mock_mode: Если True, используется мок-режим (без реальных вызовов RAGAS)
        """
        self.mock_mode = mock_mode
        
        if not self.mock_mode:
            try:
                import ragas
                self.ragas_available = True
            except ImportError:
                print("Warning: ragas not installed. RAGASEvaluator will operate in mock mode.")
                self.ragas_available = False
                self.mock_mode = True
        else:
            self.ragas_available = False
    
    def evaluate_faithfulness(
        self,
        question: str,
        answer: str,
        contexts: List[str]
    ) -> float:
        """
        Рассчитывает Faithfulness score через RAGAS.
        
        Faithfulness измеряет, насколько ответ основан на предоставленном контексте.
        Цель проекта: ≥ 0.85
        
        Args:
            question: Вопрос пользователя
            answer: Сгенерированный ответ
            contexts: Список контекстов (тексты retrieved чанков)
            
        Returns:
            Faithfulness score (0.0-1.0)
        """
        if self.mock_mode:
            # В мок-режиме возвращаем фиксированное значение для тестов
            # Проверяем, что ответ содержит текст из контекстов
            answer_lower = answer.lower()
            contexts_text = " ".join(contexts).lower()
            
            # Упрощённая проверка: если ответ содержит текст из контекстов, faithfulness высокий
            if any(context.lower() in answer_lower for context in contexts):
                return 0.90  # Высокий faithfulness
            else:
                return 0.50  # Низкий faithfulness
        
        # Реальная интеграция с RAGAS (для production)
        # TODO: Реализовать при установке ragas
        raise NotImplementedError("RAGAS integration not implemented yet. Use mock_mode=True for testing.")
    
    def evaluate_answer_relevancy(
        self,
        question: str,
        answer: str,
        contexts: List[str]
    ) -> float:
        """
        Рассчитывает Answer Relevancy score через RAGAS.
        
        Answer Relevancy измеряет, насколько ответ релевантен вопросу.
        Цель проекта: ≥ 0.80
        
        Args:
            question: Вопрос пользователя
            answer: Сгенерированный ответ
            contexts: Список контекстов (тексты retrieved чанков)
            
        Returns:
            Answer Relevancy score (0.0-1.0)
        """
        if self.mock_mode:
            # В мок-режиме возвращаем фиксированное значение для тестов
            # Проверяем, что ответ содержит ключевые слова из вопроса
            question_lower = question.lower()
            answer_lower = answer.lower()
            
            # Упрощённая проверка: если ответ содержит ключевые слова из вопроса, relevancy высокий
            question_keywords = set(question_lower.split())
            answer_keywords = set(answer_lower.split())
            
            overlap = len(question_keywords.intersection(answer_keywords))
            if overlap > 0:
                return 0.85  # Высокий relevancy
            else:
                return 0.60  # Низкий relevancy
        
        # Реальная интеграция с RAGAS (для production)
        # TODO: Реализовать при установке ragas
        raise NotImplementedError("RAGAS integration not implemented yet. Use mock_mode=True for testing.")
    
    def evaluate_all(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Рассчитывает все RAGAS метрики.
        
        Args:
            question: Вопрос пользователя
            answer: Сгенерированный ответ
            contexts: Список контекстов (тексты retrieved чанков)
            ground_truth: Ground truth ответ (опционально)
            
        Returns:
            Словарь с метриками (faithfulness, answer_relevancy)
        """
        faithfulness = self.evaluate_faithfulness(question, answer, contexts)
        answer_relevancy = self.evaluate_answer_relevancy(question, answer, contexts)
        
        return {
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy
        }

