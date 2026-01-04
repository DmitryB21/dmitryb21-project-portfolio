"""
Streamlit Demo UI для Neuro_Doc_Assistant
"""

import streamlit as st
import requests
import os
from typing import List, Dict, Any
from datetime import datetime


# Конфигурация API
def detect_api_port() -> str:
    """Автоматическое определение порта API (8000 или 8001)"""
    # Сначала проверяем переменную окружения
    env_url = os.getenv("API_BASE_URL")
    if env_url:
        return env_url
    
    # Проверяем порт 8000
    try:
        response = requests.get("http://localhost:8000/health", timeout=1)
        if response.status_code == 200:
            return "http://localhost:8000"
    except Exception:
        pass
    
    # Проверяем порт 8001
    try:
        response = requests.get("http://localhost:8001/health", timeout=1)
        if response.status_code == 200:
            return "http://localhost:8001"
    except Exception:
        pass
    
    # По умолчанию возвращаем 8000
    return "http://localhost:8000"

API_BASE_URL = detect_api_port()
API_ASK_ENDPOINT = f"{API_BASE_URL}/ask"
API_HEALTH_ENDPOINT = f"{API_BASE_URL}/health"
API_METRICS_ENDPOINT = f"{API_BASE_URL}/admin/metrics"
API_SERVICES_STATUS_ENDPOINT = f"{API_BASE_URL}/admin/services/status"
API_INDEXING_START_ENDPOINT = f"{API_BASE_URL}/admin/indexing/start"
API_INDEXING_STATUS_ENDPOINT = f"{API_BASE_URL}/admin/indexing/status"
API_INDEXING_RESET_ENDPOINT = f"{API_BASE_URL}/admin/indexing/reset"


