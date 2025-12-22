"""
Скрипт для проверки статуса индексации и информации о коллекции Qdrant
"""

import os
import sys
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

def main():
    print("=" * 80)
    print("ПРОВЕРКА СТАТУСА ИНДЕКСАЦИИ")
    print("=" * 80)
    print()
    
    # Подключение к Qdrant
    qdrant_url = os.getenv("QDRANT_URL")
    if not qdrant_url:
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
    
    print(f"🔗 Подключение к Qdrant: {qdrant_url}")
    try:
        qdrant_client = QdrantClient(url=qdrant_url)
        collections = qdrant_client.get_collections()
        print(f"✅ Подключение успешно")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return 1
    
    print()
    print("=" * 80)
    print("КОЛЛЕКЦИИ В QDRANT")
    print("=" * 80)
    
    collection_name = os.getenv("QDRANT_COLLECTION", "neuro_docs")
    
    if collection_name in [col.name for col in collections.collections]:
        print(f"✅ Коллекция '{collection_name}' найдена")
        
        # Получаем информацию о коллекции
        collection_info = qdrant_client.get_collection(collection_name)
        print()
        print(f"📊 Информация о коллекции '{collection_name}':")
        print(f"   - Количество точек: {collection_info.points_count}")
        print(f"   - Размерность векторов: {collection_info.config.params.vectors.size}")
        print(f"   - Метрика расстояния: {collection_info.config.params.vectors.distance}")
        
        # Получаем несколько примеров точек
        print()
        print("=" * 80)
        print("ПРИМЕРЫ ПРОИНДЕКСИРОВАННЫХ ДОКУМЕНТОВ")
        print("=" * 80)
        
        try:
            # Получаем первые 5 точек
            points = qdrant_client.scroll(
                collection_name=collection_name,
                limit=5
            )[0]
            
            for i, point in enumerate(points, 1):
                payload = point.payload
                print()
                print(f"📄 Пример {i}:")
                print(f"   - ID точки: {point.id}")
                print(f"   - chunk_id: {payload.get('chunk_id', 'N/A')}")
                print(f"   - doc_id: {payload.get('doc_id', 'N/A')}")
                print(f"   - source: {payload.get('source', 'N/A')}")
                print(f"   - category: {payload.get('category', 'N/A')}")
                print(f"   - embedding_version: {payload.get('embedding_version', 'N/A')}")
                print(f"   - text_length: {payload.get('text_length', 'N/A')}")
                text_preview = payload.get('text', '')[:100]
                print(f"   - текст (первые 100 символов): {text_preview}...")
        except Exception as e:
            print(f"⚠️  Не удалось получить примеры точек: {e}")
    else:
        print(f"❌ Коллекция '{collection_name}' не найдена")
        print(f"   Доступные коллекции: {[col.name for col in collections.collections]}")
        return 1
    
    print()
    print("=" * 80)
    print("КОНФИГУРАЦИЯ EMBEDDING SERVICE")
    print("=" * 80)
    
    gigachat_api_key = os.getenv("GIGACHAT_API_KEY")
    use_mock_mode = not gigachat_api_key or os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true"
    
    print(f"   - API ключ: {'✅ установлен' if gigachat_api_key else '❌ не установлен'}")
    print(f"   - Mock mode: {'✅ включен' if use_mock_mode else '❌ выключен'}")
    print(f"   - Модель: {os.getenv('EMBEDDING_MODEL_VERSION', 'GigaChat')}")
    print(f"   - Размерность: {os.getenv('EMBEDDING_DIM', '1536')}")
    
    if use_mock_mode:
        print()
        print("⚠️  ВНИМАНИЕ: Используется mock mode для генерации embeddings!")
        print("   Embeddings генерируются на основе MD5 hash текста, а не реальной модели.")
        print("   Для production использования необходимо:")
        print("   1. Установить валидный GIGACHAT_API_KEY в .env")
        print("   2. Убедиться, что GIGACHAT_MOCK_MODE=false")
        print("   3. Перезапустить ingestion pipeline")
    else:
        print()
        print("✅ Используется реальный GigaChat Embeddings API")
    
    print()
    print("=" * 80)
    print("✅ ПРОВЕРКА ЗАВЕРШЕНА")
    print("=" * 80)
    
    return 0

if __name__ == "__main__":
    exit(main())

