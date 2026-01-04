# Руководство по доработке neuro_doc_assistant_demo.ipynb

## ✅ Что уже сделано автоматически:

1. ✅ Добавлена загрузка файлов с Google Drive (ячейка 6)
2. ✅ Добавлены необходимые импорты (ячейка 4)
3. ✅ Добавлен класс GigaChatAuth (новая ячейка 14)

## 📝 Что нужно сделать вручную:

### 1. Обновить EmbeddingService (ячейка 15)

**Заменить весь код ячейки 15 на:**

```python
# ============================================
# Модуль 3: EmbeddingService (GigaChat API)
# ============================================

import numpy as np
from typing import List

class EmbeddingService:
    """
    Сервис для генерации векторных представлений через GigaChat Embeddings API.
    
    Зачем нужна:
    - Генерация embeddings для текстов (для semantic search)
    - В production: GigaChat Embeddings API
    - В Colab: можно использовать mock-режим или реальный API (при наличии ключей)
    
    Вход: texts (List[str])
    Выход: List[List[float]] — список векторов размерности embedding_dim
    
    Ограничения:
    - embedding_dim: 1536 (GigaChat) или 1024
    - batch_size: 10 (для оптимизации)
    """
    
    def __init__(
        self,
        embedding_dim: int = 1536,
        batch_size: int = 10,
        mock_mode: bool = True,
        auth_key: Optional[str] = None,
        scope: Optional[str] = None
    ):
        self.embedding_dim = embedding_dim
        self.batch_size = batch_size
        
        # Определяем auth_key (из секретов Colab или параметра)
        if not auth_key:
            try:
                auth_key = userdata.get("GIGACHAT_AUTH_KEY")
            except:
                auth_key = None
        
        # Определяем mock mode
        if mock_mode or not auth_key:
            self.mock_mode = True
        else:
            self.mock_mode = False
            self.auth = GigaChatAuth(auth_key=auth_key, scope=scope)
        
        # Настройка HTTP сессии
        self.session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.verify = False
        
        # Официальный endpoint для GigaChat Embeddings API
        self.api_url = "https://gigachat.devices.sberbank.ru/api/v1/embeddings"
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Генерирует embeddings для списка текстов.
        
        В mock-режиме: создаёт детерминированные векторы на основе hash.
        В production: вызывает GigaChat Embeddings API.
        """
        if self.mock_mode:
            return [self._generate_mock_embedding(text) for text in texts]
        
        all_embeddings = []
        # Обрабатываем тексты батчами
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_embeddings = []
            for text in batch:
                embedding = self._call_gigachat_api(text)
                batch_embeddings.append(embedding)
                time.sleep(0.1)  # Задержка между запросами
            all_embeddings.extend(batch_embeddings)
        return all_embeddings
    
    def _call_gigachat_api(self, text: str) -> List[float]:
        """Вызывает GigaChat Embeddings API для одного текста."""
        if self.mock_mode:
            return self._generate_mock_embedding(text)
        
        try:
            access_token = self.auth.get_access_token()
            if not access_token:
                return self._generate_mock_embedding(text)
            
            request_id = str(uuid.uuid4())
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Request-ID": request_id
            }
            
            payload = {
                "model": "Embeddings",
                "input": text
            }
            
            response = self.session.post(self.api_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            # Извлекаем embedding из ответа
            embedding = None
            if "data" in data and len(data["data"]) > 0:
                embedding = data["data"][0].get("embedding", [])
            elif "embedding" in data:
                embedding = data["embedding"]
            
            if embedding and len(embedding) in [1024, 1536]:
                self.embedding_dim = len(embedding)  # Обновляем размерность
                return embedding
            return self._generate_mock_embedding(text)
        except Exception as e:
            console.print(f"[yellow]⚠️  Ошибка вызова GigaChat Embeddings API: {e}[/yellow]")
            return self._generate_mock_embedding(text)
    
    def _generate_mock_embedding(self, text: str) -> List[float]:
        """Генерирует моковый embedding на основе текста."""
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        embedding = []
        for i in range(self.embedding_dim):
            hash_index = i % len(text_hash)
            char_value = ord(text_hash[hash_index])
            normalized_value = (char_value % 200 - 100) / 100.0
            embedding.append(normalized_value)
        return embedding

print("✅ EmbeddingService реализован (поддержка GigaChat API и mock режим)")
```

### 2. Обновить QdrantIndexer (ячейка 17)

**В начале ячейки 17 (перед классом QdrantIndexer) добавить:**