def check_api_health() -> bool:
    """Проверка доступности API"""
    try:
        response = requests.get(API_HEALTH_ENDPOINT, timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def get_services_status() -> Dict[str, Any]:
    """Получение статуса внешних сервисов (Qdrant и GigaChat API)"""
    try:
        response = requests.get(API_SERVICES_STATUS_ENDPOINT, timeout=5)
        response.raise_for_status()  # Вызовет исключение для статусов 4xx/5xx
        return response.json()
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.RequestException as e:
        # Логируем ошибку для отладки (в production можно использовать logger)
        print(f"Ошибка при запросе статуса сервисов: {e}")
        return None
    except Exception as e:
        # Логируем неожиданные ошибки
        print(f"Неожиданная ошибка при получении статуса сервисов: {e}")
        return None


def ask_agent(query: str, k: int = 3) -> Dict[str, Any]:
    """
    Отправка запроса к агенту через API
    
    Args:
        query: Вопрос пользователя
        k: Количество retrieved документов
    
    Returns:
        Ответ от API с answer, sources, metrics
    """
    try:
        response = requests.post(
            API_ASK_ENDPOINT,
            json={"query": query, "k": k},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Ошибка при запросе к API: {str(e)}")
        return None


def display_source(source: Dict[str, Any], index: int):
    """Отображение источника (чанка)"""
    with st.expander(f"📄 Источник {index + 1}: {source.get('id', 'N/A')}"):
        st.write("**Текст:**")
        st.write(source.get("text", ""))
        
        metadata = source.get("metadata", {})
        if metadata:
            st.write("**Метаданные:**")
            col1, col2 = st.columns(2)
            with col1:
                if "category" in metadata:
                    st.write(f"**Категория:** {metadata['category']}")
                if "file_path" in metadata:
                    st.write(f"**Файл:** {metadata['file_path']}")
            with col2:
                if "doc_id" in metadata:
                    st.write(f"**Doc ID:** {metadata['doc_id']}")


def display_metrics(metrics: Dict[str, float]):
    """Отображение метрик качества"""
    if not metrics:
        return
    
    st.subheader("📊 Метрики качества")
    
    # Основные метрики
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if "precision_at_3" in metrics:
            precision = metrics["precision_at_3"]
            st.metric("Precision@3", f"{precision:.2%}")
    
    with col2:
        if "faithfulness" in metrics:
            faithfulness = metrics["faithfulness"]
            st.metric("Faithfulness", f"{faithfulness:.2f}")
    
    with col3:
        if "answer_relevancy" in metrics:
            relevancy = metrics["answer_relevancy"]
            st.metric("Answer Relevancy", f"{relevancy:.2f}")
    
    # Latency
    if "latency_ms" in metrics:
        latency = metrics["latency_ms"]
        st.metric("⏱️ Latency", f"{latency:.0f} ms")


def main():
    """Основная функция Streamlit приложения"""
    
    # Настройка страницы
    st.set_page_config(
        page_title="Neuro_Doc_Assistant",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Заголовок
    st.title("🧠 Neuro_Doc_Assistant")
    st.markdown("**RAG + AI-Agent для работы с внутренней документацией компании**")
    
    # Создаём вкладки для основного контента
    tab1, tab2 = st.tabs(["💬 Чат", "⚙️ Управление данными"])
    
    # Sidebar с настройками
    with st.sidebar:
        st.header("⚙️ Настройки")
        
        # Проверка API
        api_status = check_api_health()
        if api_status:
            st.success("✅ API доступен")
        else:
            st.error("❌ API недоступен")
            st.info(f"Проверьте, что API запущен на {API_BASE_URL}")
            st.stop()
        
        st.divider()
        
        # Статус внешних сервисов
        st.subheader("🔌 Статус сервисов")
        
        services_status = get_services_status()
        if not services_status:
            st.warning("⚠️ Не удалось получить статус сервисов. Проверьте, что API запущен и доступен.")
            st.info(f"Попытка подключения к: {API_SERVICES_STATUS_ENDPOINT}")
            if st.button("🔄 Обновить статус", key="refresh_services_status"):
                st.rerun()
        else:
            # Qdrant статус
            qdrant_status = services_status.get("qdrant", {})
            qdrant_available = qdrant_status.get("available", False)
            qdrant_message = qdrant_status.get("message", "Статус неизвестен")
            qdrant_details = qdrant_status.get("details", {})
            
            if qdrant_available:
                st.success(f"**Qdrant:** {qdrant_message}")
                if qdrant_details:
                    with st.expander("📊 Детали Qdrant"):
                        if "points_count" in qdrant_details:
                            st.metric("Точек в коллекции", qdrant_details["points_count"])
                        if "vector_size" in qdrant_details:
                            st.write(f"**Размерность векторов:** {qdrant_details['vector_size']}")
                        if "distance" in qdrant_details:
                            st.write(f"**Метрика расстояния:** {qdrant_details['distance']}")
                        if "collection_name" in qdrant_details:
                            st.write(f"**Коллекция:** {qdrant_details['collection_name']}")
            else:
                st.error(f"**Qdrant:** {qdrant_message}")
                if qdrant_details:
                    with st.expander("⚠️ Детали ошибки"):
                        st.json(qdrant_details)
            
            st.divider()
            
            # GigaChat API статус
            gigachat_status = services_status.get("gigachat_api", {})
            gigachat_available = gigachat_status.get("available", False)
            gigachat_message = gigachat_status.get("message", "Статус неизвестен")
            gigachat_details = gigachat_status.get("details", {})
            
            if gigachat_available:
                st.success(f"**GigaChat API:** {gigachat_message}")
            else:
                # Для mock mode показываем предупреждение, а не ошибку
                if gigachat_details.get("mock_mode", False):
                    st.warning(f"**GigaChat API:** {gigachat_message}")
                else:
                    st.error(f"**GigaChat API:** {gigachat_message}")
            
            if gigachat_details:
                with st.expander("📊 Детали GigaChat API"):
                    # Показываем auth_key или api_key (для обратной совместимости)
                    if "auth_key_set" in gigachat_details:
                        st.write(f"**OAuth ключ:** {'✅ установлен' if gigachat_details['auth_key_set'] else '❌ не установлен'}")
                    elif "api_key_set" in gigachat_details:
                        st.write(f"**API ключ:** {'✅ установлен' if gigachat_details['api_key_set'] else '❌ не установлен'}")
                    
                    if "scope" in gigachat_details:
                        st.write(f"**Scope:** {gigachat_details['scope']}")
                    
                    if "mock_mode" in gigachat_details:
                        st.write(f"**Mock mode:** {'✅ включен' if gigachat_details['mock_mode'] else '❌ выключен'}")
                    
                    if "api_url" in gigachat_details:
                        st.write(f"**API URL:** {gigachat_details['api_url']}")
                    if "embeddings_url" in gigachat_details:
                        st.write(f"**Embeddings URL:** {gigachat_details['embeddings_url']}")
                    
                    # Показываем рекомендацию, если есть
                    if "recommendation" in gigachat_details:
                        st.warning(f"💡 **Рекомендация:** {gigachat_details['recommendation']}")
                    
                    # Показываем тип ошибки, если есть
                    if "error_type" in gigachat_details:
                        st.write(f"**Тип ошибки:** {gigachat_details['error_type']}")
                    
                    if "note" in gigachat_details:
                        st.info(gigachat_details["note"])
        
        st.divider()
        
        # Параметр K
        k = st.slider(
            "Количество retrieved документов (K)",
            min_value=1,
            max_value=10,
            value=3,
            help="Количество документов, которые будут извлечены из векторной базы"
        )
        
        st.divider()
        
        # Метрики системы
        st.subheader("📈 Системные метрики")
        try:
            metrics_response = requests.get(API_METRICS_ENDPOINT, timeout=2)
            if metrics_response.status_code == 200:
                system_metrics = metrics_response.json()
                agent_metrics = system_metrics.get("agent", {})
                
                st.metric("Всего запросов", agent_metrics.get("total_queries", 0))
                
                avg_latency = agent_metrics.get("average_latency_ms")
                if avg_latency:
                    st.metric("Средняя latency", f"{avg_latency:.0f} ms")
        except Exception:
            st.info("Метрики недоступны")
    
    # Вкладка "Чат"
    with tab1:
        # Инициализация истории чата
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Контейнер для поля ввода вверху
        with st.container():
            st.markdown("### 💬 Задайте вопрос")
            
            # Используем форму для поля ввода вверху
            with st.form("query_form", clear_on_submit=True):
                user_query = st.text_input(
                    "Введите ваш вопрос:",
                    placeholder="Задайте вопрос по документации...",
                    key="query_input"
                )
                submitted = st.form_submit_button("📤 Отправить", type="primary", use_container_width=True)
            
            # Кнопка очистки истории (вне формы)
            if st.session_state.messages:
                if st.button("🗑️ Очистить историю", use_container_width=True, key="clear_chat_history"):
                    st.session_state.messages = []
                    st.rerun()
        
        st.divider()
        
        # Контейнер для истории чата (ниже поля ввода)
        with st.container():
            # Обработка отправки запроса
            if submitted and user_query:
                prompt = user_query.strip()
                if prompt:
                    # Добавляем вопрос пользователя в историю
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    st.rerun()
            
            # Отображение истории чата (новые сообщения сверху, старые снизу)
            if st.session_state.messages:
                # Отображаем сообщения в обратном порядке (новые -> старые)
                # Последние сообщения будут первыми (сверху), старые - внизу
                for message in reversed(st.session_state.messages):
                    with st.chat_message(message["role"]):
                        st.write(message["content"])
                        
                        # Отображение источников для ответов агента
                        if message["role"] == "assistant" and "sources" in message:
                            st.subheader("📚 Источники")
                            for idx, source in enumerate(message["sources"]):
                                display_source(source, idx)
                        
                        # Отображение метрик для ответов агента
                        if message["role"] == "assistant" and "metrics" in message:
                            display_metrics(message["metrics"])
            
            # Обработка нового запроса (если только что добавили вопрос пользователя)
            if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                # Проверяем, не обработан ли уже этот запрос
                last_message = st.session_state.messages[-1]
                if "processed" not in last_message:
                    # Помечаем как обработанный
                    last_message["processed"] = True
                    prompt = last_message["content"]
                    
                    # Отправляем запрос к агенту
                    with st.chat_message("assistant"):
                        with st.spinner("🤔 Агент обрабатывает запрос..."):
                            response = ask_agent(prompt, k=k)
                        
                        if response:
                            answer = response.get("answer", "Ответ не получен")
                            sources = response.get("sources", [])
                            metrics = response.get("metrics", {})
                            
                            # Отображаем ответ
                            st.write(answer)
                            
                            # Добавляем ответ в историю (в конец списка - будет отображаться снизу)
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": answer,
                                "sources": sources,
                                "metrics": metrics
                            })
                            
                            # Отображаем источники
                            if sources:
                                st.subheader("📚 Источники")
                                for idx, source in enumerate(sources):
                                    display_source(source, idx)
                            
                            # Отображаем метрики
                            if metrics:
                                display_metrics(metrics)
                            
                            # Перезагружаем страницу для отображения нового ответа
                            st.rerun()
                        else:
                            st.error("Не удалось получить ответ от агента. Проверьте логи API.")
                            # Удаляем необработанный вопрос из истории при ошибке
                            if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                                st.session_state.messages.pop()
                            st.rerun()
    
    # Вкладка "Управление данными"
    with tab2:
        st.header("📊 Управление данными Qdrant")
        st.markdown("---")
        
        # Секция удаления векторов
        st.subheader("🗑️ Удаление векторов")
        st.info("⚠️ **Внимание:** Удаление коллекции приведёт к полной очистке всех векторов из Qdrant. Это действие необратимо!")
        
        collection_name = st.text_input(
            "Имя коллекции для удаления",
            value="neuro_docs",
            help="Имя коллекции, которую нужно удалить"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Удалить коллекцию", type="primary", use_container_width=True, key="delete_collection_btn"):
                try:
                    response = requests.delete(
                        f"{API_BASE_URL}/admin/qdrant/collection",
                        params={"collection_name": collection_name},
                        timeout=10
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    if result.get("success"):
                        st.success(f"✅ {result.get('message')}")
                        st.balloons()
                        # Обновляем страницу, чтобы сбросить статус индексации
                        st.rerun()
                    else:
                        st.warning(f"⚠️ {result.get('message')}")
                except requests.exceptions.RequestException as e:
                    st.error(f"❌ Ошибка при удалении коллекции: {str(e)}")
        
        with col2:
            if st.button("🔄 Обновить статус", use_container_width=True, key="refresh_collection_status_btn"):
                st.rerun()
        
        st.markdown("---")
        
        # Секция запуска индексации
        st.subheader("🔄 Запуск индексации")
        st.info("Запустите индексацию документов из `data/NeuroDoc_Data/` в Qdrant. Процесс выполняется в фоновом режиме.")
        
        # Получаем текущий статус индексации
        try:
            status_response = requests.get(API_INDEXING_STATUS_ENDPOINT, timeout=2)
            if status_response.status_code == 200:
                indexing_status = status_response.json()
            else:
                indexing_status = {"status": "idle", "progress": 0.0, "message": "", "stats": {}}
        except Exception:
            indexing_status = {"status": "idle", "progress": 0.0, "message": "", "stats": {}}
        
        # Отображаем текущий статус
        status = indexing_status.get("status", "idle")
        progress = indexing_status.get("progress", 0.0)
        current_step = indexing_status.get("current_step", "")
        message = indexing_status.get("message", "")
        stats = indexing_status.get("stats", {})
        
        # Кнопки управления - размещаем ПЕРЕД блоком автоматического обновления
        # чтобы они всегда были видны, даже при постоянном обновлении страницы
        col1, col2, col3 = st.columns(3)
        with col1:
            if status != "running":
                if st.button("🚀 Запустить индексацию", type="primary", use_container_width=True, key="start_indexing_btn"):
                    try:
                        with st.spinner("Запуск индексации..."):
                            response = requests.post(
                                API_INDEXING_START_ENDPOINT,
                                timeout=5
                            )
                            response.raise_for_status()
                            result = response.json()
                            
                            if result.get("success"):
                                st.success(f"✅ {result.get('message')}")
                                st.rerun()  # Обновляем страницу для отображения прогресса
                            else:
                                st.error(f"❌ {result.get('message')}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"❌ Ошибка при запуске индексации: {str(e)}")
        
        with col2:
            if st.button("🔄 Обновить статус", use_container_width=True, key="refresh_indexing_status_btn"):
                st.rerun()
        
        with col3:
            # Кнопка сброса всегда доступна (для сброса зависших процессов)
            # Определяем, нужно ли использовать принудительный сброс
            force_reset_needed = False
            if status == "running":
                # Проверяем, не зависла ли индексация (если идет больше 15 минут)
                started_at = indexing_status.get("started_at")
                if started_at:
                    try:
                        start_time = datetime.fromisoformat(started_at)
                        time_since_start = datetime.now() - start_time
                        # Если индексация идет больше 15 минут, предлагаем принудительный сброс
                        if time_since_start.total_seconds() > 15 * 60:
                            force_reset_needed = True
                            st.warning("⚠️ Индексация может быть зависшей (запущена более 15 минут назад)")
                    except Exception:
                        pass
                
                # Для запущенной индексации всегда предлагаем принудительный сброс
                force_reset = st.checkbox("Принудительный сброс", value=force_reset_needed, key="force_reset_checkbox", help="Используйте для зависших процессов")
            else:
                force_reset = False
            
            # Кнопка сброса всегда видна - без условий!
            button_label = "🔄 Сбросить статус" if status != "idle" else "🔄 Сбросить статус (принудительно)"
            button_clicked = st.button(button_label, use_container_width=True, key="reset_indexing_status_btn", help="Сбросить статус индексации в состояние 'idle'")
            
            if button_clicked:
                try:
                    with st.spinner("Сброс статуса..."):
                        # Используем параметр force для принудительного сброса или если статус running
                        params = {"force": "true"} if (force_reset or status == "running") else {}
                        response = requests.post(
                            API_INDEXING_RESET_ENDPOINT,
                            params=params,
                            timeout=10  # Увеличиваем timeout для надежности
                        )
                        response.raise_for_status()
                        result = response.json()
                        
                        if result.get("success"):
                            st.success(f"✅ {result.get('message')}")
                            st.rerun()
                        else:
                            st.warning(f"⚠️ {result.get('message', 'Не удалось сбросить статус')}")
                            if status == "running" and not force_reset:
                                st.info("💡 Попробуйте включить 'Принудительный сброс' для зависших процессов")
                except requests.exceptions.Timeout:
                    st.error("❌ Таймаут при сбросе статуса. Попробуйте еще раз или используйте скрипт force_reset_indexing.py")
                except requests.exceptions.RequestException as e:
                    st.error(f"❌ Ошибка при сбросе статуса: {str(e)}")
                    st.info("💡 Если проблема сохраняется, используйте скрипт: `python scripts/force_reset_indexing.py`")
        
        st.markdown("---")
        
        # Контейнер для динамического обновления
        status_container = st.container()
        
        with status_container:
            # Индикатор статуса
            if status == "running":
                st.info(f"🔄 **Индексация выполняется...**")
                
                # Режим работы embeddings (если доступен)
                if stats and "embedding_mode" in stats:
                    embedding_mode = stats["embedding_mode"]
                    if "Mock" in embedding_mode:
                        st.caption(f"⚠️ Режим: {embedding_mode}")
                    else:
                        st.caption(f"✅ Режим: {embedding_mode}")
                
                # Прогресс-бар
                progress_bar = st.progress(progress / 100.0)
                st.write(f"**Прогресс:** {progress:.1f}%")
                st.write(f"**Текущий шаг:** {current_step}")
                if message:
                    st.write(f"**Сообщение:** {message}")
                
                # Статистика
                if stats:
                    st.markdown("**📊 Статистика:**")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if "documents_loaded" in stats:
                            st.metric("Документов", stats["documents_loaded"])
                    with col2:
                        if "chunks_created" in stats:
                            st.metric("Чанков", stats["chunks_created"])
                    with col3:
                        if "embeddings_generated" in stats:
                            st.metric("Embeddings", stats["embeddings_generated"])
                    with col4:
                        if "chunks_indexed" in stats:
                            st.metric("Индексировано", stats["chunks_indexed"])
                    
                    # Режим работы embeddings
                    if "embedding_mode" in stats:
                        embedding_mode = stats["embedding_mode"]
                        if "Mock" in embedding_mode:
                            st.warning(f"⚠️ **Режим embeddings:** {embedding_mode}")
                            st.caption("Mock embeddings не отражают семантическое сходство текстов")
                        else:
                            st.info(f"✅ **Режим embeddings:** {embedding_mode}")
                
                # Автоматическое обновление каждые 2 секунды
                import time
                time.sleep(2)
                st.rerun()
            elif status == "completed":
                       st.success("✅ **Индексация завершена успешно!**")
                       if stats:
                           st.markdown("**📊 Финальная статистика:**")
                           col1, col2, col3, col4 = st.columns(4)
                           with col1:
                               if "documents_loaded" in stats:
                                   st.metric("Документов", stats["documents_loaded"])
                           with col2:
                               if "chunks_created" in stats:
                                   st.metric("Чанков", stats["chunks_created"])
                           with col3:
                               if "embeddings_generated" in stats:
                                   st.metric("Embeddings", stats["embeddings_generated"])
                           with col4:
                               if "chunks_indexed" in stats:
                                   st.metric("Индексировано", stats["chunks_indexed"])
                           
                           # Режим работы embeddings
                           if "embedding_mode" in stats:
                               embedding_mode = stats["embedding_mode"]
                               if "Mock" in embedding_mode:
                                   st.warning(f"⚠️ **Режим embeddings:** {embedding_mode}")
                                   st.caption("Mock embeddings не отражают семантическое сходство текстов. Для production рекомендуется использовать реальный GigaChat Embeddings API.")
                               else:
                                   st.success(f"✅ **Режим embeddings:** {embedding_mode}")
            elif status == "failed":
                st.error(f"❌ **Ошибка индексации:** {indexing_status.get('error', 'Неизвестная ошибка')}")
                if message:
                    st.write(f"**Детали:** {message}")
        
        # Информация о коллекции
        st.subheader("📊 Информация о коллекции")
        services_status = get_services_status()
        if services_status:
            qdrant_status = services_status.get("qdrant", {})
            qdrant_details = qdrant_status.get("details", {})
            
            if qdrant_details:
                col1, col2, col3 = st.columns(3)
                with col1:
                    if "points_count" in qdrant_details:
                        st.metric("Точек в коллекции", qdrant_details["points_count"])
                with col2:
                    if "vector_size" in qdrant_details:
                        st.metric("Размерность векторов", qdrant_details["vector_size"])
                with col3:
                    if "distance" in qdrant_details:
                        st.metric("Метрика расстояния", qdrant_details["distance"])


if __name__ == "__main__":
    main()

