# Настройка Prometheus и Grafana для мониторинга

## Текущее состояние

### Доступные метрики

Prometheus метрики уже собираются в приложении и доступны через endpoint:

**Endpoint:** `http://localhost:8000/admin/metrics/prometheus`

### Собираемые метрики

1. **neuro_doc_assistant_requests_total** (Counter)
   - Общее количество запросов к агенту

2. **neuro_doc_assistant_request_latency_seconds** (Histogram)
   - End-to-end latency запросов
   - Buckets: [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.3, 2.0, 5.0] секунд

3. **neuro_doc_assistant_retrieval_latency_seconds** (Histogram)
   - Latency поиска в Qdrant
   - Buckets: [0.01, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5] секунд

4. **neuro_doc_assistant_generation_latency_seconds** (Histogram)
   - Latency генерации ответа через LLM
   - Buckets: [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0] секунд

5. **neuro_doc_assistant_errors_total** (Counter)
   - Количество ошибок по типам
   - Labels: `error_type` (api_error, timeout_error, validation_error, retrieval_error и др.)

6. **neuro_doc_assistant_active_requests** (Gauge)
   - Текущее количество активных запросов

## Где посмотреть метрики сейчас

### 1. Через API endpoint (JSON)

```bash
# Получить метрики в JSON формате
curl http://localhost:8000/admin/metrics

# Получить метрики в формате Prometheus
curl http://localhost:8000/admin/metrics/prometheus
```

### 2. Через Swagger UI

1. Откройте `http://localhost:8000/docs`
2. Найдите endpoint `GET /admin/metrics`
3. Нажмите "Try it out" → "Execute"

### 3. Через Streamlit UI

В Streamlit UI есть секция "Системные метрики", которая показывает:
- Всего запросов
- Средняя latency

## Настройка Prometheus

### Шаг 1: Установка Prometheus

**Windows:**
1. Скачайте Prometheus с https://prometheus.io/download/
2. Распакуйте архив
3. Создайте файл `prometheus.yml` (см. ниже)

**Linux/Mac:**
```bash
# Через Homebrew (Mac)
brew install prometheus

# Или скачайте с официального сайта
```

**Docker:**
```bash
docker pull prom/prometheus
```

### Шаг 2: Конфигурация Prometheus

Создайте файл `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s  # Интервал сбора метрик
  evaluation_interval: 15s  # Интервал оценки правил

scrape_configs:
  - job_name: 'neuro-doc-assistant'
    static_configs:
      # ВАЖНО: Выберите правильный адрес в зависимости от способа запуска:
      #
      # Если Prometheus в Docker, а FastAPI локально:
      # - Используйте host.docker.internal:8000 (рекомендуется)
      # - Или используйте IP адрес вашего хоста
      #
      # Если оба запущены локально (не в Docker):
      # - Используйте localhost:8000 или 127.0.0.1:8000
      #
      # Если оба в Docker (через docker-compose):
      # - Используйте имя сервиса, например: fastapi:8000
      #
      - targets: ['host.docker.internal:8000']  # Для Docker на Windows/Mac
      # Альтернативы (раскомментируйте нужную):
      # - targets: ['172.17.0.1:8000']      # Docker bridge IP (Linux)
      # - targets: ['<YOUR_HOST_IP>:8000']  # IP адрес вашего хоста
      # - targets: ['localhost:8000']        # Если оба локально
    metrics_path: '/admin/metrics/prometheus'
    scrape_interval: 5s  # Собираем метрики каждые 5 секунд
```

**⚠️ Важно для Docker:**
- Если Prometheus запущен в Docker, а FastAPI локально, используйте `host.docker.internal:8000`
- В `docker-compose.monitoring.yml` уже добавлен `extra_hosts` для поддержки `host.docker.internal`
- Если `host.docker.internal` не работает, найдите IP адрес хоста командой `ipconfig` (Windows) или `ip addr` (Linux) и используйте его

### Шаг 3: Запуск Prometheus

**Windows:**
```powershell
# Перейдите в директорию с prometheus.exe
.\prometheus.exe --config.file=prometheus.yml
```

**Linux/Mac:**
```bash
prometheus --config.file=prometheus.yml
```

**Docker:**
```bash
docker run -d \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

### Шаг 4: Проверка Prometheus

1. Откройте `http://localhost:9090`
2. Перейдите в "Status" → "Targets"
3. Убедитесь, что `neuro-doc-assistant` в статусе "UP"

**Если target показывает DOWN с ошибкой "connection refused":**

1. **Проверьте, что FastAPI сервер запущен:**
   ```bash
   # Проверьте, что порт 8000 слушается
   netstat -ano | findstr :8000
   
   # Проверьте доступность API
   curl http://localhost:8000/health
   ```