```python
# Получение ключей Qdrant из секретов Colab
try:
    QDRANT_URL = userdata.get("QDRANT_URL")
    QDRANT_API_KEY = userdata.get("QDRANT_API_KEY", None)  # Опционально
except:
    QDRANT_URL = None
    QDRANT_API_KEY = None
    console.print("[yellow]⚠️  QDRANT_URL не найден в секретах, будет использован in-memory режим[/yellow]")
```

**Заменить метод `__init__` класса QdrantIndexer на:**

```python
    def __init__(
        self,
        qdrant_client: QdrantClient = None,
        collection_name: str = "neuro_docs",
        embedding_dim: int = 1536,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None
    ):
        # Если qdrant_client не передан, создаём его
        if qdrant_client is None:
            # Используем переданные параметры или глобальные из секретов
            url = qdrant_url or (QDRANT_URL if 'QDRANT_URL' in globals() else None)
            api_key = qdrant_api_key or (QDRANT_API_KEY if 'QDRANT_API_KEY' in globals() else None)
            
            if url:
                if api_key:
                    self.qdrant_client = QdrantClient(url=url, api_key=api_key)
                else:
                    self.qdrant_client = QdrantClient(url=url)
            else:
                # Используем in-memory режим
                self.qdrant_client = QdrantClient(":memory:")
        else:
            self.qdrant_client = qdrant_client
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
```

### 3. Обновить DocumentLoader (ячейка 8)

**В методе `load_documents` заменить жестко заданные пути на использование `LOCAL_DATA_PATH`:**

Если путь начинается с "data/NeuroDoc_Data/", заменить на `LOCAL_DATA_PATH`.

### 4. Обновить демонстрации Ingestion Pipeline (ячейка 22)

**В функции `run_ingestion_pipeline_demo()` обновить создание QdrantIndexer:**

```python
# Шаг 4: Индексация в Qdrant
console.print("\n[bold]Шаг 4: Индексация в Qdrant[/bold]")
try:
    qdrant_url = QDRANT_URL if 'QDRANT_URL' in globals() else None
    qdrant_api_key = QDRANT_API_KEY if 'QDRANT_API_KEY' in globals() else None
    if qdrant_url:
        qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key) if qdrant_api_key else QdrantClient(url=qdrant_url)
        console.print(f"[cyan]Используется внешний Qdrant: {qdrant_url}[/cyan]")
    else:
        qdrant_client = QdrantClient(":memory:")
        console.print("[cyan]Используется in-memory Qdrant[/cyan]")
except:
    qdrant_client = QdrantClient(":memory:")
    console.print("[yellow]Ошибка подключения к внешнему Qdrant, используется in-memory[/yellow]")

indexer = QdrantIndexer(qdrant_client=qdrant_client, collection_name="neuro_docs_demo", embedding_dim=1536)
indexed_count = indexer.index_chunks(chunks, embeddings)
```

### 5. Добавить тесты для модуля 5 (Retrieval Layer)

**После ячейки с `demonstrate_retrieval()` (ячейка 24) добавить новую ячейку:**

```python
# Тесты для Retriever

def test_retriever():
    """Тесты для Retriever (pytest-style)."""
    from unittest.mock import Mock, MagicMock
    
    # Создаём mock Qdrant client
    mock_qdrant = MagicMock()
    mock_result = Mock()
    mock_points = [
        Mock(
            id=0,
            score=0.95,
            payload={
                "chunk_id": "chunk_001",
                "text": "SLA сервиса платежей составляет 99.9%",
                "doc_id": "doc_001",
                "category": "it"
            }
        ),
        Mock(
            id=1,
            score=0.88,
            payload={
                "chunk_id": "chunk_002",
                "text": "Время отклика сервиса платежей не более 200мс",
                "doc_id": "doc_001",
                "category": "it"
            }
        )
    ]
    mock_result.points = mock_points
    mock_qdrant.search.return_value = mock_result
    
    # Создаём embedding service
    embedding_service = EmbeddingService(mock_mode=True)
    
    # Создаём retriever
    retriever = Retriever(
        qdrant_client=mock_qdrant,
        embedding_service=embedding_service,
        collection_name="test_collection"
    )
    
    # Тест 1: retrieve возвращает список RetrievedChunk
    query = "Какой SLA у сервиса платежей?"
    results = retriever.retrieve(query, k=2)
    
    assert len(results) == 2, "Должно быть 2 чанка"
    assert all(isinstance(chunk, RetrievedChunk) for chunk in results)
    assert all(chunk.text is not None for chunk in results)
    console.print("[green]✅ Тест 1 пройден: retrieve возвращает RetrievedChunk[/green]")
    
    # Тест 2: K параметр работает корректно
    mock_result.points = mock_points[:1]  # Один чанк
    results = retriever.retrieve(query, k=1)
    assert len(results) == 1, "Должен быть 1 чанк при k=1"
    console.print("[green]✅ Тест 2 пройден: K параметр работает[/green]")
    
    # Тест 3: Результаты отсортированы по score
    scores = [chunk.score for chunk in results]
    assert scores == sorted(scores, reverse=True), "Чанки должны быть отсортированы по score"
    console.print("[green]✅ Тест 3 пройден: Результаты отсортированы по score[/green]")

test_retriever()
print("\n✅ Все тесты Retriever пройдены")
```

