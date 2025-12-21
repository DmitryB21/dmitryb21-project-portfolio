"""
@file: experiment_repository.py
@description: ExperimentRepository - хранение и получение результатов экспериментов
@dependencies: datetime, typing
@created: 2024-12-19
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict
import uuid


@dataclass
class ExperimentConfig:
    """
    Конфигурация эксперимента.
    
    Attributes:
        chunk_size: Размер чанков (200, 300, 400 токенов)
        k: Количество retrieved документов (3, 5, 8)
        use_reranking: Использовать ли reranking
        embedding_model: Версия модели embeddings
        embedding_dim: Размерность векторов
    """
    chunk_size: int
    k: int
    use_reranking: bool = False
    embedding_model: str = "GigaChat-Embeddings-V1"
    embedding_dim: int = 1536


@dataclass
class Experiment:
    """
    Результат эксперимента.
    
    Attributes:
        id: Уникальный идентификатор эксперимента
        config: Конфигурация эксперимента
        metrics: Метрики качества (precision_at_3, faithfulness, latency и др.)
        timestamp: Время создания эксперимента
        description: Описание эксперимента
    """
    id: str
    config: ExperimentConfig
    metrics: Dict[str, float]
    timestamp: datetime
    description: Optional[str] = None


class ExperimentRepository:
    """
    Репозиторий для хранения и получения результатов экспериментов.
    
    Отвечает за:
    - Сохранение конфигураций и метрик экспериментов
    - Получение экспериментов по ID или конфигурации
    - Сравнение экспериментов по метрикам
    - Поддержка in-memory хранилища для тестов и PostgreSQL для production
    """
    
    def __init__(self, use_memory: bool = True, db_url: Optional[str] = None):
        """
        Инициализация ExperimentRepository.
        
        Args:
            use_memory: Если True, используется in-memory хранилище (для тестов)
            db_url: URL PostgreSQL (если use_memory=False)
        """
        self.use_memory = use_memory
        self.db_url = db_url
        
        if use_memory:
            # In-memory хранилище для тестов
            self._experiments: Dict[str, Experiment] = {}
        else:
            # В production здесь будет инициализация PostgreSQL
            # Для текущей реализации используем in-memory
            self._experiments: Dict[str, Experiment] = {}
            if db_url:
                # TODO: Инициализация PostgreSQL connection
                pass
    
    def save_experiment(
        self,
        config: ExperimentConfig,
        metrics: Dict[str, float],
        description: Optional[str] = None
    ) -> str:
        """
        Сохраняет результат эксперимента.
        
        Args:
            config: Конфигурация эксперимента
            metrics: Метрики качества
            description: Описание эксперимента
        
        Returns:
            ID сохранённого эксперимента
        """
        experiment_id = str(uuid.uuid4())
        
        experiment = Experiment(
            id=experiment_id,
            config=config,
            metrics=metrics,
            timestamp=datetime.now(),
            description=description
        )
        
        self._experiments[experiment_id] = experiment
        
        return experiment_id
    
    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """
        Получает эксперимент по ID.
        
        Args:
            experiment_id: ID эксперимента
        
        Returns:
            Experiment или None, если не найден
        """
        return self._experiments.get(experiment_id)
    
    def list_experiments(self, limit: Optional[int] = None) -> List[Experiment]:
        """
        Получает список всех экспериментов.
        
        Args:
            limit: Максимальное количество экспериментов (если None, возвращаются все)
        
        Returns:
            Список экспериментов, отсортированных по timestamp (новые первыми)
        """
        experiments = list(self._experiments.values())
        experiments.sort(key=lambda x: x.timestamp, reverse=True)
        
        if limit:
            experiments = experiments[:limit]
        
        return experiments
    
    def get_experiments_by_config(
        self,
        chunk_size: Optional[int] = None,
        k: Optional[int] = None,
        use_reranking: Optional[bool] = None
    ) -> List[Experiment]:
        """
        Получает эксперименты по параметрам конфигурации.
        
        Args:
            chunk_size: Фильтр по размеру чанков
            k: Фильтр по количеству retrieved документов
            use_reranking: Фильтр по использованию reranking
        
        Returns:
            Список экспериментов, соответствующих критериям
        """
        experiments = list(self._experiments.values())
        
        filtered = []
        for exp in experiments:
            if chunk_size is not None and exp.config.chunk_size != chunk_size:
                continue
            if k is not None and exp.config.k != k:
                continue
            if use_reranking is not None and exp.config.use_reranking != use_reranking:
                continue
            filtered.append(exp)
        
        filtered.sort(key=lambda x: x.timestamp, reverse=True)
        return filtered
    
    def compare_experiments(self, experiment_ids: List[str]) -> Dict[str, Any]:
        """
        Сравнивает эксперименты по метрикам.
        
        Args:
            experiment_ids: Список ID экспериментов для сравнения
        
        Returns:
            Словарь с экспериментами и сравнением метрик
        """
        experiments = [self.get_experiment(eid) for eid in experiment_ids]
        experiments = [e for e in experiments if e is not None]
        
        if not experiments:
            return {"experiments": [], "metrics_comparison": {}}
        
        # Собираем все уникальные метрики
        all_metrics = set()
        for exp in experiments:
            all_metrics.update(exp.metrics.keys())
        
        # Сравнение метрик
        metrics_comparison = {}
        for metric_name in all_metrics:
            values = [exp.metrics.get(metric_name) for exp in experiments if metric_name in exp.metrics]
            if values:
                metrics_comparison[metric_name] = {
                    "values": values,
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values)
                }
        
        return {
            "experiments": experiments,
            "metrics_comparison": metrics_comparison
        }