2. **Если Prometheus в Docker, а FastAPI локально:**
   - Убедитесь, что в `prometheus.yml` используется `host.docker.internal:8000`
   - Если `host.docker.internal` не работает, найдите IP адрес хоста:
     ```powershell
     # Windows
     ipconfig | findstr IPv4
     ```
   - Замените в `prometheus.yml` на IP адрес хоста, например: `192.168.1.152:8000`
   - Перезапустите Prometheus: `docker restart prometheus`

3. **Проверьте логи Prometheus:**
   ```bash
   docker logs prometheus --tail 50
   ```
   Ищите ошибки типа "connection refused" или "no such host"

4. **Проверьте конфигурацию:**
   - Откройте `http://localhost:9090/config` в Prometheus UI
   - Убедитесь, что target указан правильно

5. **Если проблема сохраняется:**
   - Попробуйте использовать IP адрес хоста напрямую вместо `host.docker.internal`
   - Убедитесь, что файрвол не блокирует подключения
   - Проверьте, что FastAPI слушает на `0.0.0.0:8000`, а не только на `127.0.0.1:8000`

### Шаг 5: Просмотр метрик в Prometheus

1. Откройте `http://localhost:9090`
2. Перейдите в "Graph"
3. Введите запрос, например:
   - `neuro_doc_assistant_requests_total` - общее количество запросов
   - `rate(neuro_doc_assistant_requests_total[5m])` - QPS (запросов в секунду)
   - `histogram_quantile(0.95, neuro_doc_assistant_request_latency_seconds_bucket)` - p95 latency

## Настройка Grafana

### Шаг 1: Установка Grafana

**Windows:**
1. Скачайте Grafana с https://grafana.com/grafana/download
2. Установите и запустите

**Linux/Mac:**
```bash
# Через Homebrew (Mac)
brew install grafana

# Или через Docker
docker pull grafana/grafana
```

**Docker:**
```bash
docker pull grafana/grafana
```

### Шаг 2: Запуск Grafana

**Windows:**
- Запустите Grafana из меню "Пуск"

**Linux/Mac:**
```bash
grafana-server
```

**Docker:**
```bash
docker run -d -p 3000:3000 grafana/grafana
```

### Шаг 3: Настройка источника данных

1. Откройте `http://localhost:3000`
2. Войдите (по умолчанию: admin/admin)
3. Перейдите в "Configuration" → "Data Sources"
4. Нажмите "Add data source"
5. Выберите "Prometheus"
6. **Укажите URL в зависимости от способа запуска:**
   - **Если оба запущены через Docker Compose** (в одной сети): `http://prometheus:9090`
   - **Если запущены локально** (не в Docker): `http://localhost:9090` или `http://127.0.0.1:9090`
   - **Если Grafana в Docker, а Prometheus локально** (Windows/Mac): `http://host.docker.internal:9090`
   - **Если Grafana в Docker, а Prometheus локально** (Linux): используйте IP адрес хоста
7. Нажмите "Save & Test"

**⚠️ Важно:** Если вы используете `docker-compose.monitoring.yml`, оба контейнера находятся в одной сети `monitoring`, поэтому используйте имя сервиса: `http://prometheus:9090`

#### Диагностика проблем подключения

Если вы получаете ошибку `connection refused` при настройке источника данных:

1. **Проверьте, как запущены Prometheus и Grafana:**
   ```bash
   # Проверьте запущенные Docker контейнеры
   docker ps | findstr -i "prometheus grafana"
   
   # Или проверьте процессы
   netstat -ano | findstr ":9090 :3000"
   ```

2. **Определите правильный URL:**
   - Если оба контейнера в Docker (через `docker-compose`): используйте `http://prometheus:9090`
   - Если оба запущены локально: используйте `http://127.0.0.1:9090`
   - Если Grafana в Docker, а Prometheus локально: используйте `http://host.docker.internal:9090` (Windows/Mac)

3. **Проверьте доступность Prometheus:**
   ```bash
   # Из командной строки (локально)
   curl http://127.0.0.1:9090/-/healthy
   
   # Из контейнера Grafana (если оба в Docker)
   docker exec grafana wget -qO- http://prometheus:9090/-/healthy
   ```

4. **Проверьте сеть Docker (если используете Docker Compose):**
   ```bash
   # Проверьте, что оба контейнера в одной сети
   docker network ls | findstr monitoring
   # Затем проверьте детали сети (замените имя сети на ваше)
   docker network inspect neuro_doc_assistant_monitoring
   # Или найдите имя сети автоматически
   docker network inspect $(docker network ls -q --filter name=monitoring)
   ```

5. **Если проблема сохраняется:**
   - Убедитесь, что Prometheus запущен и отвечает на `http://localhost:9090`
   - Проверьте логи Grafana: `docker logs grafana`
   - Проверьте логи Prometheus: `docker logs prometheus`