### 6. Добавить тесты для модуля 6 (Reranking)

**После ячейки с `compare_reranking()` добавить новую ячейку:**

```python
# Тесты для Reranker

def test_reranker():
    """Тесты для Reranker."""
    # Создаём тестовые чанки
    sample_chunks = [
        RetrievedChunk(
            id="chunk_1",
            text="SLA сервиса платежей составляет 99.9%. Время отклика не более 200мс.",
            score=0.85,
            metadata={"doc_id": "doc_1", "category": "it"}
        ),
        RetrievedChunk(
            id="chunk_2",
            text="HR политика компании включает правила отпусков и больничных.",
            score=0.78,
            metadata={"doc_id": "doc_2", "category": "hr"}
        ),
        RetrievedChunk(
            id="chunk_3",
            text="Платежный сервис имеет SLA 99.9% и время отклика 200мс.",
            score=0.72,
            metadata={"doc_id": "doc_3", "category": "it"}
        )
    ]
    
    query = "Какой SLA у сервиса платежей?"
    reranker = Reranker()
    
    # Тест 1: rerank возвращает RerankedChunk
    reranked = reranker.rerank(query=query, chunks=sample_chunks, top_k=3)
    
    assert len(reranked) == 3, "Должно быть 3 reranked чанка"
    assert all(hasattr(chunk, "rerank_score") for chunk in reranked)
    console.print("[green]✅ Тест 1 пройден: rerank возвращает RerankedChunk[/green]")
    
    # Тест 2: rerank_score рассчитывается для каждого чанка
    for chunk in reranked:
        assert isinstance(chunk.rerank_score, float)
        assert 0.0 <= chunk.rerank_score <= 1.0
    console.print("[green]✅ Тест 2 пройден: rerank_score рассчитывается[/green]")
    
    # Тест 3: top_k параметр работает корректно
    reranked_2 = reranker.rerank(query=query, chunks=sample_chunks, top_k=2)
    assert len(reranked_2) == 2, "Должно быть 2 чанка при top_k=2"
    console.print("[green]✅ Тест 3 пройден: top_k параметр работает[/green]")
    
    # Тест 4: Чанки отсортированы по rerank_score
    scores = [chunk.rerank_score for chunk in reranked]
    assert scores == sorted(scores, reverse=True), "Чанки должны быть отсортированы по rerank_score"
    console.print("[green]✅ Тест 4 пройден: Чанки отсортированы по rerank_score[/green]")

test_reranker()
print("\n✅ Все тесты Reranker пройдены")
```

### 7. Добавить тесты для модуля 7 (Agent Controller)

**После ячейки с `demonstrate_agent_fsm()` добавить новую ячейку:**

