"""
@file: __init__.py
@description: Generation module - генерация ответов через GigaChat API
@dependencies: None
@created: 2024-12-19
"""

from app.generation.prompt_builder import PromptBuilder
from app.generation.gigachat_client import LLMClient

__all__ = [
    "PromptBuilder",
    "LLMClient",
]