### Шаг 4: Создание дашборда

#### Панель 1: QPS (Queries Per Second)

**Query:**
```promql
rate(neuro_doc_assistant_requests_total[5m])
```

**Visualization:** Graph
**Title:** Queries Per Second

#### Панель 2: End-to-End Latency (p50, p95, p99)

**Queries:**
```promql
# p50
histogram_quantile(0.50, rate(neuro_doc_assistant_request_latency_seconds_bucket[5m]))

# p95
histogram_quantile(0.95, rate(neuro_doc_assistant_request_latency_seconds_bucket[5m]))

# p99
histogram_quantile(0.99, rate(neuro_doc_assistant_request_latency_seconds_bucket[5m]))
```

**Visualization:** Graph
**Title:** Request Latency (p50, p95, p99)

#### Панель 3: Retrieval Latency

**Query:**
```promql
histogram_quantile(0.95, rate(neuro_doc_assistant_retrieval_latency_seconds_bucket[5m]))
```

**Visualization:** Graph
**Title:** Retrieval Latency (p95)

#### Панель 4: Generation Latency

**Query:**
```promql
histogram_quantile(0.95, rate(neuro_doc_assistant_generation_latency_seconds_bucket[5m]))
```

**Visualization:** Graph
**Title:** Generation Latency (p95)

#### Панель 5: Ошибки

**Query:**
```promql
sum(rate(neuro_doc_assistant_errors_total[5m])) by (error_type)
```

**Visualization:** Graph
**Title:** Errors by Type

#### Панель 6: Активные запросы

**Query:**
```promql
neuro_doc_assistant_active_requests
```

**Visualization:** Graph
**Title:** Active Requests

### Шаг 5: Импорт готового дашборда

Создайте файл `grafana_dashboard.json` (см. пример ниже) и импортируйте его:

1. Перейдите в "Dashboards" → "Import"
2. Загрузите JSON файл или вставьте содержимое
3. Выберите источник данных (Prometheus)
4. Нажмите "Import"

## Пример конфигурации Docker Compose

Создайте файл `docker-compose.monitoring.yml`:

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:
```

Запуск:
```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

## Проверка работы

### 1. Проверка метрик в Prometheus

```bash
# Проверка endpoint
curl http://localhost:8000/admin/metrics/prometheus

# Должны быть видны метрики в формате:
# neuro_doc_assistant_requests_total 42
# neuro_doc_assistant_request_latency_seconds_bucket{le="0.1"} 10
# ...
```

### 2. Проверка в Prometheus UI

1. Откройте `http://localhost:9090`
2. Введите запрос: `neuro_doc_assistant_requests_total`
3. Должны увидеть значение метрики

### 3. Проверка в Grafana

1. Откройте `http://localhost:3000`
2. Создайте дашборд с панелями выше
3. Должны увидеть графики метрик

## Troubleshooting

### Проблема: Prometheus не может подключиться к endpoint

**Решение:**
1. Убедитесь, что FastAPI сервер запущен на `http://localhost:8000`
2. Проверьте, что endpoint доступен: `curl http://localhost:8000/admin/metrics/prometheus`
3. Проверьте конфигурацию `prometheus.yml` (правильный URL и путь)

### Проблема: Метрики не отображаются в Grafana

**Решение:**
1. Убедитесь, что Prometheus работает и собирает метрики
2. Проверьте, что источник данных в Grafana указывает на правильный Prometheus URL
3. Проверьте запросы в панелях (используйте правильные имена метрик)

### Проблема: prometheus-client не установлен

**Решение:**
```bash
pip install prometheus-client
```

После установки перезапустите FastAPI сервер.

## Полезные PromQL запросы

### QPS (Queries Per Second)
```promql
rate(neuro_doc_assistant_requests_total[5m])
```

### Средняя latency
```promql
rate(neuro_doc_assistant_request_latency_seconds_sum[5m]) / rate(neuro_doc_assistant_request_latency_seconds_count[5m])
```

### p95 latency
```promql
histogram_quantile(0.95, rate(neuro_doc_assistant_request_latency_seconds_bucket[5m]))
```

### Количество ошибок в минуту
```promql
sum(rate(neuro_doc_assistant_errors_total[1m])) by (error_type)
```

### Процент ошибок
```promql
sum(rate(neuro_doc_assistant_errors_total[5m])) / sum(rate(neuro_doc_assistant_requests_total[5m])) * 100
```

## Следующие шаги

1. ✅ Настроить Prometheus для сбора метрик
2. ✅ Настроить Grafana для визуализации
3. ⏳ Создать алерты в Grafana (например, при latency > 1.3 сек)
4. ⏳ Настроить уведомления (email, Slack и др.)
5. ⏳ Добавить дополнительные метрики (если нужно)

