"""
Скрипт для тестирования интеграции с реальным RAGAS.

Использование:
    python scripts/test_ragas_integration.py

Проверяет:
    - Импорт всех необходимых модулей
    - Создание адаптеров для LLM и Embeddings
    - Инициализацию RAGASEvaluator с реальным RAGAS
    - Выполнение оценки метрик (если доступны API ключи)
"""

import os
import sys

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_imports():
    """Проверка импорта всех необходимых модулей."""
    print("=" * 60)
    print("Тест 1: Проверка импортов")
    print("=" * 60)
    
    try:
        from app.evaluation.ragas_evaluator import RAGASEvaluator
        print("✅ RAGASEvaluator импортирован")
    except ImportError as e:
        print(f"❌ Ошибка импорта RAGASEvaluator: {e}")
        return False
    
    try:
        from app.evaluation.ragas_adapters import GigaChatLLMAdapter, GigaChatEmbeddingsAdapter
        print("✅ Адаптеры импортированы")
    except ImportError as e:
        print(f"❌ Ошибка импорта адаптеров: {e}")
        return False
    
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy
        from datasets import Dataset
        print("✅ RAGAS библиотека импортирована")
    except ImportError as e:
        print(f"❌ Ошибка импорта RAGAS: {e}")
        print("   Установите: pip install ragas langchain-core langchain-community")
        return False
    
    try:
        from langchain_core.language_models.llms import LLM
        from langchain_core.embeddings import Embeddings
        print("✅ LangChain импортирован")
    except ImportError as e:
        print(f"❌ Ошибка импорта LangChain: {e}")
        return False
    
    return True


def test_adapters_creation():
    """Проверка создания адаптеров."""
    print("\n" + "=" * 60)
    print("Тест 2: Создание адаптеров")
    print("=" * 60)
    
    try:
        from app.generation.gigachat_client import LLMClient
        from app.ingestion.embedding_service import EmbeddingService
        from app.evaluation.ragas_adapters import GigaChatLLMAdapter, GigaChatEmbeddingsAdapter
        
        # Создаём mock клиенты
        llm_client = LLMClient(mock_mode=True)
        embedding_service = EmbeddingService(mock_mode=True)
        
        # Создаём адаптеры
        llm_adapter = GigaChatLLMAdapter(llm_client=llm_client)
        embeddings_adapter = GigaChatEmbeddingsAdapter(embedding_service=embedding_service)
        
        print("✅ LLM адаптер создан")
        print("✅ Embeddings адаптер создан")
        
        return True, llm_adapter, embeddings_adapter
    except Exception as e:
        print(f"❌ Ошибка создания адаптеров: {e}")
        import traceback
        traceback.print_exc()
        return False, None, None


def test_ragas_evaluator_init():
    """Проверка инициализации RAGASEvaluator."""
    print("\n" + "=" * 60)
    print("Тест 3: Инициализация RAGASEvaluator")
    print("=" * 60)
    
    try:
        from app.evaluation.ragas_evaluator import RAGASEvaluator
        
        # Тест mock mode
        evaluator_mock = RAGASEvaluator(mock_mode=True)
        print("✅ RAGASEvaluator (mock mode) инициализирован")
        
        # Тест реального RAGAS (если доступны адаптеры)
        success, llm_adapter, embeddings_adapter = test_adapters_creation()
        if success and llm_adapter and embeddings_adapter:
            evaluator_real = RAGASEvaluator(
                mock_mode=False,
                llm_adapter=llm_adapter,
                embeddings_adapter=embeddings_adapter
            )
            print("✅ RAGASEvaluator (real RAGAS) инициализирован")
            print(f"   Mock mode: {evaluator_real.mock_mode}")
            print(f"   RAGAS available: {evaluator_real.ragas_available}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка инициализации RAGASEvaluator: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ragas_evaluation():
    """Проверка выполнения оценки через RAGAS (если доступны API ключи)."""
    print("\n" + "=" * 60)
    print("Тест 4: Выполнение оценки через RAGAS")
    print("=" * 60)
    
    # Проверяем наличие API ключей
    gigachat_auth_key = os.getenv("GIGACHAT_AUTH_KEY") or os.getenv("GIGACHAT_API_KEY")
    
    if not gigachat_auth_key:
        print("⚠️  GIGACHAT_AUTH_KEY не установлен, пропускаем тест реальной оценки")
        print("   Для полного теста установите GIGACHAT_AUTH_KEY в .env")
        return True
    
    try:
        from app.generation.gigachat_client import LLMClient
        from app.ingestion.embedding_service import EmbeddingService
        from app.evaluation.ragas_adapters import GigaChatLLMAdapter, GigaChatEmbeddingsAdapter
        from app.evaluation.ragas_evaluator import RAGASEvaluator
        
        # Создаём реальные клиенты (не mock)
        llm_client = LLMClient(
            auth_key=gigachat_auth_key,
            scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
            mock_mode=False
        )
        embedding_service = EmbeddingService(
            auth_key=gigachat_auth_key,
            scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
            mock_mode=False
        )
        
        # Создаём адаптеры
        llm_adapter = GigaChatLLMAdapter(llm_client=llm_client)
        embeddings_adapter = GigaChatEmbeddingsAdapter(embedding_service=embedding_service)
        
        # Создаём evaluator
        evaluator = RAGASEvaluator(
            mock_mode=False,
            llm_adapter=llm_adapter,
            embeddings_adapter=embeddings_adapter
        )
        
        # Тестовые данные
        question = "Какой SLA у сервиса платежей?"
        answer = "SLA сервиса платежей составляет 99.9%"
        contexts = [
            "SLA сервиса платежей составляет 99.9%",
            "Время отклика сервиса платежей не более 200мс"
        ]
        
        print("Выполняем оценку faithfulness...")
        faithfulness_score = evaluator.evaluate_faithfulness(question, answer, contexts)
        print(f"✅ Faithfulness score: {faithfulness_score:.3f}")
        
        print("Выполняем оценку answer_relevancy...")
        relevancy_score = evaluator.evaluate_answer_relevancy(question, answer, contexts)
        print(f"✅ Answer Relevancy score: {relevancy_score:.3f}")
        
        print("Выполняем полную оценку...")
        all_metrics = evaluator.evaluate_all(question, answer, contexts)
        print(f"✅ Все метрики: {all_metrics}")
        
        return True
    except Exception as e:
        print(f"⚠️  Ошибка выполнения оценки: {e}")
        print("   Это может быть связано с недоступностью GigaChat API")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Основная функция для запуска всех тестов."""
    print("\n" + "=" * 60)
    print("Тестирование интеграции с реальным RAGAS")
    print("=" * 60)
    
    # Загружаем переменные окружения из .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Переменные окружения загружены из .env")
    except ImportError:
        print("⚠️  python-dotenv не установлен, используем системные переменные")
    
    results = []
    
    # Тест 1: Импорты
    results.append(("Импорты", test_imports()))
    
    # Тест 2: Создание адаптеров
    success, _, _ = test_adapters_creation()
    results.append(("Создание адаптеров", success))
    
    # Тест 3: Инициализация RAGASEvaluator
    results.append(("Инициализация RAGASEvaluator", test_ragas_evaluator_init()))
    
    # Тест 4: Выполнение оценки (опционально)
    results.append(("Выполнение оценки", test_ragas_evaluation()))
    
    # Итоги
    print("\n" + "=" * 60)
    print("Итоги тестирования")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 Все тесты пройдены! Интеграция с RAGAS работает корректно.")
    else:
        print("\n⚠️  Некоторые тесты не пройдены. Проверьте ошибки выше.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

