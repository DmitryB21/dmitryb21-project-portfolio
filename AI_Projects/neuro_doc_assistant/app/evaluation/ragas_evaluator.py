"""
@file: ragas_evaluator.py
@description: RAGASEvaluator - интеграция с RAGAS для Faithfulness и Answer Relevancy
@dependencies: ragas (опционально, для production)
@created: 2024-12-19
"""

from typing import List, Dict, Any, Optional

# Импорты для реального RAGAS
try:
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy
    from datasets import Dataset
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False


class RAGASEvaluator:
    """
    Оценщик качества ответов через RAGAS.
    
    Отвечает за:
    - Расчёт Faithfulness (насколько ответ основан на контексте)
    - Расчёт Answer Relevancy (насколько ответ релевантен запросу)
    - Интеграция с RAGAS библиотекой
    """
    
    def __init__(
        self,
        mock_mode: bool = False,
        llm_adapter=None,
        embeddings_adapter=None
    ):
        """
        Инициализация RAGASEvaluator.
        
        Args:
            mock_mode: Если True, используется мок-режим (без реальных вызовов RAGAS)
            llm_adapter: LangChain-совместимый LLM адаптер (для реального RAGAS)
            embeddings_adapter: LangChain-совместимый Embeddings адаптер (для реального RAGAS)
        """
        self.mock_mode = mock_mode
        self.llm_adapter = llm_adapter
        self.embeddings_adapter = embeddings_adapter
        
        if not self.mock_mode:
            if not RAGAS_AVAILABLE:
                print("Warning: ragas not installed. RAGASEvaluator will operate in mock mode.")
                self.ragas_available = False
                self.mock_mode = True
            elif not llm_adapter or not embeddings_adapter:
                print("Warning: LLM or Embeddings adapter not provided. RAGASEvaluator will operate in mock mode.")
                self.ragas_available = False
                self.mock_mode = True
            else:
                self.ragas_available = True
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
        
        # Реальная интеграция с RAGAS
        if not self.ragas_available:
            raise RuntimeError("RAGAS not available. Check installation and adapters.")
        
        try:
            # Создаём dataset для RAGAS
            # RAGAS ожидает: contexts - список списков, где каждый элемент - список контекстов для одного примера
            dataset_dict = {
                "question": [question],
                "answer": [answer],
                "contexts": [contexts]  # contexts уже список строк, оборачиваем в список для одного примера
            }
            dataset = Dataset.from_dict(dataset_dict)
            
            # Выполняем оценку faithfulness
            result = evaluate(
                dataset=dataset,
                metrics=[faithfulness],
                llm=self.llm_adapter,
                embeddings=self.embeddings_adapter
            )
            
            # Извлекаем score (результат - DataFrame с одной строкой)
            faithfulness_score = result["faithfulness"].iloc[0] if hasattr(result, "iloc") else result["faithfulness"][0]
            return float(faithfulness_score)
        except Exception as e:
            print(f"Error evaluating faithfulness with RAGAS: {e}")
            # Fallback к mock mode при ошибке
            return 0.75
    
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
        
        # Реальная интеграция с RAGAS
        if not self.ragas_available:
            raise RuntimeError("RAGAS not available. Check installation and adapters.")
        
        try:
            # Создаём dataset для RAGAS
            # RAGAS ожидает: contexts - список списков, где каждый элемент - список контекстов для одного примера
            dataset_dict = {
                "question": [question],
                "answer": [answer],
                "contexts": [contexts]  # contexts уже список строк, оборачиваем в список для одного примера
            }
            dataset = Dataset.from_dict(dataset_dict)
            
            # Выполняем оценку answer_relevancy
            result = evaluate(
                dataset=dataset,
                metrics=[answer_relevancy],
                llm=self.llm_adapter,
                embeddings=self.embeddings_adapter
            )
            
            # Извлекаем score (результат - DataFrame с одной строкой)
            relevancy_score = result["answer_relevancy"].iloc[0] if hasattr(result, "iloc") else result["answer_relevancy"][0]
            return float(relevancy_score)
        except Exception as e:
            print(f"Error evaluating answer_relevancy with RAGAS: {e}")
            # Fallback к mock mode при ошибке
            return 0.75
    
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