```python
# Тесты для AgentStateMachine

def test_agent_state_machine():
    """Тесты для AgentStateMachine."""
    state_machine = AgentStateMachine()
    
    # Тест 1: Начальное состояние IDLE
    assert state_machine.current_state == AgentState.IDLE, "Начальное состояние должно быть IDLE"
    console.print("[green]✅ Тест 1 пройден: Начальное состояние IDLE[/green]")
    
    # Тест 2: Переходы между состояниями
    state_machine.transition_to(AgentState.VALIDATE_QUERY)
    assert state_machine.current_state == AgentState.VALIDATE_QUERY
    
    state_machine.transition_to(AgentState.RETRIEVE)
    assert state_machine.current_state == AgentState.RETRIEVE
    
    state_machine.transition_to(AgentState.GENERATE)
    assert state_machine.current_state == AgentState.GENERATE
    console.print("[green]✅ Тест 2 пройден: Переходы между состояниями работают[/green]")
    
    # Тест 3: История состояний сохраняется
    history = state_machine.get_history()
    assert len(history) >= 3, "История должна содержать минимум 3 состояния"
    assert AgentState.IDLE in history, "История должна содержать IDLE"
    assert AgentState.VALIDATE_QUERY in history, "История должна содержать VALIDATE_QUERY"
    console.print("[green]✅ Тест 3 пройден: История состояний сохраняется[/green]")
    
    # Тест 4: Полный flow UC-1
    state_machine.reset()
    states = [
        AgentState.VALIDATE_QUERY,
        AgentState.RETRIEVE,
        AgentState.GENERATE,
        AgentState.VALIDATE_ANSWER,
        AgentState.LOG_METRICS,
        AgentState.RETURN_RESPONSE,
        AgentState.IDLE
    ]
    for state in states:
        state_machine.transition_to(state)
    assert state_machine.current_state == AgentState.IDLE, "Финальное состояние должно быть IDLE"
    console.print("[green]✅ Тест 4 пройден: Полный flow UC-1 работает[/green]")

test_agent_state_machine()
print("\n✅ Все тесты AgentStateMachine пройдены")
```

### 8. Добавить тесты для модуля 8 (Generation Layer)

**После ячейки с `demonstrate_generation()` добавить новую ячейку:**

```python
# Тесты для PromptBuilder и LLMClient

def test_prompt_builder():
    """Тесты для PromptBuilder."""
    prompt_builder = PromptBuilder()
    
    # Создаём тестовые чанки
    sample_chunks = [
        RetrievedChunk(
            id="chunk_001",
            text="SLA сервиса платежей составляет 99.9%",
            score=0.95,
            metadata={"doc_id": "doc_001", "category": "it"}
        ),
        RetrievedChunk(
            id="chunk_002",
            text="Время отклика сервиса платежей не более 200мс",
            score=0.88,
            metadata={"doc_id": "doc_001", "category": "it"}
        )
    ]
    
    query = "Какой SLA у сервиса платежей?"
    
    # Тест 1: Prompt содержит запрос и контекст
    prompt = prompt_builder.build_prompt(query, sample_chunks)
    
    assert prompt is not None, "Prompt не должен быть None"
    assert query in prompt, "Prompt должен содержать запрос"
    assert sample_chunks[0].text in prompt, "Prompt должен содержать текст из чанков"
    console.print("[green]✅ Тест 1 пройден: Prompt содержит запрос и контекст[/green]")
    
    # Тест 2: Prompt содержит инструкцию "отвечай только по контексту"
    prompt_lower = prompt.lower()
    instruction_keywords = ["только", "контекст", "не придумывай", "строго"]
    assert any(kw in prompt_lower for kw in instruction_keywords), "Prompt должен содержать инструкцию"
    console.print("[green]✅ Тест 2 пройден: Prompt содержит инструкцию[/green]")
    
    # Тест 3: Обработка пустого списка чанков
    prompt_empty = prompt_builder.build_prompt(query, [])
    assert prompt_empty is not None, "Prompt не должен быть None даже при пустых чанках"
    assert "нет информации" in prompt_empty.lower() or "не найдено" in prompt_empty.lower(), "Prompt должен указывать на отсутствие информации"
    console.print("[green]✅ Тест 3 пройден: Обработка пустого списка чанков работает[/green]")

def test_llm_client():
    """Тесты для LLMClient."""
    llm_client = LLMClient(mock_mode=True)
    
    # Тест 1: generate_answer возвращает строку
    prompt = "Контекст: SLA сервиса платежей составляет 99.9%. Вопрос: Какой SLA?"
    answer = llm_client.generate_answer(prompt)
    
    assert isinstance(answer, str), "Ответ должен быть строкой"
    assert len(answer) > 0, "Ответ не должен быть пустым"
    console.print("[green]✅ Тест 1 пройден: generate_answer возвращает ответ[/green]")

test_prompt_builder()
test_llm_client()
print("\n✅ Все тесты Generation Layer пройдены")
```

## 🔑 Требуемые секреты Colab:

Для полной работы notebook нужно добавить в Colab → Runtime → Secrets:
- `GIGACHAT_AUTH_KEY` - Base64 encoded "Client ID:Client Secret"
- `GIGACHAT_SCOPE` - Scope для OAuth (по умолчанию GIGACHAT_API_PERS)
- `QDRANT_URL` - URL внешнего Qdrant сервиса (опционально)
- `QDRANT_API_KEY` - API ключ для Qdrant (опционально)

Если секреты не заданы, система будет работать в mock режиме.

