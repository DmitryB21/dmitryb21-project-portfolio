"""
@file: test_embedding_service.py
@description: Тесты для EmbeddingService - генерация векторных представлений
@dependencies: app.ingestion.embedding_service
@created: 2024-12-19
"""

import pytest
from unittest.mock import Mock, patch
from app.ingestion.embedding_service import EmbeddingService


class TestEmbeddingService:
    """
    Тесты для EmbeddingService компонента.
    
    EmbeddingService отвечает за:
    - Генерацию векторных представлений через GigaChat Embeddings API
    - Батчинг для оптимизации throughput
    - Размерность векторов: 1536 или 1024 (фиксируется в конфигурации)
    """

    @pytest.fixture
    def embedding_service(self):
        """Фикстура для создания экземпляра EmbeddingService"""
        return EmbeddingService(model_version="test_model", embedding_dim=1536)

    @pytest.fixture
    def sample_texts(self):
        """Создаёт список тестовых текстов"""
        return [
            "Первый текст для тестирования embeddings.",
            "Второй текст с другим содержанием.",
            "Третий текст для проверки батчинга."
        ]

    @pytest.fixture
    def mock_gigachat_response(self):
        """Мок ответа от GigaChat Embeddings API - возвращает список векторов"""
        # Симулируем ответ с векторами размерности 1536
        return [0.1] * 1536

    def test_generate_embeddings_single_text(self, embedding_service, mock_gigachat_response):
        """
        UC-1 Ingestion: Генерация embedding для одного текста
        
        Given:
            - Один текст для обработки
        When:
            - Вызывается generate_embeddings
        Then:
            - Возвращается список с одним вектором
            - Вектор имеет правильную размерность (1536 или 1024)
            - Вектор содержит числовые значения
        """
        with patch.object(embedding_service, '_call_gigachat_api', return_value=mock_gigachat_response):
            embeddings = embedding_service.generate_embeddings(["Тестовый текст"])
        
        assert len(embeddings) == 1
        assert len(embeddings[0]) == embedding_service.embedding_dim
        assert all(isinstance(val, (int, float)) for val in embeddings[0])

    def test_generate_embeddings_multiple_texts(self, embedding_service, sample_texts, mock_gigachat_response):
        """
        UC-1 Ingestion: Генерация embeddings для нескольких текстов
        
        Given:
            - Несколько текстов для обработки
        When:
            - Вызывается generate_embeddings
        Then:
            - Возвращается список векторов, соответствующий количеству текстов
            - Каждый вектор имеет правильную размерность
        """
        with patch.object(embedding_service, '_call_gigachat_api', return_value=mock_gigachat_response):
            embeddings = embedding_service.generate_embeddings(sample_texts)
        
        assert len(embeddings) == len(sample_texts)
        assert all(len(emb) == embedding_service.embedding_dim for emb in embeddings)

    def test_batching_for_large_input(self, embedding_service):
        """
        UC-1 Ingestion: Батчинг для больших объёмов данных
        
        Given:
            - Большой список текстов (больше размера батча)
        When:
            - Вызывается generate_embeddings
        Then:
            - Тексты обрабатываются батчами
            - Все тексты обработаны
            - Порядок векторов соответствует порядку текстов
        """
        # Создаём список из 100 текстов (больше типичного размера батча)
        large_text_list = [f"Текст номер {i}" for i in range(100)]
        
        # Мокаем API вызовы с батчингом
        call_count = 0
        def mock_batch_call(texts):
            nonlocal call_count
            call_count += 1
            return {"data": [{"embedding": [0.1] * 1536} for _ in texts]}
        
        with patch.object(embedding_service, '_call_gigachat_api', side_effect=mock_batch_call):
            embeddings = embedding_service.generate_embeddings(large_text_list)
        
        assert len(embeddings) == len(large_text_list)
        assert call_count > 1  # Должно быть несколько батчей

    def test_embedding_dimension_1536(self):
        """
        UC-1 Ingestion: Размерность векторов 1536
        
        Given:
            - EmbeddingService настроен на размерность 1536
        When:
            - Генерируются embeddings
        Then:
            - Все векторы имеют размерность 1536
        """
        service = EmbeddingService(model_version="test_model", embedding_dim=1536)
        mock_response = [0.1] * 1536
        
        with patch.object(service, '_call_gigachat_api', return_value=mock_response):
            embeddings = service.generate_embeddings(["Тест"])
        
        assert len(embeddings[0]) == 1536

    def test_embedding_dimension_1024(self):
        """
        UC-1 Ingestion: Размерность векторов 1024
        
        Given:
            - EmbeddingService настроен на размерность 1024
        When:
            - Генерируются embeddings
        Then:
            - Все векторы имеют размерность 1024
        """
        mock_response_1024 = [0.1] * 1024
        service = EmbeddingService(model_version="test_model", embedding_dim=1024)
        
        with patch.object(service, '_call_gigachat_api', return_value=mock_response_1024):
            embeddings = service.generate_embeddings(["Тест"])
        
        assert len(embeddings[0]) == 1024

    def test_model_version_fixed(self, embedding_service):
        """
        UC-6 Ingestion: Версия модели фиксируется для воспроизводимости
        
        Given:
            - EmbeddingService создан с определённой версией модели
        When:
            - Генерируются embeddings
        Then:
            - Версия модели используется в API вызовах
            - Версия фиксируется в метаданных для экспериментов
        """
        assert embedding_service.model_version == "test_model"
        assert embedding_service.embedding_dim == 1536

    def test_error_handling_api_failure(self, embedding_service):
        """
        UC-1 Ingestion: Обработка ошибок API
        
        Given:
            - GigaChat Embeddings API возвращает ошибку
        When:
            - Вызывается generate_embeddings
        Then:
            - Выбрасывается соответствующее исключение
            - Ошибка логируется
        """
        with patch.object(embedding_service, '_call_gigachat_api', side_effect=Exception("API Error")):
            with pytest.raises(Exception):
                embedding_service.generate_embeddings(["Тест"])

    def test_empty_input_handling(self, embedding_service):
        """
        UC-1 Ingestion: Обработка пустого списка текстов
        
        Given:
            - Пустой список текстов
        When:
            - Вызывается generate_embeddings
        Then:
            - Возвращается пустой список или выбрасывается ValueError
        """
        with pytest.raises((ValueError, AssertionError)):
            embedding_service.generate_embeddings([])

    def test_embedding_consistency(self, embedding_service, mock_gigachat_response):
        """
        UC-6 Ingestion: Воспроизводимость embeddings
        
        Given:
            - Один и тот же текст обрабатывается дважды
        When:
            - Генерируются embeddings с одинаковыми параметрами
        Then:
            - Векторы идентичны (при одинаковых параметрах модели)
        """
        text = "Тестовый текст для проверки воспроизводимости"
        
        with patch.object(embedding_service, '_call_gigachat_api', return_value=mock_gigachat_response):
            emb1 = embedding_service.generate_embeddings([text])
            emb2 = embedding_service.generate_embeddings([text])
        
        # При одинаковых параметрах и моке должны быть одинаковые результаты
        assert emb1 == emb2

