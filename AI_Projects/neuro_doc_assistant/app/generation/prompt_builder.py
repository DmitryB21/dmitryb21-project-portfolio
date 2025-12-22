"""
@file: prompt_builder.py
@description: PromptBuilder - формирование prompt с контекстом и инструкцией
@dependencies: app.retrieval.retriever
@created: 2024-12-19
"""

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.retrieval.retriever import RetrievedChunk


class PromptBuilder:
    """
    Построитель prompt для GigaChat API.
    
    Отвечает за:
    - Формирование prompt с контекстом из retrieved чанков
    - Добавление строгой инструкции «отвечай только по контексту»
    - Структурирование prompt для оптимальной работы LLM
    """
    
    def __init__(
        self,
        instruction_template: str = None
    ):
        """
        Инициализация PromptBuilder.
        
        Args:
            instruction_template: Шаблон инструкции (опционально, используется по умолчанию)
        """
        self.instruction_template = instruction_template or self._default_instruction()
    
    def _default_instruction(self) -> str:
        """
        Возвращает инструкцию по умолчанию для предотвращения галлюцинаций.
        
        Returns:
            Текст инструкции
        """
        return (
            "Ты - помощник, который отвечает на вопросы строго на основе предоставленного контекста.\n"
            "ВАЖНО:\n"
            "- Отвечай ТОЛЬКО на основе информации из контекста\n"
            "- НЕ придумывай информацию, которой нет в контексте\n"
            "- НЕ добавляй факты, не упомянутые в контексте\n"
            "- Если в контексте нет ответа на вопрос, честно скажи об этом\n"
            "- Используй информацию из контекста дословно или близко к тексту\n"
        )
    
    def build_prompt(
        self,
        query: str,
        retrieved_chunks: List["RetrievedChunk"]
    ) -> str:
        """
        Формирует prompt с контекстом и запросом.
        
        Args:
            query: Запрос пользователя
            retrieved_chunks: Список retrieved чанков с контекстом
            
        Returns:
            Сформированный prompt для GigaChat API
            
        Raises:
            ValueError: Если список чанков пуст (опционально, в зависимости от требований)
        """
        if not retrieved_chunks:
            # Если нет контекста, формируем prompt с сообщением об отсутствии информации
            return (
                f"{self.instruction_template}\n\n"
                f"Контекст: В предоставленной документации нет релевантной информации.\n\n"
                f"Вопрос: {query}\n\n"
                f"Ответ: В документации не найдено информации для ответа на этот вопрос."
            )
        
        # Формируем контекст из всех retrieved чанков
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, start=1):
            context_parts.append(f"[Источник {i}]\n{chunk.text}\n")
        
        context = "\n".join(context_parts)
        
        # Формируем полный prompt
        prompt = (
            f"{self.instruction_template}\n\n"
            f"Контекст из документации:\n{context}\n\n"
            f"Вопрос: {query}\n\n"
            f"Ответ (на основе контекста):"
        )
        
        return prompt

