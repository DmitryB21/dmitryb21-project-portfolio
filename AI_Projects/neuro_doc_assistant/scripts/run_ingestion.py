#!/usr/bin/env python
"""
Скрипт для запуска Ingestion Pipeline - загрузка и индексация документов в Qdrant
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from app.ingestion.loader import DocumentLoader
from app.ingestion.chunker import Chunker
from app.ingestion.embedding_service import EmbeddingService
from app.ingestion.indexer import QdrantIndexer
from app.api.indexing_status import get_tracker
from app.storage.document_repository import DocumentRepository, DocumentMetadata

# Загружаем переменные окружения
load_dotenv()


def main():
    """
    Запуск полного Ingestion Pipeline:
    1. Загрузка документов из data/NeuroDoc_Data/
    2. Чанкинг документов
    3. Генерация embeddings
    4. Индексация в Qdrant (создание коллекции neuro_docs, если не существует)
    """
    tracker = get_tracker()
    tracker.start(total_steps=5)
    
    print("=" * 80)
    print("Neuro_Doc_Assistant - Ingestion Pipeline")
    print("=" * 80)
    print()
    
    # Определяем источник данных (S3 или локальная файловая система)
    use_s3_env = os.getenv("USE_S3_STORAGE", "auto").lower()
    use_s3 = use_s3_env in ("true", "1", "yes", "auto")
    
    print(f"🔍 Определение источника данных...")
    print(f"   USE_S3_STORAGE={use_s3_env}")
    
    # Проверяем наличие переменных S3
    s3_endpoint = os.getenv("S3_ENDPOINT")
    s3_access_key = os.getenv("S3_ACCESS_KEY")
    s3_secret_key = os.getenv("S3_SECRET_KEY")
    s3_bucket = os.getenv("S3_BUCKET")
    
    print(f"   S3_ENDPOINT: {s3_endpoint or 'NOT SET'}")
    print(f"   S3_ACCESS_KEY: {'SET' if s3_access_key else 'NOT SET'}")
    print(f"   S3_SECRET_KEY: {'SET' if s3_secret_key else 'NOT SET'}")
    print(f"   S3_BUCKET: {s3_bucket or 'NOT SET'}")
    
    # Проверяем наличие boto3 перед попыткой использования S3
    if use_s3:
        try:
            import boto3
            print(f"   ✅ boto3 доступен: {boto3.__version__}")
        except ImportError as e:
            print(f"   ❌ boto3 не установлен: {e}")
            print(f"   💡 Установите boto3: pip install boto3")
            print(f"   Переключение на локальную файловую систему...")
            use_s3 = False
    
    # Инициализируем loader с автоматическим определением
    try:
        loader = DocumentLoader(storage_backend="auto" if use_s3 else "local")
        print(f"   ✅ DocumentLoader инициализирован: {loader.storage_backend}")
        
        # Если определился как local, но мы хотели S3, проверяем почему
        if loader.storage_backend == "local" and use_s3:
            print(f"   ⚠️  DocumentLoader выбрал 'local' вместо 's3'")
            if not all([s3_endpoint, s3_access_key, s3_secret_key, s3_bucket]):
                print(f"   💡 Причина: Не все переменные S3 установлены")
                print(f"      Отсутствуют: {[var for var, val in [('S3_ENDPOINT', s3_endpoint), ('S3_ACCESS_KEY', s3_access_key), ('S3_SECRET_KEY', s3_secret_key), ('S3_BUCKET', s3_bucket)] if not val]}")
            elif loader.s3_storage is None:
                print(f"   💡 Причина: S3 storage не инициализирован")
                # Пытаемся получить информацию об ошибке
                if hasattr(loader, '_s3_init_error'):
                    print(f"      Ошибка инициализации: {loader._s3_init_error}")
                if hasattr(loader, '_s3_list_error'):
                    print(f"      Ошибка при проверке документов: {loader._s3_list_error}")
                print(f"      Проверьте:")
                print(f"        1. MinIO запущен: docker ps | grep minio")
                print(f"        2. Доступность endpoint: curl {s3_endpoint}")
                print(f"        3. Правильность credentials в .env")
    except Exception as e:
        print(f"   ⚠️  Ошибка инициализации DocumentLoader: {e}")
        import traceback
        traceback.print_exc()
        print("   Переключение на локальную файловую систему...")
        loader = DocumentLoader(storage_backend="local")
    
    # Проверка наличия данных
    hr_dir = None
    it_dir = None
    
    if loader.storage_backend == "s3":
        # Проверяем наличие документов в S3
        print("📦 Проверка документов в S3 хранилище...")
        try:
            # S3 storage уже инициализирован в DocumentLoader
            if loader.s3_storage:
                all_docs = loader.s3_storage.list_documents()
                if not all_docs:
                    print("⚠️  В S3 хранилище не найдено документов")
                    print("   Переключение на локальную файловую систему...")
                    loader = DocumentLoader(storage_backend="local")
                else:
                    print(f"   ✅ Найдено документов в S3: {len(all_docs)}")
                    # Группируем по категориям для информации
                    categories = {}
                    for doc_key in all_docs:
                        category = doc_key.split('/')[0] if '/' in doc_key else "unknown"
                        categories[category] = categories.get(category, 0) + 1
                    print(f"   Категории: {', '.join([f'{k}: {v}' for k, v in sorted(categories.items())])}")
            else:
                print("⚠️  S3 storage не инициализирован")
                print("   Переключение на локальную файловую систему...")
                loader = DocumentLoader(storage_backend="local")
        except Exception as e:
            print(f"⚠️  Предупреждение: не удалось проверить S3: {e}")
            import traceback
            traceback.print_exc()
            print("   Переключение на локальную файловую систему...")
            loader = DocumentLoader(storage_backend="local")
    
    if loader.storage_backend == "local":
        # Проверяем локальную файловую систему
        data_dir = project_root / "data" / "NeuroDoc_Data"
        if not data_dir.exists():
            print(f"❌ Ошибка: Директория с данными не найдена: {data_dir}")
            print("   Создайте директорию data/NeuroDoc_Data/ и поместите туда документы.")
            print("   Или настройте S3 хранилище (USE_S3_STORAGE=true в .env)")
            return 1
        
        hr_dir = data_dir / "hr"
        it_dir = data_dir / "it"
        
        if not hr_dir.exists() and not it_dir.exists():
            print(f"❌ Ошибка: Не найдены директории hr/ или it/ в {data_dir}")
            return 1
    
    # Инициализация Qdrant клиента
    tracker.update_step(1, "Подключение к Qdrant", "Подключение к Qdrant...")
    print("[Шаг 1/5] Подключение к Qdrant...")
    qdrant_url = os.getenv("QDRANT_URL")
    if not qdrant_url:
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
    
    try:
        qdrant_client = QdrantClient(url=qdrant_url)
        # Проверяем подключение
        collections = qdrant_client.get_collections()
        print(f"✅ Подключение к Qdrant успешно: {qdrant_url}")
        tracker.update_step(1, "Подключение к Qdrant", f"✅ Подключено к {qdrant_url}")
    except Exception as e:
        error_msg = f"Ошибка подключения к Qdrant: {e}"
        print(f"❌ {error_msg}")
        print()
        print("Убедитесь, что Qdrant запущен:")
        print("  Docker: docker run -p 6333:6333 qdrant/qdrant")
        print("  Или установите Qdrant локально")
        tracker.fail(error_msg)
        return 1
    
    # Инициализация компонентов
    tracker.update_step(2, "Инициализация компонентов", "Инициализация компонентов...")
    print()
    print("[Шаг 2/5] Инициализация компонентов...")
    
    # DocumentLoader уже инициализирован выше при проверке данных
    # Chunker инициализируется отдельно
    chunker = Chunker()
    
    # Инициализация DocumentRepository для сохранения метаданных в PostgreSQL
    doc_repository = None
    try:
        doc_repository = DocumentRepository()
        print("   ✅ DocumentRepository инициализирован (PostgreSQL)")
    except Exception as e:
        print(f"   ⚠️  Предупреждение: не удалось инициализировать DocumentRepository: {e}")
        print("   Метаданные не будут сохраняться в PostgreSQL")
    
    # Начальная размерность из конфигурации (может быть обновлена после первого ответа API)
    initial_embedding_dim = int(os.getenv("EMBEDDING_DIM", "1536"))
    gigachat_auth_key = os.getenv("GIGACHAT_AUTH_KEY")
    gigachat_scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    
    # Определяем, использовать ли mock mode
    # Если auth_key не предоставлен или mock mode включен, используем mock mode
    use_mock_mode = not gigachat_auth_key or os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true"
    
    # Определяем фактический режим работы (после инициализации EmbeddingService)
    # Сначала создаем сервис, чтобы узнать его фактический режим
    embedding_service = EmbeddingService(
        model_version=os.getenv("EMBEDDING_MODEL_VERSION", "GigaChat"),
        embedding_dim=initial_embedding_dim,
        auth_key=gigachat_auth_key,
        scope=gigachat_scope,
        mock_mode=use_mock_mode
    )
    
    # Получаем фактический режим работы после инициализации
    actual_mode = "Mock Embeddings" if embedding_service.mock_mode else "GigaChat Embeddings API"
    
    # Сохраняем информацию о режиме в трекер
    tracker.update_stats(embedding_mode=actual_mode)
    
    # Выводим информацию о режиме работы
    print()
    print("=" * 80)
    print("📊 РЕЖИМ РАБОТЫ EMBEDDINGS")
    print("=" * 80)
    if embedding_service.mock_mode:
        print("   ⚠️  РЕЖИМ: Mock Embeddings")
        print("   📝 Описание: Используются детерминированные mock embeddings на основе MD5 hash")
        print("   ⚠️  Внимание: Mock embeddings НЕ отражают семантическое сходство текстов!")
        if not gigachat_auth_key:
            print("   💡 Причина: GIGACHAT_AUTH_KEY не установлен в .env файле")
        elif os.getenv("GIGACHAT_MOCK_MODE", "false").lower() == "true":
            print("   💡 Причина: GIGACHAT_MOCK_MODE=true в .env файле")
        else:
            print("   💡 Причина: Автоматический fallback (API недоступен или требует подписку)")
    else:
        print("   ✅ РЕЖИМ: GigaChat Embeddings API")
        print("   📝 Описание: Используется реальный GigaChat Embeddings API")
        print(f"   🔑 Аутентификация: OAuth 2.0 (scope: {gigachat_scope})")
        print(f"   🌐 Endpoint: {embedding_service.api_url}")
        print(f"   🤖 Модель: Embeddings")
        print("   ⚠️  Примечание: API может требовать платную подписку (402 Payment Required)")
        print("      При ошибке 402 система автоматически переключится на mock embeddings")
    print("=" * 80)
    print()
    
    collection_name = os.getenv("QDRANT_COLLECTION", "neuro_docs")
    # Используем размерность из embedding_service (может быть обновлена после первого ответа API)
    # Но для инициализации indexer используем начальную размерность
    indexer = QdrantIndexer(
        qdrant_client=qdrant_client,
        collection_name=collection_name,
        embedding_dim=initial_embedding_dim
    )
    print(f"✅ Компоненты инициализированы (collection: {collection_name}, embedding_dim: {initial_embedding_dim})")
    tracker.update_step(2, "Инициализация компонентов", f"✅ Компоненты инициализированы (collection: {collection_name}, режим: {actual_mode})")
    
    # Загрузка документов
    tracker.update_step(3, "Загрузка документов", "Загрузка документов...")
    print()
    print("[Шаг 3/5] Загрузка документов...")
    
    all_documents = []
    
    if loader.storage_backend == "s3":
        # Загрузка из S3
        print("   📦 Используется S3 хранилище")
        # Загружаем только hr и it документы
        categories = ["hr", "it"]
        
        for category in categories:
            try:
                print(f"   Загрузка {category.upper()} документов из S3...")
                category_documents = loader.load_documents(category + "/", category=category)
                all_documents.extend(category_documents)
                print(f"   ✅ Загружено {category.upper()} документов: {len(category_documents)}")
            except Exception as e:
                print(f"   ⚠️  Предупреждение: не удалось загрузить {category}: {e}")
    else:
        # Загрузка из локальной файловой системы
        print("   📁 Используется локальная файловая система")
        if hr_dir.exists():
            print(f"   Загрузка HR документов из {hr_dir}...")
            hr_documents = loader.load_documents(str(hr_dir), category="hr")
            all_documents.extend(hr_documents)
            print(f"   ✅ Загружено HR документов: {len(hr_documents)}")
        
        if it_dir.exists():
            print(f"   Загрузка IT документов из {it_dir}...")
            it_documents = loader.load_documents(str(it_dir), category="it")
            all_documents.extend(it_documents)
            print(f"   ✅ Загружено IT документов: {len(it_documents)}")
    
    if not all_documents:
        error_msg = "Не найдено документов для загрузки"
        print(f"❌ Ошибка: {error_msg}")
        tracker.fail(error_msg)
        return 1
    
    print(f"✅ Всего загружено документов: {len(all_documents)}")
    tracker.update_stats(documents_loaded=len(all_documents))
    tracker.update_step(3, "Загрузка документов", f"✅ Загружено документов: {len(all_documents)}")
    
    # Чанкинг
    tracker.update_step(4, "Разбиение на чанки", "Разбиение документов на чанки...")
    print()
    print("[Шаг 4/5] Разбиение документов на чанки...")
    chunk_size = int(os.getenv("CHUNK_SIZE", "300"))
    overlap_percent = float(os.getenv("CHUNK_OVERLAP_PERCENT", "0.25"))
    
    all_chunks = []
    for i, doc in enumerate(all_documents):
        chunks = chunker.chunk_documents(
            [doc],
            chunk_size=chunk_size,
            overlap_percent=overlap_percent
        )
        all_chunks.extend(chunks)
        # Обновляем прогресс чанкинга
        if (i + 1) % 10 == 0 or i == len(all_documents) - 1:
            progress = 20.0 + ((i + 1) / len(all_documents)) * 20.0  # Шаг 4: 20-40%
            tracker.update_progress(progress, f"Обработано документов: {i + 1}/{len(all_documents)}")
    
    print(f"✅ Создано чанков: {len(all_chunks)} (chunk_size={chunk_size}, overlap={overlap_percent*100}%)")
    tracker.update_stats(chunks_created=len(all_chunks))
    tracker.update_step(4, "Разбиение на чанки", f"✅ Создано чанков: {len(all_chunks)}")
    
    # Генерация embeddings
    tracker.update_step(5, "Генерация embeddings", f"Генерация embeddings ({actual_mode})...")
    print()
    print("[Шаг 5/5] Генерация embeddings и индексация в Qdrant...")
    if embedding_service.mock_mode:
        print("   ⚠️  Режим: Mock Embeddings (детерминированные векторы на основе MD5 hash)")
    else:
        print(f"   ✅ Режим: GigaChat Embeddings API ({embedding_service.api_url})")
    print("   Это может занять некоторое время...")
    
    chunk_texts = [chunk.text for chunk in all_chunks]
    
    # Генерируем embeddings батчами для оптимизации
    batch_size = 10
    all_embeddings = []
    total_batches = (len(chunk_texts) + batch_size - 1) // batch_size
    
    # Импортируем time для задержек при rate limiting
    import time
    
    for batch_idx, i in enumerate(range(0, len(chunk_texts), batch_size)):
        batch = chunk_texts[i:i + batch_size]
        batch_embeddings = embedding_service.generate_embeddings(batch)
        all_embeddings.extend(batch_embeddings)
        
        # После первого батча проверяем, не изменилась ли размерность
        # (API может вернуть другую размерность, например 1024 вместо 1536)
        if batch_idx == 0 and batch_embeddings and len(batch_embeddings) > 0:
            actual_dim = len(batch_embeddings[0])
            if actual_dim != initial_embedding_dim:
                print(f"   ℹ️  Обнаружена размерность embeddings: {actual_dim} (ожидалась {initial_embedding_dim})")
                print(f"   ✅ Автоматически обновляю конфигурацию для работы с размерностью {actual_dim}")
                # Обновляем размерность в indexer
                indexer.embedding_dim = actual_dim
                # Обновляем информацию в трекере
                tracker.update_stats(embedding_dim=actual_dim)
        
        # Обновляем прогресс генерации embeddings
        embeddings_progress = 40.0 + (batch_idx / total_batches) * 30.0  # Шаг 5: 40-70%
        mode_label = "mock" if embedding_service.mock_mode else "GigaChat API"
        tracker.update_progress(
            embeddings_progress,
            f"Генерация embeddings ({mode_label}): {min(i + batch_size, len(chunk_texts))}/{len(chunk_texts)} чанков"
        )
        tracker.update_stats(embeddings_generated=len(all_embeddings))
        print(f"   Обработано {min(i + batch_size, len(chunk_texts))}/{len(chunk_texts)} чанков...")
        
        # Добавляем небольшую задержку между батчами для избежания rate limiting
        # (только если не последний батч)
        if batch_idx < total_batches - 1:
            time.sleep(0.5)  # Задержка 0.5 секунды между батчами
    
    print(f"✅ Сгенерировано embeddings: {len(all_embeddings)}")
    print(f"   📊 Режим работы: {actual_mode}")
    
    # Индексация в Qdrant
    tracker.update_progress(70.0, f"Индексация в Qdrant (коллекция: {collection_name})...")
    print()
    print(f"   Индексация в Qdrant (коллекция: {collection_name})...")
    print("   Коллекция будет создана автоматически, если не существует.")
    
    try:
        indexer.index_chunks(all_chunks, all_embeddings)
        print(f"✅ Индексация завершена успешно!")
        tracker.update_stats(chunks_indexed=len(all_embeddings))
        tracker.update_progress(100.0, "Индексация завершена успешно!")
    except Exception as e:
        error_msg = f"Ошибка при индексации: {e}"
        print(f"❌ {error_msg}")
        tracker.fail(error_msg)
        return 1
    
    # Получаем фактическую размерность (может быть обновлена после первого ответа API)
    final_embedding_dim = embedding_service.embedding_dim
    
    # Сохранение метаданных в PostgreSQL
    if doc_repository:
        print()
        print("[Дополнительно] Сохранение метаданных в PostgreSQL...")
        saved_count = 0
        for doc in all_documents:
            try:
                s3_key = doc.metadata.get("s3_key") or doc.metadata.get("file_path")
                # Если это локальный путь, пытаемся преобразовать в S3 ключ
                if s3_key and not s3_key.startswith(("hr/", "it/", "compliance/", "onboarding/")):
                    # Извлекаем категорию из пути
                    path_parts = s3_key.replace("\\", "/").split("/")
                    if "hr" in path_parts:
                        category_idx = path_parts.index("hr")
                        s3_key = "/".join(path_parts[category_idx:])
                    elif "it" in path_parts:
                        category_idx = path_parts.index("it")
                        s3_key = "/".join(path_parts[category_idx:])
                    elif "compliance" in path_parts:
                        category_idx = path_parts.index("compliance")
                        s3_key = "/".join(path_parts[category_idx:])
                    elif "onboarding" in path_parts:
                        category_idx = path_parts.index("onboarding")
                        s3_key = "/".join(path_parts[category_idx:])
                
                if s3_key:
                    # Создаем метаданные документа
                    doc_metadata = DocumentMetadata(
                        file_path=doc.metadata.get("file_path", ""),
                        s3_key=s3_key if s3_key.startswith(("hr/", "it/", "compliance/", "onboarding/")) else None,
                        category=doc.metadata.get("category", "unknown"),
                        filename=doc.metadata.get("filename", ""),
                        embedding_mode=actual_mode,
                        embedding_dim=final_embedding_dim,
                        metadata=doc.metadata
                    )
                    
                    # Сохраняем документ
                    doc_id = doc_repository.save_document(doc_metadata)
                    
                    # Отмечаем как проиндексированный
                    if s3_key.startswith(("hr/", "it/", "compliance/", "onboarding/")):
                        doc_repository.mark_as_indexed(s3_key, actual_mode, final_embedding_dim)
                    
                    saved_count += 1
            except Exception as e:
                print(f"   ⚠️  Предупреждение: не удалось сохранить метаданные для {doc.metadata.get('filename', 'unknown')}: {e}")
        
        if saved_count > 0:
            print(f"   ✅ Метаданные сохранены в PostgreSQL: {saved_count} документов")
    
    # Проверка результата
    tracker.complete("Индексация завершена успешно!")
    print()
    print("=" * 80)
    print("✅ INGESTION PIPELINE ЗАВЕРШЕН УСПЕШНО")
    print("=" * 80)
    print()
    
    print(f"📊 Статистика:")
    print(f"   - Загружено документов: {len(all_documents)}")
    print(f"   - Создано чанков: {len(all_chunks)}")
    print(f"   - Сгенерировано embeddings: {len(all_embeddings)}")
    print(f"   - Размерность embeddings: {final_embedding_dim}")
    print(f"   - Режим embeddings: {actual_mode}")
    print(f"   - Индексировано в Qdrant: {len(all_embeddings)}")
    print(f"   - Коллекция: {collection_name}")
    if doc_repository:
        print(f"   - Метаданные сохранены в PostgreSQL: {saved_count if 'saved_count' in locals() else 0} документов")
    print()
    if embedding_service.mock_mode:
        print("⚠️  ВНИМАНИЕ: Использованы mock embeddings!")
        print("   Mock embeddings не отражают семантическое сходство текстов.")
        print("   Для production рекомендуется использовать реальный GigaChat Embeddings API.")
        print("   Подробнее: https://developers.sber.ru/portal/products/gigachat")
    else:
        print("✅ Использован реальный GigaChat Embeddings API")
    print()
    print("Теперь можно запускать FastAPI сервер и Streamlit UI!")
    print()
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

