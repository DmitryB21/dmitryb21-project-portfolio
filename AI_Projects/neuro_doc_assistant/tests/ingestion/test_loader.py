"""
@file: test_loader.py
@description: Тесты для DocumentLoader - загрузка и нормализация документов
@dependencies: app.ingestion.loader
@created: 2024-12-19
"""

import pytest
from pathlib import Path
from app.ingestion.loader import DocumentLoader, Document


class TestDocumentLoader:
    """
    Тесты для DocumentLoader компонента.
    
    DocumentLoader отвечает за:
    - Загрузку документов из файловой системы (MD файлы)
    - Нормализацию текста (удаление лишних пробелов, нормализация кодировок)
    - Извлечение метаданных (путь к файлу, тип документа, категория: hr/it/compliance)
    """

    @pytest.fixture
    def loader(self):
        """Фикстура для создания экземпляра DocumentLoader"""
        return DocumentLoader()

    @pytest.fixture
    def sample_hr_file(self, tmp_path):
        """Создаёт тестовый HR файл"""
        hr_file = tmp_path / "hr_test.md"
        hr_file.write_text(
            "# Политика удалённой работы\n\n"
            "## Введение\n\n"
            "Настоящая политика устанавливает правила удалённой работы."
        )
        return hr_file

    @pytest.fixture
    def sample_it_file(self, tmp_path):
        """Создаёт тестовый IT файл"""
        it_file = tmp_path / "it_test.md"
        it_file.write_text(
            "# Порядок обращения в техподдержку\n\n"
            "## Общие положения\n\n"
            "Техническая поддержка предназначена для оперативного решения проблем."
        )
        return it_file

    def test_load_single_md_file(self, loader, sample_hr_file):
        """
        UC-1 Ingestion: Загрузка одного MD файла
        
        Given:
            - Существует валидный MD файл в файловой системе
        When:
            - Вызывается load_documents с путём к файлу
        Then:
            - Возвращается список Document с одним элементом
            - Document содержит нормализованный текст
            - Document содержит метаданные (id, file_path, category)
        """
        documents = loader.load_documents(str(sample_hr_file))
        
        assert len(documents) == 1
        assert isinstance(documents[0], Document)
        assert documents[0].text is not None
        assert len(documents[0].text) > 0
        assert documents[0].id is not None
        assert documents[0].metadata["file_path"] == str(sample_hr_file)
        assert documents[0].metadata["category"] in ["hr", "it", "compliance"]

    def test_load_directory_with_multiple_files(self, loader, tmp_path):
        """
        UC-1 Ingestion: Загрузка директории с несколькими файлами
        
        Given:
            - Директория содержит несколько MD файлов
        When:
            - Вызывается load_documents с путём к директории
        Then:
            - Возвращается список Document для каждого файла
            - Каждый Document содержит корректные метаданные
        """
        # Создаём тестовую структуру директорий
        hr_dir = tmp_path / "hr"
        hr_dir.mkdir()
        (hr_dir / "hr_01.md").write_text("# HR Policy 1")
        (hr_dir / "hr_02.md").write_text("# HR Policy 2")
        
        documents = loader.load_documents(str(hr_dir))
        
        assert len(documents) == 2
        assert all(isinstance(doc, Document) for doc in documents)
        assert all(doc.metadata["category"] == "hr" for doc in documents)

    def test_text_normalization(self, loader, tmp_path):
        """
        UC-1 Ingestion: Нормализация текста
        
        Given:
            - MD файл содержит текст с лишними пробелами и нестандартными символами
        When:
            - Файл загружается через DocumentLoader
        Then:
            - Текст нормализован (удалены лишние пробелы, нормализованы кодировки)
            - Сохранена читаемость текста
        """
        test_file = tmp_path / "test.md"
        test_file.write_text(
            "#   Заголовок  с  лишними  пробелами\n\n"
            "Текст   с   множественными   пробелами."
        )
        
        documents = loader.load_documents(str(test_file))
        
        assert len(documents) == 1
        text = documents[0].text
        # Проверяем, что лишние пробелы удалены
        assert "  " not in text  # Нет двойных пробелов
        assert text.strip() == text  # Нет пробелов в начале/конце

    def test_metadata_extraction_hr(self, loader, sample_hr_file):
        """
        UC-1 Ingestion: Извлечение метаданных для HR документов
        
        Given:
            - HR файл загружается из директории data/NeuroDoc_Data/hr/
        When:
            - Файл обрабатывается DocumentLoader
        Then:
            - Метаданные содержат category="hr"
            - Метаданные содержат корректный file_path
            - Метаданные содержат уникальный id документа
        """
        documents = loader.load_documents(str(sample_hr_file))
        
        assert len(documents) == 1
        metadata = documents[0].metadata
        assert metadata["category"] == "hr"
        assert "file_path" in metadata
        assert "id" in metadata or documents[0].id is not None

    def test_metadata_extraction_it(self, loader, sample_it_file):
        """
        UC-1 Ingestion: Извлечение метаданных для IT документов
        
        Given:
            - IT файл загружается из директории data/NeuroDoc_Data/it/
        When:
            - Файл обрабатывается DocumentLoader
        Then:
            - Метаданные содержат category="it"
            - Метаданные содержат корректный file_path
        """
        documents = loader.load_documents(str(sample_it_file))
        
        assert len(documents) == 1
        metadata = documents[0].metadata
        assert metadata["category"] == "it"

    def test_load_nonexistent_file(self, loader):
        """
        UC-1 Ingestion: Обработка ошибок - несуществующий файл
        
        Given:
            - Путь к несуществующему файлу
        When:
            - Вызывается load_documents
        Then:
            - Выбрасывается FileNotFoundError или возвращается пустой список
        """
        with pytest.raises((FileNotFoundError, ValueError)):
            loader.load_documents("/nonexistent/path/file.md")

    def test_load_invalid_file_format(self, loader, tmp_path):
        """
        UC-1 Ingestion: Обработка невалидных форматов файлов
        
        Given:
            - Файл с неподдерживаемым форматом (не MD)
        When:
            - Вызывается load_documents
        Then:
            - Файл пропускается или выбрасывается ошибка (в зависимости от реализации)
        """
        # Пока поддерживаем только MD, другие форматы могут быть пропущены
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("Some text")
        
        # Поведение зависит от реализации - может быть пропуск или ошибка
        # Это нужно уточнить в требованиях
        pass

    def test_load_real_hr_directory(self, loader):
        """
        UC-1 Ingestion: Загрузка реальной директории HR документов
        
        Given:
            - Директория data/NeuroDoc_Data/hr/ существует и содержит MD файлы
        When:
            - Вызывается load_documents с путём к директории
        Then:
            - Загружаются все MD файлы из директории
            - Каждый документ имеет корректные метаданные
        """
        hr_path = Path("data/NeuroDoc_Data/hr")
        if not hr_path.exists():
            pytest.skip("HR directory not found")
        
        documents = loader.load_documents(str(hr_path))
        
        assert len(documents) > 0
        assert all(doc.metadata["category"] == "hr" for doc in documents)
        assert all(doc.text is not None and len(doc.text) > 0 for doc in documents)

    def test_load_real_it_directory(self, loader):
        """
        UC-1 Ingestion: Загрузка реальной директории IT документов
        
        Given:
            - Директория data/NeuroDoc_Data/it/ существует и содержит MD файлы
        When:
            - Вызывается load_documents с путём к директории
        Then:
            - Загружаются все MD файлы из директории
            - Каждый документ имеет корректные метаданные
        """
        it_path = Path("data/NeuroDoc_Data/it")
        if not it_path.exists():
            pytest.skip("IT directory not found")
        
        documents = loader.load_documents(str(it_path))
        
        assert len(documents) > 0
        assert all(doc.metadata["category"] == "it" for doc in documents)
        assert all(doc.text is not None and len(doc.text) > 0 for doc in documents)

