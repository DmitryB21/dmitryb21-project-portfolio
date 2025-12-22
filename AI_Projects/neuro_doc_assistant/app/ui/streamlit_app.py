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
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
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
        if services_status:
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
        else:
            st.warning("⚠️ Не удалось получить статус сервисов")
        
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
    
    # Инициализация истории чата
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Отображение истории чата
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
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
    
    # Форма для ввода вопроса
    if prompt := st.chat_input("Задайте вопрос по документации..."):
        # Добавляем вопрос пользователя в историю
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Отображаем вопрос
        with st.chat_message("user"):
            st.write(prompt)
        
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
                
                # Добавляем ответ в историю
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
            else:
                st.error("Не удалось получить ответ от агента. Проверьте логи API.")
    
    # Кнопка очистки истории
    if st.session_state.messages:
        if st.button("🗑️ Очистить историю"):
            st.session_state.messages = []
            st.rerun()


if __name__ == "__main__":
    main()

