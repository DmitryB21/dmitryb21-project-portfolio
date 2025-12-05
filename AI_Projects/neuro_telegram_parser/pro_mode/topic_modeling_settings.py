"""
Хранилище настроек для Topic Modeling Pipeline.

Настройки сохраняются в JSON-файл topic_modeling_settings.json в корне проекта,
чтобы их можно было менять через UI без перезапуска приложения.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = PROJECT_ROOT / "topic_modeling_settings.json"


SETTING_SPECS: Dict[str, Dict[str, Any]] = {
    # Группа 1: Модели и ресурсы
    "use_gpu_for_qwen": {"type": "bool", "default": False},
    "qwen_n_threads": {"type": "int", "default": 4, "min": 1, "max": os.cpu_count() or 8},
    "qwen_n_gpu_layers": {"type": "int", "default": 0, "min": 0, "max": 64},
    "frida_device": {"type": "str", "default": "cpu", "choices": ["cpu", "cuda"]},
    "gte_device": {"type": "str", "default": "cpu", "choices": ["cpu", "cuda"]},

    # Группа 2: Кластеризация (BERTopic)
    "hdbscan_min_cluster_size": {"type": "int", "default": 3, "min": 2, "max": 50},
    "nr_topics_auto": {"type": "bool", "default": True},
    "max_topics": {"type": "int", "default": 100, "min": 10, "max": 1000},
    "umap_n_neighbors": {"type": "int", "default": 15, "min": 5, "max": 200},
    "umap_n_components": {"type": "int", "default": 5, "min": 2, "max": 50},

    # Группа 3: Генерация заголовков
    "use_qwen_for_titles": {"type": "bool", "default": True},
    "max_title_length": {"type": "int", "default": 100, "min": 20, "max": 200},
    "title_temperature": {"type": "float", "default": 0.25, "min": 0.05, "max": 1.0},
    "num_sample_texts": {"type": "int", "default": 3, "min": 1, "max": 10},

    # Группа 4: Производительность
    "batch_size_qdrant": {"type": "int", "default": 50, "min": 10, "max": 1000},
    "max_posts_for_clustering": {"type": "int", "default": 50000, "min": 1000, "max": 200000},
    "rerun_interval_hours": {"type": "int", "default": 24, "min": 1, "max": 168},

    # Дополнительные параметры (не выводятся напрямую в UI, но полезны для тонкой настройки)
    "qwen_n_ctx": {"type": "int", "default": 2048, "min": 512, "max": 8192},
    "qwen_n_batch": {"type": "int", "default": 64, "min": 16, "max": 512},
    "qwen_use_mmap": {"type": "bool", "default": True},
    "qwen_use_mlock": {"type": "bool", "default": False},
    "qwen_low_resource_mode": {"type": "bool", "default": True},
}

SETTING_GROUPS: List[Dict[str, Any]] = [
    {
        "id": "models",
        "title": "Модели и ресурсы",
        "description": "Настройки производительности и устройств для FRIDA, GTE и Qwen2.5.",
        "fields": [
            {"key": "use_gpu_for_qwen", "label": "Использовать GPU для Qwen", "type": "bool"},
            {"key": "qwen_n_threads", "label": "Потоки CPU для Qwen", "type": "int"},
            {"key": "qwen_n_gpu_layers", "label": "Слои Qwen на GPU", "type": "int"},
            {"key": "frida_device", "label": "Устройство FRIDA", "type": "select", "options": ["cpu", "cuda"]},
            {"key": "gte_device", "label": "Устройство GTE", "type": "select", "options": ["cpu", "cuda"]}
        ]
    },
    {
        "id": "clustering",
        "title": "Кластеризация (BERTopic)",
        "description": "Тонкая настройка UMAP и HDBSCAN для аналитиков.",
        "fields": [
            {"key": "hdbscan_min_cluster_size", "label": "Минимальный размер кластера", "type": "int"},
            {"key": "nr_topics_auto", "label": "Авто объединение тем", "type": "bool"},
            {"key": "max_topics", "label": "Максимум тем (если авто-режим выключен)", "type": "int"},
            {"key": "umap_n_neighbors", "label": "UMAP n_neighbors", "type": "int"},
            {"key": "umap_n_components", "label": "UMAP n_components", "type": "int"}
        ]
    },
    {
        "id": "titles",
        "title": "Генерация заголовков",
        "description": "Параметры вызова локальной модели Qwen2.5 и постобработки текстов.",
        "fields": [
            {"key": "use_qwen_for_titles", "label": "Использовать Qwen для заголовков", "type": "bool"},
            {"key": "max_title_length", "label": "Максимальная длина заголовка (символы)", "type": "int"},
            {"key": "title_temperature", "label": "Температура Qwen", "type": "float"},
            {"key": "num_sample_texts", "label": "Примеров сообщений в промпте", "type": "int"}
        ]
    },
    {
        "id": "performance",
        "title": "Производительность",
        "description": "Ограничения для безопасного запуска на локальном железе.",
        "fields": [
            {"key": "batch_size_qdrant", "label": "Размер батча для Qdrant", "type": "int"},
            {"key": "max_posts_for_clustering", "label": "Макс. постов для BERTopic", "type": "int"},
            {"key": "rerun_interval_hours", "label": "Интервал автозапуска (часы)", "type": "int"}
        ]
    }
]


def _cast_value(key: str, value: Any) -> Any:
    """Привести значение к типу согласно спецификации."""
    spec = SETTING_SPECS.get(key)
    if not spec:
        return value

    target_type = spec["type"]
    try:
        if target_type == "bool":
            if isinstance(value, bool):
                casted = value
            elif isinstance(value, str):
                casted = value.strip().lower() in {"1", "true", "yes", "on"}
            else:
                casted = bool(value)
        elif target_type == "int":
            casted = int(value)
        elif target_type == "float":
            casted = float(value)
        elif target_type == "str":
            casted = str(value)
        else:
            casted = value
    except (TypeError, ValueError):
        casted = spec.get("default")

    # Ограничения min/max/choices
    if isinstance(casted, (int, float)):
        if "min" in spec and casted < spec["min"]:
            casted = spec["min"]
        if "max" in spec and casted > spec["max"]:
            casted = spec["max"]
    if "choices" in spec and casted not in spec["choices"]:
        casted = spec["default"]

    return casted


def load_topic_modeling_settings() -> Dict[str, Any]:
    """Загрузить настройки (с учётом значений по умолчанию)."""
    settings = {key: spec["default"] for key, spec in SETTING_SPECS.items()}
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                if key in SETTING_SPECS:
                    settings[key] = _cast_value(key, value)
        except Exception:
            # Если файл повреждён, игнорируем и используем умолчания
            pass
    return settings


def save_topic_modeling_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Сохранить настройки в файл и вернуть итоговый словарь."""
    settings = load_topic_modeling_settings()
    changed = False

    for key, value in updates.items():
        if key not in SETTING_SPECS:
            continue
        new_value = _cast_value(key, value)
        if settings.get(key) != new_value:
            settings[key] = new_value
            changed = True

    if changed or not SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            raise RuntimeError(f"Не удалось сохранить настройки topic modeling: {exc}") from exc

    return settings


def get_setting_specs() -> Dict[str, Dict[str, Any]]:
    """Вернуть спецификации настроек (для UI/валидации)."""
    return SETTING_SPECS


def get_setting_groups() -> List[Dict[str, Any]]:
    """Вернуть описание групп настроек для отображения в UI."""
    return SETTING_GROUPS


def get_settings_with_specs() -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """Помощник для API: вернуть значения и их спецификации."""
    settings = load_topic_modeling_settings()
    return settings, SETTING_SPECS


def cast_setting_value(key: str, value: Any) -> Any:
    """Публичный помощник для приведения типов (для использования в других модулях)."""
    return _cast_value(key, value)

