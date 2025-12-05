"""
Модуль для тематического моделирования с использованием BERTopic, FRIDA, GTE и OpenAI GPT

Этот модуль реализует современный пайплайн тематического моделирования:
- FRIDA (ai-forever/FRIDA) для поиска и классификации
- gte-multilingual-base для кластеризации
- BERTopic для тематического моделирования
- OpenAI GPT API для генерации заголовков тем (с fallback на ключевые слова)

Архитектура:
- Два индекса Qdrant: posts_search (FRIDA) и posts_clustering (GTE)
- Результаты сохраняются в PostgreSQL (dedup_clusters, cluster_messages)
- Асинхронная обработка с поддержкой батчей
"""

import asyncio
import logging
import os
import re
import time
import gc
import sys
import types
from collections import Counter
from dataclasses import dataclass, fields, asdict
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple
import json
import uuid
from pathlib import Path

# Устанавливаем заглушку для llama_cpp ДО импорта bertopic
# (bertopic пытается импортировать llama_cpp при загрузке, но мы его не используем)
if 'llama_cpp' not in sys.modules:
    try:
        import llama_cpp
    except (ImportError, RuntimeError, FileNotFoundError, OSError):
        # Создаем минимальную заглушку для llama_cpp
        llama_cpp_stub = types.ModuleType('llama_cpp')
        llama_cpp_stub.Llama = None
        sys.modules['llama_cpp'] = llama_cpp_stub

# Асинхронные библиотеки
import asyncpg
import numpy as np

# Векторная БД
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, 
    Filter, FieldCondition, MatchValue
)

# ML библиотеки
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

# Безопасный импорт BERTopic (заглушка для llama_cpp уже установлена выше)
try:
    from bertopic import BERTopic
    BERTOPIC_AVAILABLE = True
except (ImportError, RuntimeError, FileNotFoundError) as e:
    BERTOPIC_AVAILABLE = False
    BERTopic = None
    # logger может быть еще не инициализирован, используем print
    print(f"⚠️ BERTopic недоступен: {e}")

try:
    from umap import UMAP
    UMAP_AVAILABLE = True
except ImportError:
    UMAP_AVAILABLE = False
    UMAP = None

try:
    from hdbscan import HDBSCAN
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False
    HDBSCAN = None

# OpenAI для генерации заголовков (импортируется в openai_generator)

try:
    import psutil
except ImportError:
    psutil = None

# Конфигурация
from config_utils import get_config
from pro_mode.topic_modeling_progress import TopicModelingProgressTracker
from pro_mode.topic_modeling_settings import (
    load_topic_modeling_settings,
    cast_setting_value,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = PROJECT_ROOT / "topic_modeling.log"
TOPIC_REPORT_DIR = PROJECT_ROOT / "artifacts" / "topic_modeling"
TOPIC_REPORT_FILE = TOPIC_REPORT_DIR / "topic_modeling.json"

logger = logging.getLogger(__name__)


def _ensure_topic_modeling_file_handler() -> None:
    """Attach a dedicated file handler so the pipeline always logs to topic_modeling.log."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler_exists = any(
        isinstance(handler, logging.FileHandler)
        and getattr(handler, "baseFilename", "") == str(LOG_FILE)
        for handler in logger.handlers
    )
    if handler_exists:
        return

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)


_ensure_topic_modeling_file_handler()


class TopicModelingCancelled(Exception):
    """Исключение для корректной отмены пайплайна."""
    pass


# ============================================================================
# ШАГ 2: РЕАЛИЗАЦИЯ EMBEDDER'ОВ
# ============================================================================

class FRIDAEmbedder:
    """
    Embedder на основе модели FRIDA (ai-forever/FRIDA)
    
    Поддерживает режимы:
    - search_document: для индексации документов
    - search_query: для поисковых запросов
    - categorize_topic: для классификации тем
    
    При использовании режима добавляет префикс "{mode}: {text}"
    """
    
    def __init__(self, model_name: str = "ai-forever/FRIDA", device: str = "cpu"):
        """
        Инициализация FRIDA embedder
        
        Args:
            model_name: Имя модели в HuggingFace
            device: Устройство для вычислений ("cpu" или "cuda")
        """
        self.model_name = model_name
        self.device = device
        self._model: Optional[SentenceTransformer] = None
        self._dimension: Optional[int] = None
        self._cache: Dict[str, List[float]] = {}  # Простой кэш эмбеддингов
    
    def _load_model(self):
        """Ленивая загрузка модели"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers не установлен. "
                "Установите: pip install sentence-transformers"
            )
        
        if self._model is None:
            logger.info(f"Загрузка модели FRIDA: {self.model_name} на устройстве: {self.device}")
            # Принудительная сборка мусора перед загрузкой для освобождения памяти
            gc.collect()
            
            # Очистка GPU памяти, если используем CUDA
            if self.device == "cuda":
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        logger.info("   🧹 GPU кэш очищен перед загрузкой FRIDA")
                except Exception as e:
                    logger.warning(f"   ⚠️ Не удалось очистить GPU кэш: {e}")
            
            try:
                # Пытаемся загрузить с оптимизацией памяти через model_kwargs
                self._model = SentenceTransformer(
                    self.model_name, 
                    device=self.device,
                    model_kwargs={"low_cpu_mem_usage": True} if hasattr(SentenceTransformer, 'model_kwargs') else {}
                )
            except (TypeError, AttributeError):
                # Если model_kwargs не поддерживается, загружаем стандартным способом
                self._model = SentenceTransformer(self.model_name, device=self.device)
            except RuntimeError as e:
                # Если ошибка памяти на GPU, пробуем загрузить на CPU
                if "out of memory" in str(e).lower() or "cuda" in str(e).lower():
                    logger.warning(f"   ⚠️ Недостаточно GPU памяти для FRIDA, переключаемся на CPU: {e}")
                    if self.device == "cuda":
                        try:
                            import torch
                            if torch.cuda.is_available():
                                torch.cuda.empty_cache()
                        except Exception:
                            pass
                        self.device = "cpu"
                        self._model = SentenceTransformer(self.model_name, device="cpu")
                        logger.info("   ✅ FRIDA загружена на CPU (fallback из-за нехватки GPU памяти)")
                    else:
                        raise
                else:
                    raise
            # Получаем размерность из модели
            test_embedding = self._model.encode(["test"], show_progress_bar=False)
            self._dimension = len(test_embedding[0])
            logger.info(f"✅ FRIDA модель загружена, размерность: {self._dimension}")
            # Сборка мусора после загрузки
            gc.collect()
    
    def encode(self, texts: List[str], mode: Optional[str] = None) -> List[List[float]]:
        """
        Кодирование текстов в эмбеддинги
        
        Args:
            texts: Список текстов для кодирования
            mode: Режим работы ("search_document", "search_query", "categorize_topic")
                 Если указан, добавляется префикс "{mode}: {text}"
        
        Returns:
            Список эмбеддингов (каждый - список float)
        """
        if not texts:
            return []
        
        self._load_model()
        
        # Формируем тексты с префиксами, если режим указан
        if mode:
            prefixed_texts = [f"{mode}: {text}" for text in texts]
        else:
            prefixed_texts = texts
        
        # Проверяем кэш (только для одиночных текстов без режима)
        if len(texts) == 1 and not mode:
            cache_key = texts[0]
            if cache_key in self._cache:
                return [self._cache[cache_key]]
        
        # Кодируем с оптимизацией батчинга
        # Для CPU используем меньший batch_size для стабильности
        # Для GPU можно использовать больший batch_size
        
        # Вычисляем среднюю длину текстов для динамической настройки batch_size
        total_chars = sum(len(text) for text in prefixed_texts)
        avg_text_length = total_chars / len(prefixed_texts) if prefixed_texts else 0
        
        # Динамически уменьшаем batch_size для длинных текстов
        if self.device == "cpu":
            # Для CPU: уменьшаем batch_size для длинных текстов
            if avg_text_length > 2000:  # Очень длинные тексты
                batch_size = 4
            elif avg_text_length > 1000:  # Длинные тексты
                batch_size = 8
            else:  # Короткие тексты
                batch_size = 16
        else:
            # Для GPU: можно использовать больший batch_size
            batch_size = 32 if avg_text_length < 1000 else 16
        
        # Логируем параметры для отладки
        logger.info(f"   📊 Параметры encode: {len(prefixed_texts)} текстов, batch_size={batch_size}, avg_length={avg_text_length:.0f} символов, total_chars={total_chars}")
        
        encode_start = time.perf_counter()
        embeddings = self._model.encode(
            prefixed_texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True  # Нормализация для косинусного расстояния
        )
        encode_duration = time.perf_counter() - encode_start
        logger.debug(f"   ⏱️ encode() завершен за {encode_duration:.1f}с ({len(prefixed_texts)/encode_duration:.2f} текстов/сек)")
        
        # Сохраняем в кэш (только для одиночных текстов без режима)
        if len(texts) == 1 and not mode:
            self._cache[texts[0]] = embeddings[0].tolist()
        
        return embeddings.tolist()
    
    def get_dimension(self) -> int:
        """Получить размерность эмбеддингов"""
        if self._dimension is None:
            self._load_model()
        return self._dimension


