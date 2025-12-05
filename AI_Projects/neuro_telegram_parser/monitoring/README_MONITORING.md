# 📊 Настройка мониторинга для Telegram Parser

Этот документ описывает, как настроить систему мониторинга для отслеживания метрик, описанных в `METRICS.md`.

## 🎯 Быстрый старт

### 1. Добавление мониторинга в docker-compose.yml

```yaml
# Добавьте в docker-compose.yml

services:
  # ... существующие сервисы ...

  # Prometheus
  prometheus:
    image: prom/prometheus:latest
    container_name: telegram_parser_prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./monitoring/alerts.yml:/etc/prometheus/alerts.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
    ports:
      - "9090:9090"
    networks:
      - telegram_parser_network
    restart: unless-stopped

  # Grafana
  grafana:
    image: grafana/grafana:latest
    container_name: telegram_parser_grafana
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    ports:
      - "3000:3000"
    networks:
      - telegram_parser_network
    depends_on:
      - prometheus
    restart: unless-stopped

  # Node Exporter (системные метрики)
  node-exporter:
    image: prom/node-exporter:latest
    container_name: telegram_parser_node_exporter
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    ports:
      - "9100:9100"
    networks:
      - telegram_parser_network
    restart: unless-stopped

  # cAdvisor (метрики Docker)
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: telegram_parser_cadvisor
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    ports:
      - "8080:8080"
    networks:
      - telegram_parser_network
    restart: unless-stopped

  # PostgreSQL Exporter
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    container_name: telegram_parser_postgres_exporter
    environment:
      - DATA_SOURCE_NAME=postgresql://indlab_user:indlab_pass@127.0.0.1:5432/indlab_db?sslmode=disable
    ports:
      - "9187:9187"
    network_mode: host
    restart: unless-stopped

  # Redis Exporter
  redis-exporter:
    image: oliver006/redis_exporter:latest
    container_name: telegram_parser_redis_exporter
    environment:
      - REDIS_ADDR=127.0.0.1:6379
      - REDIS_PASSWORD=indlab_redis_pass
    ports:
      - "9121:9121"
    network_mode: host
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
```

### 2. Добавление метрик в Flask приложение

Установите `prometheus-flask-exporter`:

```bash
pip install prometheus-flask-exporter
```

Добавьте в `app.py`:

```python
from prometheus_flask_exporter import PrometheusMetrics

# После создания app
metrics = PrometheusMetrics(app)

# Метрики по умолчанию:
# - http_request_duration_seconds
# - http_request_total
# - flask_http_request_total

# Кастомные метрики
messages_parsed = metrics.counter(
    'messages_parsed_total',
    'Total number of messages parsed',
    labels={'channel': lambda: request.view_args.get('channel', 'unknown')}
)

tasks_created = metrics.counter(
    'tasks_created_total',
    'Total number of tasks created',
    labels={'task_type': lambda: request.json.get('type', 'unknown')}
)
```

### 3. Добавление метрик для Huey

Создайте файл `monitoring/huey_metrics.py`:

```python
from prometheus_client import Counter, Histogram, Gauge
import time

# Метрики для задач Huey
huey_tasks_total = Counter(
    'huey_tasks_total',
    'Total number of Huey tasks',
    ['task_name', 'status']
)

huey_task_duration = Histogram(
    'huey_task_duration_seconds',
    'Duration of Huey tasks',
    ['task_name']
)

huey_queue_length = Gauge(
    'huey_queue_length',
    'Current length of Huey queue'
)

def track_task(task_name):
    """Декоратор для отслеживания задач Huey"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                huey_tasks_total.labels(task_name=task_name, status='success').inc()
                return result
            except Exception as e:
                huey_tasks_total.labels(task_name=task_name, status='error').inc()
                raise
            finally:
                duration = time.time() - start_time
                huey_task_duration.labels(task_name=task_name).observe(duration)
        return wrapper
    return decorator
```

Используйте в `tasks.py`:

```python
from monitoring.huey_metrics import track_task

@huey.task()
@track_task('parse_channel')
def orchestrate_parsing_from_file(...):
    # ваш код
    pass
```

## 📊 Настройка Grafana

### 1. Создание дашборда

1. Откройте Grafana: http://localhost:3000
2. Логин: `admin`, пароль: `admin`
3. Добавьте Prometheus как источник данных:
   - URL: `http://prometheus:9090`
   - Access: Server (default)

### 2. Примеры запросов для дашборда

#### Общая производительность:
```promql
# RPS
rate(http_requests_total[5m])

# P95 Latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error Rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

#### Использование ресурсов:
```promql
# CPU Usage
100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory Usage
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# Disk Usage
(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100
```

#### База данных:
```promql
# PostgreSQL Cache Hit Ratio
(sum(rate(pg_stat_database_blks_hit[5m])) / sum(rate(pg_stat_database_blks_hit[5m]) + rate(pg_stat_database_blks_read[5m]))) * 100

# Redis Hit Rate
(redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)) * 100
```

#### Очередь задач:
```promql
# Queue Length
huey_queue_length

# Task Success Rate
(rate(huey_tasks_total{status="success"}[5m]) / rate(huey_tasks_total[5m])) * 100
```

## 🔔 Настройка алертов

### Вариант 1: Prometheus Alertmanager

Добавьте в `docker-compose.yml`:

```yaml
  alertmanager:
    image: prom/alertmanager:latest
    container_name: telegram_parser_alertmanager
    volumes:
      - ./monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml
    ports:
      - "9093:9093"
    networks:
      - telegram_parser_network
    restart: unless-stopped
```

Создайте `monitoring/alertmanager.yml`:

```yaml
route:
  receiver: 'default'
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h

receivers:
  - name: 'default'
    email_configs:
      - to: 'admin@example.com'
        from: 'alerts@example.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'alerts@example.com'
        auth_password: 'password'
```

### Вариант 2: Grafana Alerts

Настройте алерты прямо в Grafana:
1. Откройте панель с метрикой
2. Нажмите "Edit"
3. Перейдите в "Alert"
4. Настройте условия и уведомления

## 📝 Логирование

### Настройка структурированного логирования

Добавьте в `app.py`:

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

# Настройка логгера
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
```

## 🚀 Запуск мониторинга

```bash
# Запуск всех сервисов включая мониторинг
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f prometheus grafana
```

## 📍 Доступ к сервисам

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **cAdvisor**: http://localhost:8080
- **Node Exporter**: http://localhost:9100/metrics

## 🔍 Полезные запросы Prometheus

### Топ медленных эндпоинтов:
```promql
topk(10, histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])))
```

### Топ эндпоинтов по количеству запросов:
```promql
topk(10, rate(http_requests_total[5m]))
```

### Топ эндпоинтов по ошибкам:
```promql
topk(10, rate(http_requests_total{status=~"5.."}[5m]))
```

## 📚 Дополнительные ресурсы

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Flask Exporter](https://github.com/rycus86/prometheus_flask_exporter)

