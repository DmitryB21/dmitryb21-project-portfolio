# Устранение проблем с Mock Mode

## Проблема: Нерелевантные ответы в Mock Mode

### Симптомы

- В UI показывается ошибка: "GigaChat OAuth ключ не установлен"
- Ответы не соответствуют запросу (например, на вопрос про интернет приходит ответ про HR/оценку)
- Метрики показывают низкие значения: `faithfulness: 0.5`, `answer_relevancy: 0.6`

### Причины

1. **GIGACHAT_AUTH_KEY не установлен** - система автоматически переходит в mock mode
2. **Mock mode возвращает весь контекст** без фильтрации по релевантности
3. **Retrieved chunks нерелевантны запросу** - проблема с embeddings или поиском в Qdrant

### Решения

#### 1. Настройка GigaChat OAuth 2.0

**Проблема:** В `.env` используется старый формат `GIGACHAT_API_KEY` вместо `GIGACHAT_AUTH_KEY`

**Решение:**
1. Получите Client ID и Client Secret в личном кабинете GigaChat
2. Создайте Authorization Key (Base64 от `Client ID:Client Secret`)
3. Добавьте в `.env`:
   ```env
   GIGACHAT_AUTH_KEY=ваш_base64_encoded_auth_key
   GIGACHAT_SCOPE=GIGACHAT_API_PERS
   ```
4. Удалите старую строку `GIGACHAT_API_KEY` из `.env`

См. подробные инструкции в `docs/gigachat_oauth_setup.md`

#### 2. Проверка Retrieved Chunks

**Проблема:** Retrieved chunks нерелевантны запросу

**Решение:**
1. Проверьте логи через `/admin/logs` endpoint
2. Найдите запись с `action: "retrieve_chunks"` и `metadata.chunks_info`
3. Проверьте:
   - Какие чанки были получены
   - Их score (релевантность)
   - Содержимое чанков

**Пример проверки:**
```bash
curl http://localhost:8000/admin/logs?limit=50 | jq '.logs[] | select(.action == "retrieve_chunks") | .metadata.chunks_info'
```

#### 3. Улучшение качества поиска

Если retrieved chunks нерелевантны:

1. **Проверьте индексацию:**
   ```bash
   python scripts/check_indexing_status.py
   ```

2. **Переиндексируйте документы:**
   ```bash
   python scripts/run_ingestion.py
   ```

3. **Используйте reranking:**
   - Включите reranking в запросе через API
   - Это улучшит релевантность retrieved chunks

#### 4. Использование Mock Mode

Если вы хотите использовать mock mode для тестирования:

1. **Включите mock mode явно:**
   ```env
   GIGACHAT_MOCK_MODE=true
   ```

2. **Поймите ограничения:**
   - Mock mode просто возвращает первый retrieved chunk
   - Нет реальной генерации ответа через LLM
   - Ответы могут быть нерелевантными, если retrieved chunks нерелевантны

3. **Для production используйте реальный API:**
   - Настройте `GIGACHAT_AUTH_KEY`
   - Убедитесь, что интернет доступен
   - Проверьте статус через UI

### Диагностика

#### Шаг 1: Проверка статуса сервисов

В Streamlit UI проверьте секцию "Статус сервисов":
- Qdrant должен быть доступен
- GigaChat API должен показывать статус (доступен или mock mode)

#### Шаг 2: Проверка логов

```bash
# Получить последние логи
curl http://localhost:8000/admin/logs?limit=20

# Найти информацию о retrieved chunks
curl http://localhost:8000/admin/logs?limit=50 | jq '.logs[] | select(.action == "retrieve_chunks")'
```

#### Шаг 3: Проверка retrieved chunks

В логах найдите `metadata.chunks_info` для запроса:
- Проверьте `text_preview` - соответствует ли содержимое запросу?
- Проверьте `score` - высокий ли score у чанков?
- Проверьте `metadata` - правильная ли категория документов?

### Примеры проблем и решений

#### Проблема: "Ожидание целей и критериев оценки" на вопрос про интернет

**Причина:** Retrieved chunks содержат HR документы вместо IT документов

**Решение:**
1. Проверьте, что в Qdrant есть IT документы
2. Проверьте embeddings - возможно, они нерелевантны
3. Переиндексируйте документы с правильными категориями

#### Проблема: Mock mode возвращает весь контекст

**Причина:** Mock mode в старых версиях возвращал весь контекст

**Решение:** Обновлено в последней версии - mock mode теперь возвращает только первый (самый релевантный) источник

### Рекомендации

1. **Всегда используйте реальный API для production**
   - Mock mode предназначен только для тестирования
   - Реальный API обеспечивает лучшую релевантность ответов

2. **Проверяйте retrieved chunks**
   - Если chunks нерелевантны, проблема в поиске, а не в генерации
   - Используйте reranking для улучшения качества

3. **Мониторьте метрики**
   - `faithfulness` < 0.7 - проблема с генерацией или контекстом
   - `answer_relevancy` < 0.7 - проблема с релевантностью retrieved chunks

4. **Логируйте всё**
   - Используйте `/admin/logs` для отладки
   - Проверяйте `chunks_info` в метаданных