class GTEEmbedder:
    """
    Embedder на основе модели gte-multilingual-base (Alibaba-NLP/gte-multilingual-base)
    
    Используется для кластеризации. ВАЖНО: без префиксов!
    Только чистые эмбеддинги текстов.
    """
    
    def __init__(self, model_name: str = "Alibaba-NLP/gte-multilingual-base", device: str = "cpu"):
        """
        Инициализация GTE embedder
        
        Args:
            model_name: Имя модели в HuggingFace
            device: Устройство для вычислений ("cpu" или "cuda")
        """
        self.model_name = model_name
        self.device = device
        self._model: Optional[SentenceTransformer] = None
        self._dimension: Optional[int] = None
        self._cache: Dict[str, List[float]] = {}  # Простой кэш эмбеддингов
    
    def _load_model(self):
        """Ленивая загрузка модели"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers не установлен. "
                "Установите: pip install sentence-transformers"
            )
        
        if self._model is None:
            logger.info(f"Загрузка модели GTE: {self.model_name}")
            # GTE модель требует trust_remote_code=True
            # Используем transformers напрямую
            try:
                from transformers import AutoModel, AutoTokenizer
                import torch
                
                logger.info("Загрузка GTE через transformers с trust_remote_code=True...")
                tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
                model = AutoModel.from_pretrained(self.model_name, trust_remote_code=True)
                model.eval()
                if self.device == "cuda" and torch.cuda.is_available():
                    model = model.cuda()
                    device_torch = "cuda"
                else:
                    device_torch = "cpu"
                
                # Создаем обертку для совместимости с SentenceTransformer API
                class GTEWrapper:
                    def __init__(self, model, tokenizer, device_torch):
                        self.model = model
                        self.tokenizer = tokenizer
                        self.device_torch = device_torch
                    
                    def encode(self, texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True, **kwargs):
                        """Кодирование текстов в эмбеддинги"""
                        if isinstance(texts, str):
                            texts = [texts]
                        
                        # Токенизация
                        inputs = self.tokenizer(
                            texts,
                            padding=True,
                            truncation=True,
                            max_length=512,
                            return_tensors="pt"
                        )
                        if self.device_torch == "cuda":
                            inputs = {k: v.cuda() for k, v in inputs.items()}
                        
                        # Получаем эмбеддинги
                        with torch.no_grad():
                            outputs = self.model(**inputs)
                            # Используем mean pooling
                            embeddings = outputs.last_hidden_state
                            attention_mask = inputs['attention_mask']
                            embeddings = (embeddings * attention_mask.unsqueeze(-1)).sum(1) / attention_mask.sum(1, keepdim=True).clamp(min=1e-9)
                            
                            # Нормализация
                            if normalize_embeddings:
                                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                        
                        # Конвертируем в numpy
                        if convert_to_numpy:
                            embeddings = embeddings.cpu().numpy()
                        
                        return embeddings
                
                self._model = GTEWrapper(model, tokenizer, device_torch)
                
            except Exception as e:
                logger.error(f"Ошибка загрузки GTE модели: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # Получаем размерность из модели
            test_embedding = self._model.encode(["test"], show_progress_bar=False)
            if isinstance(test_embedding, list):
                self._dimension = len(test_embedding[0])
            else:
                self._dimension = test_embedding.shape[1] if len(test_embedding.shape) > 1 else len(test_embedding[0])
            logger.info(f"✅ GTE модель загружена, размерность: {self._dimension}")
    
    def encode(self, texts: List[str], mode: Optional[str] = None) -> List[List[float]]:
        """
        Кодирование текстов в эмбеддинги
        
        Args:
            texts: Список текстов для кодирования
            mode: Игнорируется (для совместимости с интерфейсом)
                 GTE не использует префиксы!
        
        Returns:
            Список эмбеддингов (каждый - список float)
        """
        if not texts:
            return []
        
        self._load_model()
        
        # ВАЖНО: GTE не использует префиксы, только чистые тексты
        # Параметр mode игнорируется
        
        # Проверяем кэш
        if len(texts) == 1:
            cache_key = texts[0]
            if cache_key in self._cache:
                return [self._cache[cache_key]]
        
        # Кодируем без префиксов
        # Проверяем, является ли модель оберткой GTEWrapper
        if hasattr(self._model, 'encode'):
            embeddings = self._model.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True  # Нормализация для косинусного расстояния
            )
        else:
            # Fallback для обычного SentenceTransformer
            embeddings = self._model.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
        
        # Сохраняем в кэш
        if len(texts) == 1:
            self._cache[texts[0]] = embeddings[0].tolist()
        
        return embeddings.tolist()
    
    def get_dimension(self) -> int:
        """Получить размерность эмбеддингов"""
        if self._dimension is None:
            self._load_model()
        return self._dimension


# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

@dataclass
class TopicModelingConfig:
    """Конфигурация для TopicModelingService"""
    
    # Модели
    frida_model_name: str = "ai-forever/FRIDA"
    gte_model_name: str = "Alibaba-NLP/gte-multilingual-base"
    frida_device: str = "cpu"
    gte_device: str = "cpu"
    
    # Qdrant
    qdrant_host: str = "127.0.0.1"
    qdrant_port: int = 6333
    search_collection: str = "posts_search"
    clustering_collection: str = "posts_clustering"
    
    # Размерности эмбеддингов (будут определены автоматически при загрузке моделей)
    frida_dimension: int = 1536  # FRIDA (определяется автоматически)
    gte_dimension: int = 768  # gte-multilingual-base (определяется автоматически)
    
    # BERTopic параметры
    umap_n_neighbors: int = 15
    umap_n_components: int = 5
    umap_min_dist: float = 0.0
    hdbscan_min_cluster_size: int = 3
    hdbscan_min_samples: int = 1
    nr_topics: str = "auto"  # Автоматическое объединение тем (legacy)
    nr_topics_auto: bool = True
    max_topics: int = 100
    
    # OpenAI параметры для генерации заголовков
    use_openai_for_titles: bool = True  # Использовать OpenAI GPT для генерации заголовков
    openai_model: str = "gpt-3.5-turbo"  # Модель OpenAI (gpt-3.5-turbo, gpt-4, etc.)
    openai_temperature: float = 0.3  # Температура генерации
    openai_max_tokens: int = 50  # Максимальное количество токенов
    openai_timeout: float = 30.0  # Таймаут запроса в секундах
    max_title_length: int = 100
    num_sample_texts: int = 3
    
    # Обработка
    batch_size_qdrant: int = 50
    max_posts_for_clustering: int = 50_000
    rerun_interval_hours: int = 24
    
    @classmethod
    def from_config_file(cls) -> "TopicModelingConfig":
        """Создать конфигурацию из config.ini"""
        config = get_config()
        
        # Читаем настройки Qdrant
        qdrant_host = "127.0.0.1"
        qdrant_port = 6333
        if 'qdrant' in config:
            qdrant_host = config['qdrant'].get('host', qdrant_host)
            qdrant_port = int(config['qdrant'].get('port', qdrant_port))
        
        # Читаем настройки моделей (если есть секция topic_modeling)
        frida_model = "ai-forever/FRIDA"
        gte_model = "Alibaba-NLP/gte-multilingual-base"
        qwen_path = ""
        
        topic_section = config['topic_modeling'] if 'topic_modeling' in config else {}

        def get_int(key: str, default: int) -> int:
            try:
                return int(topic_section.get(key, default))
            except (TypeError, ValueError):
                return default

        def get_float(key: str, default: float) -> float:
            try:
                return float(topic_section.get(key, default))
            except (TypeError, ValueError):
                return default

        def get_bool(key: str, default: bool) -> bool:
            value = topic_section.get(key)
            if value is None:
                return default
            value = value.strip().lower()
            if value in {"1", "true", "yes", "on"}:
                return True
            if value in {"0", "false", "no", "off"}:
                return False
            return default

        if topic_section:
            frida_model = topic_section.get('frida_model', frida_model)
            gte_model = topic_section.get('gte_model', gte_model)
        
        kwargs = {
            "frida_model_name": frida_model,
            "gte_model_name": gte_model,
            "qdrant_host": qdrant_host,
            "qdrant_port": qdrant_port,
            "frida_device": topic_section.get('frida_device', cls.frida_device),
            "gte_device": topic_section.get('gte_device', cls.gte_device),
            "batch_size_qdrant": get_int('batch_size_qdrant', cls.batch_size_qdrant),
            "max_posts_for_clustering": get_int('max_posts_for_clustering', cls.max_posts_for_clustering),
            "rerun_interval_hours": get_int('rerun_interval_hours', cls.rerun_interval_hours),
            "use_openai_for_titles": get_bool('use_openai_for_titles', cls.use_openai_for_titles),
            "openai_model": topic_section.get('openai_model', cls.openai_model),
            "openai_temperature": get_float('openai_temperature', cls.openai_temperature),
            "openai_max_tokens": get_int('openai_max_tokens', cls.openai_max_tokens),
            "openai_timeout": get_float('openai_timeout', cls.openai_timeout),
            "max_title_length": get_int('max_title_length', cls.max_title_length),
            "num_sample_texts": get_int('num_sample_texts', cls.num_sample_texts),
            "umap_n_neighbors": get_int('umap_n_neighbors', cls.umap_n_neighbors),
            "umap_n_components": get_int('umap_n_components', cls.umap_n_components),
            "umap_min_dist": get_float('umap_min_dist', cls.umap_min_dist),
            "hdbscan_min_cluster_size": get_int('hdbscan_min_cluster_size', cls.hdbscan_min_cluster_size),
            "hdbscan_min_samples": get_int('hdbscan_min_samples', cls.hdbscan_min_samples),
            "nr_topics_auto": get_bool('nr_topics_auto', cls.nr_topics_auto),
            "max_topics": get_int('max_topics', cls.max_topics),
        }

        cfg = cls(**kwargs)
        cfg.nr_topics = "auto" if cfg.nr_topics_auto else cfg.max_topics

        # Переопределяем настройками из UI (JSON)
        overrides = load_topic_modeling_settings()
        for key, value in overrides.items():
            if hasattr(cfg, key):
                cfg_value = cast_setting_value(key, value)
                setattr(cfg, key, cfg_value)

        cfg.nr_topics = "auto" if cfg.nr_topics_auto else cfg.max_topics
        return cfg


class TopicModelingService:
    """
    Сервис для тематического моделирования с использованием BERTopic
    
    Основные возможности:
    - Индексация постов в два индекса Qdrant (search и clustering)
    - Построение тематической модели через BERTopic
    - Генерация заголовков тем через Qwen2.5
    - Сохранение результатов в PostgreSQL
    """
    
    def __init__(
        self,
        config: Optional[TopicModelingConfig] = None,
        progress_tracker: Optional[TopicModelingProgressTracker] = None
    ):
        """
        Инициализация сервиса
        
        Args:
            config: Конфигурация сервиса. Если None, загружается из config.ini
            progress_tracker: Трекер прогресса для интеграции с UI
        """
        self.config = config or TopicModelingConfig.from_config_file()
        self.progress_tracker = progress_tracker
        
        # Ленивая загрузка моделей (при первом использовании)
        self._frida_embedder: Optional['FRIDAEmbedder'] = None
        self._gte_embedder: Optional['GTEEmbedder'] = None
        self._openai_generator: Optional['OpenAITitleGenerator'] = None
        self._bertopic: Optional[BERTopic] = None
        
        # Служебные структуры
        self._timings: Dict[str, float] = {}
        self._resource_usage: Dict[str, float] = {"peak_ram_gb": 0.0}
        self._title_stats: Dict[str, Any] = {"count": 0, "durations": []}
        self._metrics_snapshot: Dict[str, Any] = {}
        
        # Qdrant клиент
        self.qdrant_client = QdrantClient(
            host=self.config.qdrant_host,
            port=self.config.qdrant_port,
            timeout=60.0
        )
        
        # PostgreSQL DSN (будет загружен при первом использовании)
        self._pg_dsn: Optional[str] = None
        
        # Временные данные для сохранения результатов
        self._last_post_ids: Optional[List[int]] = None
        self._last_topics: Optional[List[int]] = None
        self._last_probs: Optional[List[float]] = None
        self._last_texts: Optional[List[str]] = None
        
        logger.info("✅ TopicModelingService инициализирован")
        logger.info(f"   Qdrant: {self.config.qdrant_host}:{self.config.qdrant_port}")
        logger.info(f"   Коллекции: {self.config.search_collection}, {self.config.clustering_collection}")

    # ------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------

    def _progress_start(self, settings: Optional[Dict[str, Any]] = None):
        if self.progress_tracker:
            self.progress_tracker.start(settings or {})

    def _progress_step(self, step_id: str, status: str, details: Optional[Dict[str, Any]] = None):
        if self.progress_tracker:
            self.progress_tracker.update_step(step_id, status, details)

    def _progress_log(self, message: str, level: str = "info"):
        log_fn = getattr(logger, level, logger.info)
        log_fn(message)
        if self.progress_tracker:
            self.progress_tracker.log(message, level)

    def _progress_metrics(self, metrics: Dict[str, Any]):
        self._metrics_snapshot.update(metrics)
        if self.progress_tracker:
            self.progress_tracker.update_metrics(metrics)

    def _check_cancellation(self):
        if self.progress_tracker and self.progress_tracker.is_cancel_requested():
            raise TopicModelingCancelled("Пользователь отменил выполнение пайплайна")

    def _update_resource_usage(self):
        if not psutil:
            return
        process = psutil.Process(os.getpid())
        rss_gb = process.memory_info().rss / (1024 ** 3)
        peak = self._resource_usage.get("peak_ram_gb", 0.0)
        if rss_gb > peak:
            self._resource_usage["peak_ram_gb"] = round(rss_gb, 2)

    def _record_timing(self, key: str, duration: float):
        self._timings[key] = duration

    def _record_title_duration(self, duration: float):
        self._title_stats.setdefault("durations", []).append(duration)
        self._title_stats["count"] = len(self._title_stats["durations"])

    @staticmethod
    def _json_default(value: Any):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, (np.generic,)):
            return value.item()
        if isinstance(value, set):
            return list(value)
        raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")

    def _summarize_loaded_posts(self, posts: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        if not posts:
            return {"total": 0, "examples": []}
        timestamps = [
            p.get("timestamp") for p in posts
            if isinstance(p.get("timestamp"), datetime)
        ]
        examples = []
        for post in posts[:5]:
            examples.append({
                "post_id": post.get("post_id"),
                "timestamp": post.get("timestamp").isoformat() if isinstance(post.get("timestamp"), datetime) else None,
                "text_preview": (post.get("text") or "")[:280]
            })
        summary = {
            "total": len(posts),
            "examples": examples
        }
        if timestamps:
            summary["time_range"] = {
                "start": min(timestamps).isoformat(),
                "end": max(timestamps).isoformat()
            }
        return summary

    def _prepare_documents_distribution(self) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]], List[Dict[str, Any]]]:
        if not self._last_post_ids or not self._last_topics:
            return [], {}, []
        documents: List[Dict[str, Any]] = []
        distribution: Dict[int, Dict[str, Any]] = {}
        noise_docs: List[Dict[str, Any]] = []
        probs_available = self._last_probs is not None and len(self._last_probs) == len(self._last_post_ids)
        texts_available = self._last_texts is not None and len(self._last_texts) == len(self._last_post_ids)

        for idx, post_id in enumerate(self._last_post_ids):
            raw_topic = self._last_topics[idx]
            topic_id = int(raw_topic) if raw_topic is not None else None
            semantic_score: Optional[float] = None
            if probs_available and self._last_probs[idx] is not None:
                prob_row = self._last_probs[idx]
                try:
                    max_prob = float(np.max(prob_row))
                except Exception:
                    max_prob = None
                semantic_score = round(max_prob, 4) if isinstance(max_prob, (int, float)) else None
            text_preview = ""
            if texts_available:
                text_preview = (self._last_texts[idx] or "")[:500]
            doc_entry = {
                "post_id": int(post_id) if post_id is not None else None,
                "topic_id": topic_id,
                "semantic_score": semantic_score,
                "text_preview": text_preview
            }
            documents.append(doc_entry)

            bucket = distribution.setdefault(topic_id, {"count": 0, "scores": []})
            bucket["count"] += 1
            if semantic_score is not None:
                bucket["scores"].append(semantic_score)

            if topic_id == -1:
                noise_docs.append(doc_entry)

        for topic_id, bucket in distribution.items():
            scores = bucket.pop("scores")
            bucket["avg_semantic_score"] = round(mean(scores), 4) if scores else None

        return documents, distribution, noise_docs

    async def _get_classification_data(self) -> Optional[Dict[str, Any]]:
        """Получить данные классификации из БД"""
        try:
            dsn = self._get_pg_dsn()
            conn = await asyncpg.connect(dsn=dsn)
            
            try:
                # Получаем все темы с их описаниями
                topics_rows = await conn.fetch("""
                    SELECT id, name, description, color
                    FROM topics
                    ORDER BY name
                """)
                
                # Получаем классификации сообщений с информацией о сообщениях
                classifications_rows = await conn.fetch("""
                    SELECT 
                        mt.topic_id,
                        mt.message_id,
                        mt.confidence_score,
                        m.text_content,
                        m.published_at,
                        m.channel_id,
                        c.name as channel_name,
                        c.username as channel_username
                    FROM message_topics mt
                    JOIN messages m ON mt.message_id = m.id
                    LEFT JOIN channels c ON m.channel_id = c.id
                    ORDER BY mt.topic_id, mt.confidence_score DESC
                """)
                
                # Группируем по темам
                topics_dict = {row['id']: {
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'],
                    'color': row['color']
                } for row in topics_rows}
                
                messages_by_topic: Dict[int, List[Dict[str, Any]]] = {}
                for row in classifications_rows:
                    topic_id = row['topic_id']
                    if topic_id not in messages_by_topic:
                        messages_by_topic[topic_id] = []
                    
                    # Обрезаем текст для отчета
                    text_content = row['text_content'] or ''
                    text_preview = text_content[:200] + '...' if len(text_content) > 200 else text_content
                    
                    messages_by_topic[topic_id].append({
                        'message_id': row['message_id'],
                        'confidence_score': round(float(row['confidence_score']), 4) if row['confidence_score'] else None,
                        'text_preview': text_preview,
                        'published_at': row['published_at'].isoformat() if row['published_at'] else None,
                        'channel_id': row['channel_id'],
                        'channel_name': row['channel_name'],
                        'channel_username': row['channel_username']
                    })
                
                # Формируем результат
                classification_topics = []
                for topic_id, topic_info in topics_dict.items():
                    messages = messages_by_topic.get(topic_id, [])
                    if messages:  # Добавляем только темы с сообщениями
                        classification_topics.append({
                            'topic_id': topic_id,
                            'name': topic_info['name'],
                            'description': topic_info['description'],
                            'color': topic_info['color'],
                            'messages_count': len(messages),
                            'avg_confidence': round(
                                sum(m['confidence_score'] or 0 for m in messages) / len(messages), 
                                4
                            ) if messages else None,
                            'messages': messages
                        })
                
                return {
                    'topics_count': len(classification_topics),
                    'total_messages': sum(len(messages_by_topic.get(tid, [])) for tid in topics_dict.keys()),
                    'topics': classification_topics
                }
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения данных классификации: {e}")
            return None

    def _build_topic_modeling_report(
        self,
        *,
        new_posts: Optional[List[Dict[str, Any]]],
        topic_info: Dict[str, Any],
        save_stats: Dict[str, Any],
        metrics: Dict[str, Any],
        posts_indexed: int,
        fetch_mode: str,
        classification_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        config_snapshot = asdict(self.config)

        def _cast_topic_id(value: Any) -> Any:
            try:
                return int(value)
            except (TypeError, ValueError):
                return value

        documents, distribution, noise_docs = self._prepare_documents_distribution()
        documents_by_topic: Dict[int, List[Dict[str, Any]]] = {}
        for doc in documents:
            documents_by_topic.setdefault(doc["topic_id"], []).append(doc)

        cluster_cards = save_stats.get("cluster_cards", [])
        topic_keywords = topic_info.get("topic_keywords", {})
        clusters_detail = []
        for card in cluster_cards:
            topic_id = _cast_topic_id(card.get("topic_id"))
            cluster_docs = documents_by_topic.get(topic_id, [])
            scores = [doc["semantic_score"] for doc in cluster_docs if doc["semantic_score"] is not None]
            clusters_detail.append({
                "topic_id": topic_id,
                "title": card["title"],
                "keywords": topic_keywords.get(topic_id, card.get("keywords", [])),
                "size": len(cluster_docs),
                "avg_semantic_score": round(mean(scores), 4) if scores else None,
                "messages": cluster_docs
            })

        min_cluster_size = self.config.hdbscan_min_cluster_size
        skipped_topics = []
        for topic_id, stats in distribution.items():
            if topic_id in (None, -1):
                continue
            if stats["count"] < min_cluster_size:
                skipped_topics.append({
                    "topic_id": topic_id,
                    "size": stats["count"],
                    "keywords": topic_keywords.get(topic_id, []),
                    "messages": documents_by_topic.get(topic_id, [])
                })

        noise_section = {
            "count": len(noise_docs),
            "messages": noise_docs
        }

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "settings": {
                "config": config_snapshot,
                "runtime": {
                    "fetch_mode": fetch_mode,
                    "posts_indexed": posts_indexed
                }
            },
            "input_posts": self._summarize_loaded_posts(new_posts),
            "documents_summary": {
                "total": len(documents),
                "distribution": distribution,
                "noise": noise_section
            },
            "undistributed_messages": noise_docs,
            "clusters": clusters_detail,
            "skipped_topics": skipped_topics,
            "topic_keywords": {
                _cast_topic_id(topic_id): words
                for topic_id, words in topic_keywords.items()
            },
            "llm_titles": {
                _cast_topic_id(card.get("topic_id")): card["title"]
                for card in cluster_cards
            },
            "metrics": metrics
        }
        
        # Добавляем данные классификации, если они есть
        if classification_data:
            report["classification"] = classification_data
        
        return report

    def _write_topic_modeling_report(self, report_data: Dict[str, Any]) -> None:
        try:
            TOPIC_REPORT_DIR.mkdir(parents=True, exist_ok=True)
            with TOPIC_REPORT_FILE.open("w", encoding="utf-8") as fp:
                json.dump(report_data, fp, ensure_ascii=False, indent=2, default=self._json_default)
            logger.info(f"📝 Отчет тематического моделирования сохранен в {TOPIC_REPORT_FILE}")
        except Exception as exc:
            logger.error(f"Не удалось сохранить отчет тематического моделирования: {exc}")

    def _build_metrics(
        self,
        topic_info: Dict[str, Any],
        save_stats: Dict[str, Any],
        qdrant_stats: Dict[str, Optional[Dict[str, Any]]],
        execution_time: float,
        posts_indexed: int,
        topics_count: int
    ) -> Dict[str, Any]:
        total_documents = len(self._last_topics or [])
        outliers = sum(1 for t in (self._last_topics or []) if t == -1)
        posts_in_clusters = total_documents - outliers
        avg_cluster_size = round(
            mean(topic_info["topic_sizes"].values()), 2
        ) if topic_info["topic_sizes"] else 0
        posts_in_clusters_pct = round(
            (posts_in_clusters / total_documents) * 100, 1
        ) if total_documents else 0
        noise_pct = round(
            (outliers / total_documents) * 100, 1
        ) if total_documents else 0
        title_avg = round(
            mean(self._title_stats["durations"]), 3
        ) if self._title_stats["durations"] else 0.0

        qdrant_batches_total = 0
        qdrant_points_total = 0
        for key in ("search", "clustering"):
            stats = qdrant_stats.get(key)
            if stats:
                qdrant_batches_total += stats.get("batches", 0)
                qdrant_points_total += stats.get("points", 0)

        metrics = {
            "execution_time_sec": round(execution_time, 2),
            "posts_indexed": posts_indexed,
            "documents_in_model": total_documents,
            "topics_found": topics_count,
            "avg_cluster_size": avg_cluster_size,
            "posts_in_clusters_pct": posts_in_clusters_pct,
            "noise_pct": noise_pct,
            "cluster_size_distribution": save_stats.get("size_distribution", {}),
            "word_cloud": save_stats.get("keyword_cloud", []),
            "sample_clusters": save_stats.get("samples", []),
            "title_generation_avg_sec": title_avg,
            "title_generation_count": self._title_stats["count"],
            "qdrant_batches_total": qdrant_batches_total,
            "qdrant_points_total": qdrant_points_total,
            "resource_usage": self._resource_usage,
            "step_timings": {k: round(v, 2) for k, v in self._timings.items()},
            "last_run_at": datetime.utcnow().isoformat()
        }
        return metrics
    
    @property
    def frida_embedder(self) -> 'FRIDAEmbedder':
        """Ленивая загрузка FRIDA embedder"""
        if self._frida_embedder is None:
            self._frida_embedder = FRIDAEmbedder(
                model_name=self.config.frida_model_name,
                device=self.config.frida_device
            )
        return self._frida_embedder
    
    @property
    def gte_embedder(self) -> 'GTEEmbedder':
        """Ленивая загрузка GTE embedder"""
        if self._gte_embedder is None:
            self._gte_embedder = GTEEmbedder(
                model_name=self.config.gte_model_name,
                device=self.config.gte_device
            )
        return self._gte_embedder
    
    @property
    def openai_generator(self) -> Optional['OpenAITitleGenerator']:
        """
        Ленивая загрузка OpenAI генератора
        
        Returns:
            OpenAITitleGenerator или None, если не настроен
        """
        if not self.config.use_openai_for_titles:
            logger.debug("OpenAI отключен в настройках (use_openai_for_titles=false). Используется fallback на ключевые слова.")
            return None
        if self._openai_generator is None:
            try:
                from pro_mode.openai_title_generator import OpenAITitleGenerator
                import os
                
                api_key = os.getenv('OPENAI_API_KEY', '').strip()
                if not api_key:
                    self._progress_log(
                        "OPENAI_API_KEY не найден в переменных окружения. Заголовки будут формироваться по ключевым словам.",
                        level="warning"
                    )
                    return None
                
                logger.info(f"🔧 Инициализация OpenAI TitleGenerator: модель {self.config.openai_model}")
                self._openai_generator = OpenAITitleGenerator(
                    api_key=api_key,
                    model=self.config.openai_model,
                    temperature=self.config.openai_temperature,
                    max_tokens=self.config.openai_max_tokens,
                    timeout=self.config.openai_timeout
                )
            except ImportError as e:
                self._progress_log(
                    f"openai библиотека не установлена: {e}. Установите: pip install openai",
                    level="error"
                )
                self._progress_log("Генерация заголовков будет использовать fallback (ключевые слова)", level="warning")
                return None
            except Exception as e:
                self._progress_log(f"Ошибка инициализации OpenAI: {e}", level="error")
                self._progress_log("Генерация заголовков будет использовать fallback (ключевые слова)", level="warning")
                return None
        return self._openai_generator
    
    def _get_pg_dsn(self) -> str:
        """Получить DSN для PostgreSQL"""
        if self._pg_dsn is None:
            config = get_config()
            if 'postgresql' not in config or 'dsn' not in config['postgresql']:
                raise ValueError("PostgreSQL DSN не найден в config.ini")
            self._pg_dsn = config['postgresql']['dsn']
        return self._pg_dsn
    
    async def _save_embeddings_metadata(
        self,
        posts: List[Dict[str, Any]],
        model_name: str,
        collection_name: str,
        embedding_dim: int
    ) -> None:
        """
        Сохранить метаданные эмбеддингов в таблицу embeddings
        
        Args:
            posts: Список постов с полем post_id
            model_name: Имя модели ("FRIDA" или "GTE")
            collection_name: Имя коллекции Qdrant ("posts_search" или "posts_clustering")
            embedding_dim: Размерность эмбеддинга (1536 для FRIDA, 768 для GTE)
        """
        if not posts:
            return
        
        try:
            dsn = self._get_pg_dsn()
            conn = await asyncpg.connect(dsn=dsn)
            
            try:
                # Пакетная вставка метаданных
                saved_count = 0
                for post in posts:
                    post_id = post.get('post_id')
                    if not post_id:
                        continue
                    
                    try:
                        # Используем ON CONFLICT для обновления существующих записей
                        await conn.execute("""
                            INSERT INTO embeddings (message_id, model, vector_id, embedding_dim, collection_name)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (message_id, model, collection_name) DO UPDATE SET
                                vector_id = EXCLUDED.vector_id,
                                embedding_dim = EXCLUDED.embedding_dim,
                                created_at = NOW()
                        """, 
                        post_id,  # message_id
                        model_name,  # model
                        str(post_id),  # vector_id (ID в Qdrant)
                        embedding_dim,  # embedding_dim
                        collection_name  # collection_name
                        )
                        saved_count += 1
                    except Exception as e:
                        logger.warning(f"Не удалось сохранить метаданные для post_id={post_id}: {e}")
                        continue
                
                if saved_count > 0:
                    logger.debug(f"💾 Сохранено метаданных эмбеддингов: {saved_count} записей (модель={model_name}, коллекция={collection_name})")
                
            finally:
                await conn.close()
                
        except Exception as e:
            # Не прерываем процесс индексации, если сохранение метаданных не удалось
            logger.warning(f"⚠️ Не удалось сохранить метаданные эмбеддингов в PostgreSQL: {e}")
    
    # ============================================================================
    # ШАГ 3: ИНТЕГРАЦИЯ С QDRANT
    # ============================================================================
    
    async def _ensure_collection(
        self, 
        collection_name: str, 
        vector_size: int
    ) -> None:
        """
        Убедиться, что коллекция существует в Qdrant
        
        Args:
            collection_name: Имя коллекции
            vector_size: Размерность векторов
        """
        try:
            # Проверяем существование коллекции
            collections = self.qdrant_client.get_collections().collections
            collection_exists = any(c.name == collection_name for c in collections)
            
            if collection_exists:
                # Проверяем размерность
                collection_info = self.qdrant_client.get_collection(collection_name)
                try:
                    existing_size = collection_info.config.params.vectors.size
                except AttributeError:
                    try:
                        existing_size = collection_info.config.vectors.size
                    except AttributeError:
                        logger.warning(f"Не удалось определить размерность коллекции {collection_name}, пересоздаю...")
                        self.qdrant_client.delete_collection(collection_name=collection_name)
                        collection_exists = False
                
                if collection_exists and existing_size != vector_size:
                    logger.warning(
                        f"Размерность коллекции {collection_name} не совпадает: "
                        f"ожидается {vector_size}, найдено {existing_size}. Пересоздаю..."
                    )
                    self.qdrant_client.delete_collection(collection_name=collection_name)
                    collection_exists = False
            
            if not collection_exists:
                # Создаем коллекцию
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✅ Коллекция {collection_name} создана с размерностью {vector_size}")
            else:
                logger.debug(f"✅ Коллекция {collection_name} существует с правильной размерностью")
                
        except Exception as e:
            logger.error(f"Ошибка при создании коллекции {collection_name}: {e}")
            raise
    
    async def upsert_to_search_index(self, posts: List[Dict[str, Any]]) -> None:
        """
        Добавить/обновить посты в индекс поиска (posts_search)
        
        Использует FRIDA embedder с режимом "search_document"
        
        Args:
            posts: Список постов с полями:
                - post_id: ID поста (int)
                - text: Текст поста (str)
                - timestamp: Временная метка (datetime или str)
        """
        if not posts:
            return
        
        # Валидация и фильтрация постов
        valid_posts = []
        for post in posts:
            if not isinstance(post, dict):
                logger.warning(f"Пропущен невалидный пост (не словарь): {post}")
                continue
            if 'post_id' not in post or 'text' not in post:
                logger.warning(f"Пропущен пост без обязательных полей: {post}")
                continue
            text = post.get('text', '').strip()
            if not text or len(text) < 10:
                logger.debug(f"Пропущен пост {post.get('post_id')} с пустым или слишком коротким текстом")
                continue
            # Обрезаем очень длинные тексты
            if len(text) > 10000:
                text = text[:10000]
                post = {**post, 'text': text}
            valid_posts.append(post)
        
        if not valid_posts:
            logger.warning("Нет валидных постов для индексации в search индекс")
            return
        
        posts = valid_posts
        
        logger.info(f"Индексация {len(posts)} постов в search индекс...")
        
        # Убеждаемся, что коллекция существует
        frida_dim = self.frida_embedder.get_dimension()
        await self._ensure_collection(self.config.search_collection, frida_dim)
        
        # Получаем эмбеддинги через FRIDA с режимом search_document
        logger.info(f"   Генерация эмбеддингов через FRIDA для {len(posts)} постов...")
        texts = [post['text'] for post in posts]
        
        # Анализ длин текстов для оптимизации
        text_lengths = [len(text) for text in texts]
        avg_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
        max_length = max(text_lengths) if text_lengths else 0
        total_chars = sum(text_lengths)
        logger.info(f"   📊 Статистика текстов: avg={avg_length:.0f} символов, max={max_length}, total={total_chars}")
        
        # Дополнительная обрезка очень длинных текстов (FRIDA оптимально работает с текстами до 512 токенов)
        # Примерно 2000 символов для русского текста
        max_text_length = 2000
        texts_trimmed = []
        trimmed_count = 0
        for text in texts:
            if len(text) > max_text_length:
                texts_trimmed.append(text[:max_text_length])
                trimmed_count += 1
            else:
                texts_trimmed.append(text)
        if trimmed_count > 0:
            logger.info(f"   ✂️ Обрезано {trimmed_count} текстов до {max_text_length} символов")
        texts = texts_trimmed
        
        embed_batch = min(self.config.batch_size_qdrant, len(texts))
        frida_vectors: List[List[float]] = []
        total_batches = (len(texts) + embed_batch - 1) // embed_batch
        batch_start_time = time.perf_counter()
        for idx in range(0, len(texts), embed_batch):
            batch_texts = texts[idx:idx + embed_batch]
            batch_num = idx // embed_batch + 1
            batch_batch_start = time.perf_counter()
            logger.info(f"   FRIDA генерация батча {batch_num}/{total_batches} ({len(batch_texts)} текстов)...")
            frida_vectors.extend(self.frida_embedder.encode(batch_texts, mode="search_document"))
            batch_duration = time.perf_counter() - batch_batch_start
            logger.info(f"   ✅ Батч {batch_num}/{total_batches} завершен за {batch_duration:.1f}с ({len(batch_texts)/batch_duration:.2f} текстов/сек)")
        total_duration = time.perf_counter() - batch_start_time
        logger.info(f"   ✅ Все эмбеддинги сгенерированы за {total_duration:.1f}с ({len(texts)/total_duration:.1f} текстов/сек)")
        embeddings = frida_vectors
        logger.info(f"   ✅ Эмбеддинги сгенерированы: {len(embeddings)} векторов размерностью {len(embeddings[0]) if embeddings else 0}")
        
        # Формируем точки для Qdrant
        points = []
        for i, post in enumerate(posts):
            point = PointStruct(
                id=post['post_id'],
                vector=embeddings[i],
                payload={
                    "post_id": post['post_id'],
                    "text": post['text'],
                    "timestamp": post['timestamp'].isoformat() if isinstance(post['timestamp'], datetime) else str(post['timestamp'])
                }
            )
            points.append(point)
        
        # Пакетная вставка
        batch_size = self.config.batch_size_qdrant
        total_batches = (len(points) + batch_size - 1) // batch_size
        logger.info(f"   Начало пакетной вставки: {total_batches} батчей по {batch_size} точек")
        
        for i in range(0, len(points), batch_size):
            self._check_cancellation()
            batch = points[i:i + batch_size]
            batch_num = i // batch_size + 1
            logger.info(f"   Вставка батча {batch_num}/{total_batches} ({len(batch)} точек)...")
            
            try:
                self.qdrant_client.upsert(
                    collection_name=self.config.search_collection,
                    points=batch
                )
                logger.info(f"   ✅ Батч {batch_num}/{total_batches} вставлен успешно")
                self._update_resource_usage()
            except Exception as e:
                logger.error(f"   ❌ Ошибка при вставке батча {batch_num}: {e}")
                raise
        
        # Сохраняем метаданные эмбеддингов в PostgreSQL
        try:
            await self._save_embeddings_metadata(
                posts=posts,
                model_name="FRIDA",
                collection_name=self.config.search_collection,
                embedding_dim=frida_dim
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сохранить метаданные FRIDA эмбеддингов: {e}")
        
        logger.info(f"✅ Индексация в search индекс завершена: {len(posts)} постов")
        return {
            "points": len(points),
            "batches": total_batches
        }
    
    async def upsert_to_clustering_index(self, posts: List[Dict[str, Any]]) -> None:
        """
        Добавить/обновить посты в индекс кластеризации (posts_clustering)
        
        Использует GTE embedder (без префиксов!)
        
        Args:
            posts: Список постов с полями:
                - post_id: ID поста (int)
                - text: Текст поста (str)
                - timestamp: Временная метка (datetime или str)
        """
        if not posts:
            return
        
        # Валидация и фильтрация постов (та же логика, что и для search)
        valid_posts = []
        for post in posts:
            if not isinstance(post, dict):
                logger.warning(f"Пропущен невалидный пост (не словарь): {post}")
                continue
            if 'post_id' not in post or 'text' not in post:
                logger.warning(f"Пропущен пост без обязательных полей: {post}")
                continue
            text = post.get('text', '').strip()
            if not text or len(text) < 10:
                logger.debug(f"Пропущен пост {post.get('post_id')} с пустым или слишком коротким текстом")
                continue
            # Обрезаем очень длинные тексты
            if len(text) > 10000:
                text = text[:10000]
                post = {**post, 'text': text}
            valid_posts.append(post)
        
        if not valid_posts:
            logger.warning("Нет валидных постов для индексации в clustering индекс")
            return
        
        posts = valid_posts
        
        logger.info(f"Индексация {len(posts)} постов в clustering индекс...")
        
        # Убеждаемся, что коллекция существует
        gte_dim = self.gte_embedder.get_dimension()
        await self._ensure_collection(self.config.clustering_collection, gte_dim)
        
        # Получаем эмбеддинги через GTE (без префиксов!)
        logger.info(f"   Генерация эмбеддингов через GTE для {len(posts)} постов...")
        texts = [post['text'] for post in posts]
        embed_batch = min(self.config.batch_size_qdrant, len(texts))
        gte_vectors: List[List[float]] = []
        total_batches = (len(texts) + embed_batch - 1) // embed_batch
        for idx in range(0, len(texts), embed_batch):
            batch_texts = texts[idx:idx + embed_batch]
            batch_num = idx // embed_batch + 1
            logger.info(f"   GTE генерация батча {batch_num}/{total_batches} ({len(batch_texts)} текстов)")
            gte_vectors.extend(self.gte_embedder.encode(batch_texts))
        embeddings = gte_vectors
        logger.info(f"   ✅ Эмбеддинги сгенерированы: {len(embeddings)} векторов размерностью {len(embeddings[0]) if embeddings else 0}")
        
        # Формируем точки для Qdrant
        points = []
        for i, post in enumerate(posts):
            point = PointStruct(
                id=post['post_id'],
                vector=embeddings[i],
                payload={
                    "post_id": post['post_id'],
                    "text": post['text'],
                    "timestamp": post['timestamp'].isoformat() if isinstance(post['timestamp'], datetime) else str(post['timestamp'])
                }
            )
            points.append(point)
        
        # Пакетная вставка
        batch_size = self.config.batch_size_qdrant
        total_batches = (len(points) + batch_size - 1) // batch_size
        logger.info(f"   Начало пакетной вставки: {total_batches} батчей по {batch_size} точек")
        
        for i in range(0, len(points), batch_size):
            self._check_cancellation()
            batch = points[i:i + batch_size]
            batch_num = i // batch_size + 1
            logger.info(f"   Вставка батча {batch_num}/{total_batches} ({len(batch)} точек)...")
            
            try:
                self.qdrant_client.upsert(
                    collection_name=self.config.clustering_collection,
                    points=batch
                )
                logger.info(f"   ✅ Батч {batch_num}/{total_batches} вставлен успешно")
                self._update_resource_usage()
            except Exception as e:
                logger.error(f"   ❌ Ошибка при вставке батча {batch_num}: {e}")
                raise
        
        # Сохраняем метаданные эмбеддингов в PostgreSQL
        try:
            await self._save_embeddings_metadata(
                posts=posts,
                model_name="GTE",
                collection_name=self.config.clustering_collection,
                embedding_dim=gte_dim
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сохранить метаданные GTE эмбеддингов: {e}")
        
        logger.info(f"✅ Индексация в clustering индекс завершена: {len(posts)} постов")
        return {
            "points": len(points),
            "batches": total_batches
        }
    
    async def fetch_all_for_clustering(
        self, 
        limit: Optional[int] = None
    ) -> Tuple[List[int], List[str], List[List[float]]]:
        """
        Выгрузить все тексты и эмбеддинги из posts_clustering для кластеризации
        
        Args:
            limit: Максимальное количество постов для выгрузки
        
        Returns:
            Кортеж (post_ids, texts, embeddings):
                - post_ids: Список ID постов
                - texts: Список текстов постов
                - embeddings: Список эмбеддингов (каждый - список float)
        """
        effective_limit = limit or self.config.max_posts_for_clustering
        effective_limit = min(effective_limit, self.config.max_posts_for_clustering)
        logger.info(f"Выгрузка данных из {self.config.clustering_collection} (лимит: {effective_limit})...")
        
        # Проверяем существование коллекции
        collections = self.qdrant_client.get_collections().collections
        collection_exists = any(c.name == self.config.clustering_collection for c in collections)
        
        if not collection_exists:
            logger.warning(f"Коллекция {self.config.clustering_collection} не существует. Возвращаем пустые данные.")
            return [], [], []
        
        # Проверяем, есть ли данные в коллекции
        try:
            count_result = self.qdrant_client.count(self.config.clustering_collection)
            if count_result.count == 0:
                logger.warning(f"Коллекция {self.config.clustering_collection} пуста. Возвращаем пустые данные.")
                return [], [], []
        except Exception as e:
            logger.warning(f"Не удалось проверить количество точек в коллекции: {e}")
        
        # Используем scroll для получения всех точек
        try:
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.config.clustering_collection,
                limit=effective_limit,
                with_payload=True,
                with_vectors=True
            )
            
            points, _ = scroll_result
            
            post_ids = []
            texts = []
            embeddings = []
            
            for point in points:
                if point.payload and 'text' in point.payload and 'post_id' in point.payload:
                    post_ids.append(point.payload['post_id'])
                    texts.append(point.payload['text'])
                    embeddings.append(point.vector)
            
            logger.info(f"✅ Выгружено {len(texts)} постов для кластеризации")
            return post_ids, texts, embeddings
            
        except Exception as e:
            logger.error(f"Ошибка при выгрузке данных из Qdrant: {e}")
            raise
    
    # ============================================================================
    # ШАГ 4: ИНТЕГРАЦИЯ С BERTOPIC
    # ============================================================================
    
    async def build_topic_model(self) -> BERTopic:
        """
        Построить тематическую модель через BERTopic
        
        Использует данные из posts_clustering коллекции Qdrant.
        Передает готовые эмбеддинги в BERTopic (не генерирует их заново).
        
        Returns:
            Обученная модель BERTopic
        """
        logger.info("🔨 Построение тематической модели через BERTopic...")
        
        # Выгружаем все тексты и эмбеддинги
        post_ids, texts, embeddings = await self.fetch_all_for_clustering()
        
        if len(texts) < self.config.hdbscan_min_cluster_size:
            raise ValueError(
                f"Недостаточно данных для кластеризации: "
                f"найдено {len(texts)} постов, требуется минимум {self.config.hdbscan_min_cluster_size}"
            )
        
        logger.info(f"📊 Обработка {len(texts)} постов...")
        
        # Проверяем доступность библиотек
        if not UMAP_AVAILABLE:
            raise ImportError(
                "umap-learn не установлен. "
                "Установите: pip install umap-learn"
            )
        if not HDBSCAN_AVAILABLE:
            raise ImportError(
                "hdbscan не установлен. "
                "Установите: pip install hdbscan"
            )
        if not BERTOPIC_AVAILABLE:
            raise ImportError(
                "bertopic не установлен. "
                "Установите: pip install bertopic"
            )
        
        # Инициализируем UMAP
        umap_model = UMAP(
            n_neighbors=self.config.umap_n_neighbors,
            n_components=self.config.umap_n_components,
            min_dist=self.config.umap_min_dist,
            metric='cosine',
            random_state=42
        )
        
        # Инициализируем HDBSCAN
        hdbscan_model = HDBSCAN(
            min_cluster_size=self.config.hdbscan_min_cluster_size,
            min_samples=self.config.hdbscan_min_samples,
            metric='euclidean',
            cluster_selection_method='eom',
            prediction_data=True  # Важно для предсказания новых документов
        )
        
        # Инициализируем BERTopic
        # embedding_model=None, т.к. мы передаем готовые эмбеддинги
        self._bertopic = BERTopic(
            embedding_model=None,  # Используем готовые эмбеддинги
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            nr_topics=self.config.nr_topics,  # Автоматическое объединение мелких тем
            verbose=True
        )
        
        # Преобразуем embeddings в numpy array
        embeddings_array = np.array(embeddings)
        
        # Обучаем модель
        logger.info("🎓 Обучение BERTopic...")
        topics, probs = self._bertopic.fit_transform(texts, embeddings=embeddings_array)
        
        # Сохраняем post_ids для последующего использования
        self._last_post_ids = post_ids
        self._last_topics = topics
        self._last_probs = probs
        self._last_texts = list(texts)
        
        # Логируем статистику
        unique_topics = set(topics)
        noise_count = sum(1 for t in topics if t == -1)
        logger.info(f"✅ Модель обучена:")
        logger.info(f"   - Найдено тем: {len(unique_topics) - (1 if -1 in unique_topics else 0)}")
        logger.info(f"   - Шум (outliers): {noise_count}")
        logger.info(f"   - Средний размер темы: {len(texts) / max(1, len(unique_topics) - 1):.1f}")
        
        return self._bertopic
    
    def get_topic_info(self) -> Dict[str, Any]:
        """
        Получить информацию о темах из обученной модели BERTopic
        
        Returns:
            Словарь с информацией о темах:
                - topics_df: DataFrame с темами, ключевыми словами, размерами
                - topic_sizes: Словарь {topic_id: размер}
                - topic_keywords: Словарь {topic_id: [ключевые слова]}
        """
        if self._bertopic is None:
            raise ValueError("Модель BERTopic не обучена. Вызовите build_topic_model() сначала")
        
        # Получаем DataFrame с информацией о темах
        topics_df = self._bertopic.get_topic_info()
        
        # Получаем размеры тем
        topic_sizes = {}
        for topic_id in topics_df['Topic'].values:
            if topic_id != -1:  # Игнорируем шум
                size = len([t for t in self._bertopic.topics_ if t == topic_id])
                topic_sizes[topic_id] = size
        
        # Получаем ключевые слова для каждой темы
        topic_keywords = {}
        for topic_id in topics_df['Topic'].values:
            if topic_id != -1:
                keywords = self._bertopic.get_topic(topic_id)
                topic_keywords[topic_id] = [word for word, _ in keywords[:10]]  # Топ-10 ключевых слов
        
        return {
            "topics_df": topics_df,
            "topic_sizes": topic_sizes,
            "topic_keywords": topic_keywords
        }
    
    async def save_topics_to_db(
        self,
        topic_info: Optional[Dict[str, Any]] = None,
        texts: Optional[List[str]] = None,
        topics: Optional[List[int]] = None,
        post_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Сохранить результаты тематического моделирования в PostgreSQL
        
        Для каждой темы:
        - Создает запись в dedup_clusters (или обновляет существующую)
        - Генерирует заголовок через Qwen2.5
        - Сохраняет ключевые слова
        
        Для каждого поста:
        - Обновляет связь в cluster_messages (post_id -> cluster_id)
        
        Args:
            topic_info: Результат get_topic_info() - информация о темах (если None, вызывается автоматически)
            texts: Список текстов постов (если None, используется последний результат build_topic_model)
            topics: Список topic_id для каждого поста (если None, используется последний результат)
            post_ids: Список ID постов (если None, используется последний результат)
        
        Returns:
            Словарь со статистикой:
                - clusters_created: Количество созданных кластеров
                - posts_linked: Количество привязанных постов
        """
        logger.info("💾 Сохранение результатов тематического моделирования в PostgreSQL...")
        
        if self._bertopic is None:
            raise ValueError("Модель BERTopic не обучена. Вызовите build_topic_model() сначала")
        
        # Используем сохраненные данные, если параметры не указаны
        if topics is None:
            if self._last_topics is None:
                raise ValueError("Темы не указаны и не сохранены. Укажите topics или вызовите build_topic_model()")
            topics = self._last_topics
        
        if post_ids is None:
            if self._last_post_ids is None:
                raise ValueError("ID постов не указаны и не сохранены. Укажите post_ids или вызовите build_topic_model()")
            post_ids = self._last_post_ids
        
        if texts is None:
            # Нужно получить тексты из Qdrant по post_ids
            # Для упрощения, получаем все данные заново
            post_ids_from_qdrant, texts_from_qdrant, _ = await self.fetch_all_for_clustering()
            # Создаем маппинг post_id -> text
            text_map = {pid: text for pid, text in zip(post_ids_from_qdrant, texts_from_qdrant)}
            texts = [text_map.get(pid, "") for pid in post_ids]
        
        self._last_texts = texts
        
        if topic_info is None:
            topic_info = self.get_topic_info()
        
        if len(texts) != len(topics):
            raise ValueError(f"Несоответствие размеров: {len(texts)} текстов, {len(topics)} тем")
        
        if len(post_ids) != len(texts):
            raise ValueError(f"Несоответствие размеров: {len(texts)} текстов, {len(post_ids)} ID")
        
        dsn = self._get_pg_dsn()
        conn = await asyncpg.connect(dsn=dsn)
        
        try:
            clusters_created = 0
            posts_linked = 0
            cluster_cards: List[Dict[str, Any]] = []
            keyword_counter: Counter = Counter()
            size_distribution: Counter = Counter()
            
            # Группируем посты по темам
            topic_to_posts: Dict[int, List[Tuple[int, str]]] = {}
            for i, topic_id in enumerate(topics):
                if topic_id == -1:  # Пропускаем шум
                    continue
                if topic_id not in topic_to_posts:
                    topic_to_posts[topic_id] = []
                topic_to_posts[topic_id].append((post_ids[i], texts[i]))
            
            eligible_topics = {
                topic_id: posts_data
                for topic_id, posts_data in topic_to_posts.items()
                if len(posts_data) >= self.config.hdbscan_min_cluster_size
            }
            total_topics = len(eligible_topics)
            completed_titles = 0
            if total_topics:
                # Логируем метод генерации заголовков
                if self.config.use_openai_for_titles:
                    logger.info(f"📝 Генерация заголовков через OpenAI для {total_topics} тем...")
                else:
                    logger.info(f"📝 Генерация заголовков через ключевые слова (OpenAI отключен) для {total_topics} тем...")
                
                self._progress_step("title_generation", "running", {
                    "topics": total_topics,
                    "completed": completed_titles
                })
            
            # Обрабатываем каждую тему
            for topic_id, posts_data in eligible_topics.items():
                size_distribution[len(posts_data)] += 1
                
                # Получаем ключевые слова
                keywords = topic_info['topic_keywords'].get(topic_id, [])
                keyword_counter.update(keywords[:10])

                # Получаем примеры текстов
                sample_texts = [
                    text[:500]
                    for _, text in posts_data[:self.config.num_sample_texts]
                ]
                
                # Генерируем заголовок через OpenAI (если доступен) или используем fallback
                title = None
                openai_gen = self.openai_generator  # Инициализируем генератор (ленивая загрузка)
                if openai_gen is not None and self.config.use_openai_for_titles:
                    try:
                        logger.info(f"   Генерация заголовка через OpenAI для темы {topic_id}...")
                        title_start = time.perf_counter()
                        title = await openai_gen.generate_title(
                            topic_id=topic_id,
                            keywords=keywords,
                            sample_texts=sample_texts,
                            temperature=self.config.openai_temperature,
                            max_tokens=self.config.openai_max_tokens
                        )
                        self._record_title_duration(time.perf_counter() - title_start)
                        logger.info(f"   ✅ Заголовок сгенерирован через OpenAI: {title[:50]}...")
                    except Exception as e:
                        logger.warning(f"   ⚠️ Ошибка генерации заголовка через OpenAI для темы {topic_id}: {e}")
                else:
                    logger.debug(f"   OpenAI генератор недоступен, используется fallback для темы {topic_id}")
                
                # Fallback: используем ключевые слова или первый текст
                if not title or len(title.strip()) < 5:
                    if keywords:
                        # Улучшенный fallback: формируем более читаемый заголовок из ключевых слов
                        # Берем топ-3 ключевых слова и объединяем их более естественно
                        if len(keywords) >= 3:
                            title = f"{keywords[0]}, {keywords[1]} и {keywords[2]}"
                        elif len(keywords) == 2:
                            title = f"{keywords[0]} и {keywords[1]}"
                        else:
                            title = keywords[0] if keywords else "Тема"
                    elif sample_texts:
                        # Берем первые слова из первого примера
                        first_words = sample_texts[0].split()[:8]
                        title = " ".join(first_words)
                    else:
                        title = f"Тема {topic_id}"
                    
                    logger.info(f"   📝 Использован fallback заголовок для темы {topic_id}: {title[:50]}...")
                
                # Создаем UUID для кластера
                cluster_id = str(uuid.uuid4())

                cluster_cards.append({
                    "topic_id": topic_id,
                    "title": (title or "").strip()[:self.config.max_title_length],
                    "keywords": keywords[:5],
                    "size": len(posts_data),
                    "sample": sample_texts[0][:200] if sample_texts else ""
                })
                title = cluster_cards[-1]["title"]
                
                # Сохраняем кластер в dedup_clusters
                await conn.execute("""
                    INSERT INTO dedup_clusters (
                        cluster_id, title, summary, created_at, stats
                    ) VALUES ($1, $2, $3, $4, $5::jsonb)
                    ON CONFLICT (cluster_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        updated_at = NOW(),
                        stats = EXCLUDED.stats
                """,
                    cluster_id,
                    title,
                    sample_texts[0][:500] if sample_texts else "",  # summary
                    datetime.now(),
                    json.dumps({
                        'message_count': len(posts_data),
                        'topic_id': topic_id,
                        'keywords': keywords[:10]
                    })
                )
                
                clusters_created += 1
                
                # Связываем посты с кластером
                for post_id, _ in posts_data:
                    try:
                        await conn.execute("""
                            INSERT INTO cluster_messages (
                                cluster_id, message_id, similarity_score, is_primary
                            ) VALUES ($1, $2, $3, $4)
                            ON CONFLICT (cluster_id, message_id) DO UPDATE SET
                                similarity_score = EXCLUDED.similarity_score
                        """,
                            cluster_id,
                            post_id,
                            1.0,  # similarity_score (можно улучшить, используя probs из BERTopic)
                            False  # is_primary (можно выбрать первый или самый репрезентативный)
                        )
                        posts_linked += 1
                    except Exception as e:
                        logger.warning(f"Ошибка привязки поста {post_id} к кластеру {cluster_id}: {e}")
                        continue
                
                completed_titles += 1
                self._progress_step("title_generation", "running", {
                    "topics": total_topics,
                    "completed": completed_titles,
                    "current_topic": int(topic_id) if isinstance(topic_id, (int, np.integer)) else topic_id
                })
                self._progress_log(
                    f"Генерация заголовков: {completed_titles}/{total_topics} (тема {topic_id})",
                    level="info"
                )
            
            logger.info(f"✅ Сохранение завершено:")
            logger.info(f"   - Создано кластеров: {clusters_created}")
            logger.info(f"   - Привязано постов: {posts_linked}")
            
            # Освобождаем память OpenAI после генерации заголовков
            if self._openai_generator is not None:
                logger.info("🧹 Освобождение памяти OpenAI после генерации заголовков...")
                self._openai_generator.release_model()
                self._openai_generator = None
                gc.collect()
                # Очистка GPU кэша (если был использован)
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        logger.info("   ✅ GPU кэш очищен")
                except Exception:
                    pass
            
            return {
                "clusters_created": clusters_created,
                "posts_linked": posts_linked,
                "samples": cluster_cards[:10],
                "cluster_cards": cluster_cards,
                "keyword_cloud": [
                    {"text": word, "weight": count}
                    for word, count in keyword_counter.most_common(50)
                ],
                "size_distribution": dict(size_distribution)
            }
            
        finally:
            await conn.close()

    async def regenerate_titles(
        self,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Генерация заголовков через OpenAI по существующим кластерам."""
        openai_gen = self.openai_generator
        if openai_gen is None:
            raise RuntimeError("OpenAI генератор недоступен. Проверьте настройки Topic Modeling и OPENAI_API_KEY.")

        limit_value = limit if isinstance(limit, int) and limit > 0 else 100
        logger.info(f"🔁 Перегенерация заголовков через OpenAI (limit={limit_value})")
        start_time = time.perf_counter()
        conn = await asyncpg.connect(self._get_pg_dsn())
        updated = 0
        try:
            rows = await conn.fetch(
                """
                SELECT cluster_id, stats, summary
                FROM dedup_clusters
                ORDER BY updated_at DESC NULLS LAST
                LIMIT $1
                """,
                limit_value
            )

            for idx, row in enumerate(rows, start=1):
                stats = row.get('stats') or {}
                keywords = []
                if isinstance(stats, dict):
                    keywords = stats.get('keywords') or []
                elif isinstance(stats, str):
                    try:
                        keywords = json.loads(stats).get('keywords', [])
                    except Exception:
                        keywords = []

                if not isinstance(keywords, list):
                    keywords = list(keywords) if keywords else []

                sample_texts = [str(row['summary'])] if row.get('summary') else []
                logger.info(f"   Генерация заголовка через OpenAI для кластера: {row['cluster_id']} ({idx}/{len(rows)})")
                title_start = time.perf_counter()
                title = await openai_gen.generate_title(
                    topic_id=idx,
                    keywords=keywords,
                    sample_texts=sample_texts,
                    temperature=self.config.openai_temperature,
                    max_tokens=self.config.openai_max_tokens
                )
                self._record_title_duration(time.perf_counter() - title_start)

                await conn.execute(
                    """
                    UPDATE dedup_clusters
                    SET title = $1, updated_at = NOW()
                    WHERE cluster_id = $2
                    """,
                    title[:self.config.max_title_length],
                    row['cluster_id']
                )
                updated += 1

        finally:
            await conn.close()

        duration = time.perf_counter() - start_time
        logger.info(f"✅ Заголовки обновлены: {updated} записей за {duration:.1f}c")
        return {"processed": updated, "limit": limit_value, "duration": round(duration, 1)}
    
    # ============================================================================
    # ШАГ 7: ОСНОВНОЙ МЕТОД - ПОЛНЫЙ ПАЙПЛАЙН
    # ============================================================================
    
    async def run_full_pipeline(
        self,
        new_posts: Optional[List[Dict[str, Any]]] = None,
        fetch_from_db: bool = True,
        run_classification: bool = True
    ) -> Dict[str, Any]:
        """
        Выполнить полный цикл тематического моделирования с трекингом прогресса.
        """
        start_time = time.perf_counter()
        self._timings.clear()
        self._resource_usage = {"peak_ram_gb": 0.0}
        self._title_stats = {"count": 0, "durations": []}
        qdrant_stats: Dict[str, Optional[Dict[str, Any]]] = {"search": None, "clustering": None}
        current_step = None

        settings_snapshot = {
            "fetch_from_db": fetch_from_db,
            "max_posts_for_clustering": self.config.max_posts_for_clustering,
            "batch_size_qdrant": self.config.batch_size_qdrant,
            "use_openai_for_titles": self.config.use_openai_for_titles
        }
        self._progress_start(settings_snapshot)

        try:
            # ШАГ 1. Загружаем посты
            current_step = "fetch_posts"
            self._progress_step(current_step, "running", {
                "mode": "postgresql" if fetch_from_db else "manual"
            })
            step_start = time.perf_counter()
            if new_posts is None and fetch_from_db:
                new_posts = await self._fetch_posts_from_db(
                    limit=None,
                    days_back=self.config.rerun_interval_hours // 24 if self.config.rerun_interval_hours >= 24 else 30
                )
            elif new_posts is None:
                new_posts = []
            fetch_duration = time.perf_counter() - step_start
            self._record_timing("fetch_posts", fetch_duration)
            self._progress_step(current_step, "done", {
                "count": len(new_posts),
                "duration": round(fetch_duration, 2)
            })
            self._progress_log(f"Получено {len(new_posts)} постов для индексации", "info")
            self._check_cancellation()

            # ШАГ 2-4. Векторизация и индексация
            posts_indexed = len(new_posts)
            if new_posts:
                # Освобождаем память OpenAI перед загрузкой FRIDA (если OpenAI был загружен)
                if self._openai_generator is not None:
                    logger.info("🧹 Освобождение памяти OpenAI перед загрузкой FRIDA...")
                    self._openai_generator.release_model()
                    self._openai_generator = None
                    gc.collect()
                    # Очистка GPU кэша, если используется
                    try:
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                            logger.info("   ✅ GPU кэш очищен")
                    except Exception:
                        pass
                
                self._progress_step("frida_embeddings", "running", {"count": len(new_posts)})
                self._progress_step("qdrant_indexing", "running", {"collections": 2})
                step_start = time.perf_counter()
                qdrant_stats["search"] = await self.upsert_to_search_index(new_posts)
                frida_duration = time.perf_counter() - step_start
                self._record_timing("frida_embeddings", frida_duration)
                self._progress_step("frida_embeddings", "done", {
                    "vectors": qdrant_stats["search"]["points"],
                    "duration": round(frida_duration, 2)
                })
                self._progress_log(f"FRIDA завершила индексацию {len(new_posts)} постов за {frida_duration:.1f}с", "info")
                # Освобождаем память перед загрузкой GTE
                self._progress_log("Освобождение памяти после FRIDA перед загрузкой GTE", "info")
                self._frida_embedder = None
                gc.collect()

                self._check_cancellation()
                self._progress_step("gte_embeddings", "running", {"count": len(new_posts)})
                step_start = time.perf_counter()
                qdrant_stats["clustering"] = await self.upsert_to_clustering_index(new_posts)
                gte_duration = time.perf_counter() - step_start
                self._record_timing("gte_embeddings", gte_duration)
                self._progress_step("gte_embeddings", "done", {
                    "vectors": qdrant_stats["clustering"]["points"],
                    "duration": round(gte_duration, 2)
                })
                self._progress_log(f"GTE завершила индексацию {len(new_posts)} постов за {gte_duration:.1f}с", "info")
                # Освобождаем память перед BERTopic
                self._progress_log("Освобождение памяти после GTE перед BERTopic", "info")
                self._gte_embedder = None
                gc.collect()

                total_batches = (qdrant_stats["search"]["batches"] + qdrant_stats["clustering"]["batches"])
                self._progress_step("qdrant_indexing", "done", {"batches_total": total_batches})
            else:
                self._progress_step("frida_embeddings", "skipped", {"reason": "Нет новых постов"})
                self._progress_step("gte_embeddings", "skipped", {"reason": "Нет новых постов"})
                self._progress_step("qdrant_indexing", "skipped", {"reason": "Нет новых постов"})

            self._check_cancellation()

            # ШАГ 5. Построение BERTopic
            current_step = "bertopic"
            self._progress_step(current_step, "running", {
                "limit": self.config.max_posts_for_clustering
            })
            step_start = time.perf_counter()
            bertopic_model = await self.build_topic_model()
            bertopic_duration = time.perf_counter() - step_start
            self._record_timing("bertopic", bertopic_duration)
            documents_count = len(self._last_topics or [])
            self._progress_step(current_step, "done", {
                "documents": documents_count,
                "duration": round(bertopic_duration, 2)
            })

            topic_info = self.get_topic_info()
            topics_count = len(topic_info["topic_sizes"])
            self._progress_log(f"BERTopic завершен: найдено {topics_count} тем", "info")

            # ШАГ 6-7. Генерация заголовков и сохранение
            self._progress_step("title_generation", "running", {"topics": topics_count})
            self._progress_step("save_to_db", "running", {})
            save_stats = await self.save_topics_to_db(topic_info=topic_info)
            title_avg = round(mean(self._title_stats["durations"]), 3) if self._title_stats["durations"] else 0.0
            self._progress_step("title_generation", "done", {
                "generated": self._title_stats["count"],
                "avg_time_sec": title_avg
            })
            self._progress_step("save_to_db", "done", {
                "clusters": save_stats["clusters_created"],
                "posts_linked": save_stats["posts_linked"]
            })
            self._progress_log(
                f"Сохранено {save_stats['clusters_created']} кластеров, привязано {save_stats['posts_linked']} постов",
                "info"
            )

            # ШАГ 8. Классификация сообщений (опционально)
            classification_stats = None
            if run_classification:
                try:
                    current_step = "classification"
                    self._progress_step(current_step, "running", {})
                    step_start = time.perf_counter()
                    
                    from pro_mode.classification_service import ClassificationService
                    classification_service = ClassificationService()
                    
                    # Получаем ID сообщений для классификации
                    message_ids = [post.get('post_id') for post in new_posts if post.get('post_id')]
                    if not message_ids and fetch_from_db:
                        # Если нет новых постов, классифицируем последние сообщения
                        message_ids = None
                    
                    classification_stats = await classification_service.classify_all_messages_in_pipeline(
                        message_ids=message_ids,
                        limit=len(new_posts) if new_posts else None
                    )
                    
                    classification_duration = time.perf_counter() - step_start
                    self._record_timing("classification", classification_duration)
                    self._progress_step(current_step, "done", {
                        "processed": classification_stats.get('processed', 0),
                        "classified": classification_stats.get('classified', 0),
                        "success_rate": round(classification_stats.get('success_rate', 0), 1),
                        "duration": round(classification_duration, 2)
                    })
                    self._progress_log(
                        f"Классификация завершена: {classification_stats.get('processed', 0)} обработано, "
                        f"{classification_stats.get('classified', 0)} классифицировано "
                        f"({classification_stats.get('success_rate', 0):.1f}%)",
                        "info"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка классификации сообщений: {e}")
                    self._progress_step(current_step, "error", {"message": str(e)})
                    classification_stats = {
                        'processed': 0,
                        'classified': 0,
                        'errors': 1,
                        'success_rate': 0
                    }
            else:
                logger.info("⏭️ Классификация пропущена (отключена)")

            execution_time = time.perf_counter() - start_time
            metrics = self._build_metrics(
                topic_info=topic_info,
                save_stats=save_stats,
                qdrant_stats=qdrant_stats,
                execution_time=execution_time,
                posts_indexed=posts_indexed,
                topics_count=topics_count
            )
            self._progress_metrics(metrics)

            # Получаем данные классификации для отчета
            classification_data = None
            if run_classification and classification_stats:
                try:
                    classification_data = await self._get_classification_data()
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось получить данные классификации для отчета: {e}")

            report_payload = self._build_topic_modeling_report(
                new_posts=new_posts,
                topic_info=topic_info,
                save_stats=save_stats,
                metrics=metrics,
                posts_indexed=posts_indexed,
                fetch_mode="postgresql" if fetch_from_db else "manual",
                classification_data=classification_data
            )
            self._write_topic_modeling_report(report_payload)

            result = {
                "posts_indexed": posts_indexed,
                "topics_found": topics_count,
                "clusters_created": save_stats["clusters_created"],
                "posts_linked": save_stats["posts_linked"],
                "execution_time": execution_time,
                "metrics": metrics,
                "classification": classification_stats
            }

            logger.info("✅ Пайплайн тематического моделирования завершен успешно")
            logger.info(f"   Проиндексировано постов: {posts_indexed}")
            logger.info(f"   Найдено тем: {topics_count}")
            logger.info(f"   Создано кластеров: {save_stats['clusters_created']}")
            logger.info(f"   Привязано постов: {save_stats['posts_linked']}")
            logger.info(f"   Время выполнения: {execution_time:.2f} сек")

            if self.progress_tracker:
                self.progress_tracker.finish("success", result)
            return result

        except TopicModelingCancelled as cancel_exc:
            if current_step:
                self._progress_step(current_step, "cancelled", {"message": str(cancel_exc)})
            execution_time = time.perf_counter() - start_time
            partial_result = {
                "posts_indexed": len(new_posts) if new_posts else 0,
                "topics_found": len(set(self._last_topics or [])) - 1 if self._last_topics else 0,
                "clusters_created": 0,
                "posts_linked": 0,
                "execution_time": execution_time,
                "metrics": {}
            }
            if self.progress_tracker:
                self.progress_tracker.finish("cancelled", partial_result, error=str(cancel_exc))
            logger.warning("⚠️ Пайплайн остановлен пользователем")
            self._progress_log("Пайплайн остановлен пользователем", "warning")
            raise
        except Exception as e:
            if current_step:
                self._progress_step(current_step, "error", {"message": str(e)})
            execution_time = time.perf_counter() - start_time
            logger.error(f"❌ Ошибка в пайплайне тематического моделирования: {e}")
            self._progress_log(f"Ошибка пайплайна: {e}", "error")
            if self.progress_tracker:
                self.progress_tracker.finish(
                    "error",
                    {"execution_time": execution_time},
                    error=str(e)
                )
            raise
    
    async def _fetch_posts_from_db(
        self,
        limit: Optional[int] = None,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Загрузить посты из PostgreSQL для индексации
        
        Args:
            limit: Максимальное количество постов (если None, без ограничений)
            days_back: Загружать посты за последние N дней
        
        Returns:
            Список постов: [{"post_id": int, "text": str, "timestamp": datetime}, ...]
        """
        logger.info(f"📥 Начало загрузки постов из PostgreSQL (days_back={days_back}, limit={limit})")
        dsn = self._get_pg_dsn()
        logger.debug(f"Подключение к PostgreSQL: {dsn.split('@')[1] if '@' in dsn else 'скрыто'}")
        
        conn = await asyncpg.connect(dsn=dsn)
        logger.debug("✅ Подключение к PostgreSQL установлено")
        
        try:
            # Загружаем посты из таблицы messages
            # Используем text_content как текст поста
            # ВАЖНО: Используем параметризованные запросы для безопасности
            # Исправляем синтаксис INTERVAL для PostgreSQL
            query = """
                SELECT id, text_content, published_at
                FROM messages
                WHERE text_content IS NOT NULL 
                  AND text_content != ''
                  AND LENGTH(TRIM(text_content)) >= 10
                  AND published_at >= NOW() - ($1 || ' days')::INTERVAL
                ORDER BY published_at DESC
            """
            
            logger.debug(f"Выполнение SQL запроса: days_back={days_back}, limit={limit}")
            if limit:
                query += " LIMIT $2"
                rows = await conn.fetch(query, str(days_back), limit)
            else:
                rows = await conn.fetch(query, str(days_back))
            
            logger.info(f"📊 Получено {len(rows)} строк из базы данных")
            
            posts = []
            skipped = 0
            for row in rows:
                text = row['text_content']
                # Валидация: пропускаем слишком короткие или слишком длинные тексты
                if not text or len(text.strip()) < 10:
                    skipped += 1
                    continue
                # Обрезаем очень длинные тексты (для экономии памяти)
                if len(text) > 10000:
                    text = text[:10000] + "..."
                
                posts.append({
                    "post_id": row['id'],
                    "text": text.strip(),
                    "timestamp": row['published_at']
                })
            
            if skipped > 0:
                logger.info(f"⚠️ Пропущено {skipped} постов (слишком короткие)")
            
            logger.info(f"✅ Загружено {len(posts)} валидных постов из PostgreSQL")
            return posts
            
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке постов из PostgreSQL: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
        finally:
            await conn.close()
            logger.debug("🔌 Подключение к PostgreSQL закрыто")


# ============================================================================
# ШАГ 5: ГЕНЕРАЦИЯ ЗАГОЛОВКОВ ЧЕРЕЗ OPENAI GPT
# ============================================================================
# OpenAI генератор находится в pro_mode/openai_title_generator.py
# ============================================================================


# ============================================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================================

async def example_usage():
    """
    Пример использования TopicModelingService
    
    Этот пример показывает, как использовать сервис для:
    1. Индексации новых постов
    2. Построения тематической модели
    3. Сохранения результатов
    """
    # Инициализация сервиса
    service = TopicModelingService()
    
    # Вариант 1: Полный пайплайн (рекомендуется)
    # Автоматически загружает посты из БД, индексирует, строит модель и сохраняет
    result = await service.run_full_pipeline(fetch_from_db=True)
    print(f"Результат: {result}")
    
    # Вариант 2: Пошаговое выполнение
    # 1. Индексация новых постов
    new_posts = [
        {
            "post_id": 1,
            "text": "Пример текста поста",
            "timestamp": datetime.now()
        }
    ]
    await service.upsert_to_search_index(new_posts)
    await service.upsert_to_clustering_index(new_posts)
    
    # 2. Построение модели
    bertopic_model = await service.build_topic_model()
    
    # 3. Получение информации о темах
    topic_info = service.get_topic_info()
    print(f"Найдено тем: {len(topic_info['topic_sizes'])}")
    
    # 4. Сохранение в БД
    save_stats = await service.save_topics_to_db()
    print(f"Создано кластеров: {save_stats['clusters_created']}")


if __name__ == "__main__":
    # Запуск примера
    asyncio.run(example_usage())
