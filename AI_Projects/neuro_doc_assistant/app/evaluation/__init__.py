"""
@file: __init__.py
@description: Evaluation module - расчёт метрик качества и интеграция с RAGAS
@dependencies: None
@created: 2024-12-19
"""

from app.evaluation.metrics import MetricsCollector
from app.evaluation.ragas_evaluator import RAGASEvaluator

__all__ = [
    "MetricsCollector",
    "RAGASEvaluator",
]

