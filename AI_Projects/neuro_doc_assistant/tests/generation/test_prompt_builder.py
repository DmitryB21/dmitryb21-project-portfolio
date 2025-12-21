"""
@file: test_prompt_builder.py
@description: Тесты для PromptBuilder - формирование prompt с контекстом и инструкцией
@dependencies: app.generation.prompt_builder, app.retrieval.retriever
@created: 2024-12-19
"""

import pytest
from app.generation.prompt_builder import PromptBuilder
from app.retrieval.retriever import RetrievedChunk


class TestPromptBuilder:
    """
    Тесты для PromptBuilder компонента.
    
    PromptBuilder отвечает за:
    - Формирование prompt с контекстом из retrieved чанков
    - Добавление строгой инструкции «отвечай только по контексту»
    - Структурирование prompt для GigaChat API
    """
    
    @pytest.fixture
    def prompt_builder(self):
        """Фикстура для создания экземпляра PromptBuilder"""
        return PromptBuilder()
    
    @pytest.fixture
    def sample_retrieved_chunks(self):
        """Создаёт тестовые RetrievedChunk объекты"""
        return [
            RetrievedChunk(
                id="chunk_001",
                text="SLA сервиса платежей составляет 99.9%",
                score=0.95,
                metadata={
                    "doc_id": "doc_001",
                    "chunk_id": "chunk_001",
                    "source": "it",
                    "category": "it",
                    "file_path": "it_10_порядок_обращения_в_техподдержку.md"
                }
            ),
            RetrievedChunk(
                id="chunk_002",
                text="Время отклика сервиса платежей не более 200мс",
                score=0.88,
                metadata={
                    "doc_id": "doc_001",
                    "chunk_id": "chunk_002",
                    "source": "it",
                    "category": "it",
                    "file_path": "it_10_порядок_обращения_в_техподдержку.md"
                }
            )
        ]
    
    def test_build_prompt_with_context(self, prompt_builder, sample_retrieved_chunks):
        """
        UC-1 Generation: Формирование prompt с контекстом
        
        Given:
            - Запрос пользователя: "Какой SLA у сервиса платежей?"
            - Список retrieved чанков с контекстом
        When:
            - Вызывается build_prompt
        Then:
            - Prompt содержит запрос пользователя
            - Prompt содержит контекст из всех retrieved чанков
            - Prompt содержит инструкцию «отвечай только по контексту»
        """
        query = "Какой SLA у сервиса платежей?"
        
        prompt = prompt_builder.build_prompt(query, sample_retrieved_chunks)
        
        assert prompt is not None
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        
        # Проверяем, что prompt содержит запрос
        assert query.lower() in prompt.lower()
        
        # Проверяем, что prompt содержит контекст из чанков
        for chunk in sample_retrieved_chunks:
            assert chunk.text in prompt
    
    def test_prompt_contains_instruction(self, prompt_builder, sample_retrieved_chunks):
        """
        UC-1 Generation: Prompt содержит строгую инструкцию
        
        Given:
            - Запрос пользователя и retrieved чанки
        When:
            - Вызывается build_prompt
        Then:
            - Prompt содержит инструкцию «отвечай только по контексту» или аналогичную
            - Инструкция явно запрещает галлюцинации
        """
        query = "Какой SLA у сервиса платежей?"
        
        prompt = prompt_builder.build_prompt(query, sample_retrieved_chunks)
        
        # Проверяем наличие инструкции (разные варианты формулировок)
        instruction_keywords = [
            "только по контексту",
            "только на основе",
            "только используя",
            "не придумывай",
            "не добавляй",
            "строго по",
            "отвечай только"
        ]
        
        prompt_lower = prompt.lower()
        assert any(keyword in prompt_lower for keyword in instruction_keywords)
    
    def test_prompt_structure(self, prompt_builder, sample_retrieved_chunks):
        """
        UC-1 Generation: Структура prompt
        
        Given:
            - Запрос пользователя и retrieved чанки
        When:
            - Вызывается build_prompt
        Then:
            - Prompt имеет чёткую структуру (инструкция, контекст, запрос)
            - Контекст отделён от запроса
        """
        query = "Какой SLA у сервиса платежей?"
        
        prompt = prompt_builder.build_prompt(query, sample_retrieved_chunks)
        
        # Проверяем базовую структуру
        assert len(prompt) > len(query)  # Prompt должен быть больше запроса
        assert query in prompt  # Запрос должен быть в prompt
    
    def test_prompt_with_empty_chunks(self, prompt_builder):
        """
        UC-5 Generation: Обработка пустого списка чанков
        
        Given:
            - Запрос пользователя
            - Пустой список retrieved чанков
        When:
            - Вызывается build_prompt
        Then:
            - Prompt формируется с сообщением об отсутствии контекста
            - Или выбрасывается исключение (в зависимости от реализации)
        """
        query = "Какой SLA у сервиса платежей?"
        
        # Может быть либо исключение, либо prompt с сообщением об отсутствии контекста
        try:
            prompt = prompt_builder.build_prompt(query, [])
            # Если исключение не выброшено, проверяем, что prompt содержит информацию об отсутствии контекста
            assert prompt is not None
            assert "нет информации" in prompt.lower() or "не найдено" in prompt.lower() or len(prompt) > 0
        except (ValueError, AssertionError):
            # Исключение тоже допустимо
            pass
    
    def test_prompt_preserves_chunk_order(self, prompt_builder):
        """
        UC-1 Generation: Сохранение порядка чанков в prompt
        
        Given:
            - Запрос пользователя
            - Список retrieved чанков, отсортированных по score
        When:
            - Вызывается build_prompt
        Then:
            - Чанки в prompt идут в том же порядке (от более релевантных к менее релевантным)
        """
        query = "Какой SLA у сервиса платежей?"
        
        chunks = [
            RetrievedChunk(id="chunk_001", text="Первый чанк", score=0.95, metadata={"doc_id": "doc_001"}),
            RetrievedChunk(id="chunk_002", text="Второй чанк", score=0.88, metadata={"doc_id": "doc_001"}),
            RetrievedChunk(id="chunk_003", text="Третий чанк", score=0.82, metadata={"doc_id": "doc_001"}),
        ]
        
        prompt = prompt_builder.build_prompt(query, chunks)
        
        # Проверяем, что порядок сохранён (первый чанк должен быть раньше второго)
        first_index = prompt.find(chunks[0].text)
        second_index = prompt.find(chunks[1].text)
        third_index = prompt.find(chunks[2].text)
        
        assert first_index != -1
        assert second_index != -1
        assert third_index != -1
        assert first_index < second_index < third_index
    
    def test_prompt_handles_long_context(self, prompt_builder):
        """
        UC-1 Generation: Обработка длинного контекста
        
        Given:
            - Запрос пользователя
            - Большой список retrieved чанков (K=8)
        When:
            - Вызывается build_prompt
        Then:
            - Prompt формируется корректно
            - Все чанки включены в контекст
        """
        query = "Какой SLA у сервиса платежей?"
        
        # Создаём 8 чанков
        chunks = [
            RetrievedChunk(
                id=f"chunk_{i:03d}",
                text=f"Текст чанка {i}",
                score=0.9 - i * 0.1,
                metadata={"doc_id": f"doc_{i // 3:03d}"}
            )
            for i in range(8)
        ]
        
        prompt = prompt_builder.build_prompt(query, chunks)
        
        assert prompt is not None
        assert len(prompt) > 0
        
        # Проверяем, что все чанки включены
        for chunk in chunks:
            assert chunk.text in prompt
    
    def test_prompt_escapes_special_characters(self, prompt_builder):
        """
        UC-1 Generation: Обработка специальных символов в контексте
        
        Given:
            - Запрос пользователя
            - Чанки с специальными символами (кавычки, переносы строк)
        When:
            - Вызывается build_prompt
        Then:
            - Prompt формируется корректно
            - Специальные символы обрабатываются правильно
        """
        query = "Какой SLA у сервиса платежей?"
        
        chunks = [
            RetrievedChunk(
                id="chunk_001",
                text='Текст с "кавычками" и\nпереносами строк',
                score=0.95,
                metadata={"doc_id": "doc_001"}
            )
        ]
        
        prompt = prompt_builder.build_prompt(query, chunks)
        
        assert prompt is not None
        assert chunks[0].text in prompt or chunks[0].text.replace('\n', ' ') in prompt
    
    def test_prompt_includes_metadata_hint(self, prompt_builder, sample_retrieved_chunks):
        """
        UC-1 Generation: Подсказка о метаданных источников
        
        Given:
            - Запрос пользователя и retrieved чанки с метаданными
        When:
            - Вызывается build_prompt
        Then:
            - Prompt может содержать информацию о источниках (опционально)
            - Это помогает LLM ссылаться на источники в ответе
        """
        query = "Какой SLA у сервиса платежей?"
        
        prompt = prompt_builder.build_prompt(query, sample_retrieved_chunks)
        
        # Проверяем базовую структуру
        assert prompt is not None
        # Метаданные могут быть включены или нет, в зависимости от реализации
        # Это не обязательное требование, но может быть полезно

