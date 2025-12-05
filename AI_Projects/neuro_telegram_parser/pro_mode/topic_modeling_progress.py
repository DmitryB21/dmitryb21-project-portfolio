"""
Трекер прогресса Topic Modeling Pipeline.

Использует Redis для хранения состояния, чтобы UI мог получать данные
в реальном времени, а пользователь — отменять выполнение.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis

from config_utils import get_config

STEP_DEFINITIONS = [
    {"id": "fetch_posts", "title": "1. Загрузка постов из PostgreSQL", "icon": "📥"},
    {"id": "frida_embeddings", "title": "2. Векторизация для поиска (FRIDA)", "icon": "🧠"},
    {"id": "gte_embeddings", "title": "3. Векторизация для кластеризации (GTE)", "icon": "🧬"},
    {"id": "qdrant_indexing", "title": "4. Индексация в Qdrant", "icon": "🗄️"},
    {"id": "bertopic", "title": "5. Запуск BERTopic (UMAP → HDBSCAN)", "icon": "🧩"},
    {"id": "title_generation", "title": "6. Генерация заголовков (Qwen2.5)", "icon": "✍️"},
    {"id": "save_to_db", "title": "7. Сохранение в PostgreSQL", "icon": "💾"},
]

CURRENT_KEY = "topic_modeling:progress:current"
STATE_TTL_SECONDS = 60 * 60 * 48  # 48 часов
MAX_LOG_ENTRIES = 200


def _get_redis_client() -> redis.Redis:
    config = get_config()
    return redis.Redis(
        host=config['redis']['host'],
        port=int(config['redis']['port']),
        decode_responses=True
    )


class TopicModelingProgressTracker:
    """Менеджер состояния для одного запуска пайплайна."""

    def __init__(self, task_id: Optional[str] = None):
        self.task_id = task_id or f"manual-{int(time.time())}"
        self._redis = _get_redis_client()
        self._key = f"topic_modeling:progress:{self.task_id}"
        self._state: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------ helpers
    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    def _ensure_state(self):
        if self._state is None:
            raw = self._redis.get(self._key)
            if raw:
                self._state = json.loads(raw)

    def _save_state(self):
        if self._state is None:
            return
        self._state["updated_at"] = self._now()
        payload = json.dumps(self._state, ensure_ascii=False)
        self._redis.set(self._key, payload, ex=STATE_TTL_SECONDS)
        self._redis.set(CURRENT_KEY, payload, ex=STATE_TTL_SECONDS)

    def _update_step_status(self, step_id: str, status: str, details: Optional[Dict[str, Any]] = None):
        if not self._state:
            return
        for step in self._state["steps"]:
            if step["id"] == step_id:
                step["status"] = status
                if details:
                    # Обновляем детали, сохраняя предыдущие значения
                    step_details = step.get("details", {}) or {}
                    step_details.update(details)
                    step["details"] = step_details
                break
        done_steps = sum(1 for step in self._state["steps"] if step["status"] == "done")
        total_steps = len(self._state["steps"])
        self._state["progress"] = round((done_steps / total_steps) * 100, 1) if total_steps else 0.0

    # --------------------------------------------------------------------- API
    def start(self, settings: Optional[Dict[str, Any]] = None):
        self._state = {
            "task_id": self.task_id,
            "status": "running",
            "started_at": self._now(),
            "updated_at": self._now(),
            "settings": settings or {},
            "control": {"cancel_requested": False},
            "steps": [
                {
                    "id": step["id"],
                    "title": step["title"],
                    "icon": step["icon"],
                    "status": "pending",
                    "details": {}
                }
                for step in STEP_DEFINITIONS
            ],
            "progress": 0.0,
            "logs": [],
            "metrics": {},
            "result": None,
            "error": None
        }
        self._save_state()

    def update_step(self, step_id: str, status: str, details: Optional[Dict[str, Any]] = None):
        self._ensure_state()
        if not self._state:
            return
        self._update_step_status(step_id, status, details)
        self._save_state()

    def log(self, message: str, level: str = "info"):
        self._ensure_state()
        if not self._state:
            return
        log_entry = {
            "ts": self._now(),
            "level": level,
            "message": message
        }
        logs: List[Dict[str, Any]] = self._state.get("logs", [])
        logs.append(log_entry)
        if len(logs) > MAX_LOG_ENTRIES:
            logs = logs[-MAX_LOG_ENTRIES:]
        self._state["logs"] = logs
        self._save_state()

    def update_metrics(self, metrics: Dict[str, Any]):
        self._ensure_state()
        if not self._state:
            return
        merged = self._state.get("metrics", {})
        merged.update(metrics)
        self._state["metrics"] = merged
        self._save_state()

    def finish(self, status: str, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        self._ensure_state()
        if not self._state:
            return
        self._state["status"] = status
        self._state["finished_at"] = self._now()
        if result is not None:
            self._state["result"] = result
        if error:
            self._state["error"] = error
        self._save_state()

    def is_cancel_requested(self) -> bool:
        raw = self._redis.get(self._key)
        if not raw:
            return False
        state = json.loads(raw)
        control = state.get("control") or {}
        return control.get("cancel_requested", False)

    def mark_cancelled(self):
        self._ensure_state()
        if not self._state:
            return
        self._state.setdefault("control", {})["cancel_requested"] = True
        self._save_state()


# ---------------------------------------------------------------------------
# Helper functions for API
# ---------------------------------------------------------------------------
def get_current_progress() -> Optional[Dict[str, Any]]:
    client = _get_redis_client()
    raw = client.get(CURRENT_KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def request_cancel(task_id: Optional[str] = None) -> bool:
    client = _get_redis_client()
    key = CURRENT_KEY
    if task_id:
        candidate_key = f"topic_modeling:progress:{task_id}"
        if client.exists(candidate_key):
            key = candidate_key
    raw = client.get(key)
    if not raw:
        return False
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        return False
    state.setdefault("control", {})["cancel_requested"] = True
    payload = json.dumps(state, ensure_ascii=False)
    client.set(key, payload, ex=STATE_TTL_SECONDS)
    if key != CURRENT_KEY:
        client.set(CURRENT_KEY, payload, ex=STATE_TTL_SECONDS)
    return True

