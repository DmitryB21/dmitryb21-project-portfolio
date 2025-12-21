"""
Тесты для ExperimentRepository - хранение и получение результатов экспериментов
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock
from app.storage.experiment_repository import ExperimentRepository, Experiment, ExperimentConfig


@pytest.fixture
def experiment_repository():
    """Фикстура для ExperimentRepository (in-memory для тестов)"""
    return ExperimentRepository(use_memory=True)


@pytest.fixture
def sample_experiment_config():
    """Фикстура с примерной конфигурацией эксперимента"""
    return ExperimentConfig(
        chunk_size=300,
        k=5,
        use_reranking=True,
        embedding_model="GigaChat-Embeddings-V1",
        embedding_dim=1536
    )


@pytest.fixture
def sample_metrics():
    """Фикстура с примерными метриками"""
    return {
        "precision_at_3": 0.85,
        "faithfulness": 0.88,
        "answer_relevancy": 0.82,
        "latency_ms": 1200,
        "retrieval_latency_ms": 180,
        "generation_latency_ms": 800
    }


class TestExperimentRepository:
    """Тесты для ExperimentRepository"""
    
    def test_save_experiment(self, experiment_repository, sample_experiment_config, sample_metrics):
        """Тест: сохранение эксперимента"""
        experiment_id = experiment_repository.save_experiment(
            config=sample_experiment_config,
            metrics=sample_metrics,
            description="Тест влияния chunk_size=300 на метрики"
        )
        
        assert experiment_id is not None
        assert isinstance(experiment_id, str)
    
    def test_get_experiment(self, experiment_repository, sample_experiment_config, sample_metrics):
        """Тест: получение эксперимента по ID"""
        experiment_id = experiment_repository.save_experiment(
            config=sample_experiment_config,
            metrics=sample_metrics,
            description="Тест эксперимента"
        )
        
        experiment = experiment_repository.get_experiment(experiment_id)
        
        assert experiment is not None
        assert experiment.id == experiment_id
        assert experiment.config.chunk_size == 300
        assert experiment.config.k == 5
        assert experiment.metrics["precision_at_3"] == 0.85
    
    def test_list_experiments(self, experiment_repository, sample_experiment_config, sample_metrics):
        """Тест: получение списка всех экспериментов"""
        # Сохраняем несколько экспериментов
        id1 = experiment_repository.save_experiment(
            config=sample_experiment_config,
            metrics=sample_metrics,
            description="Эксперимент 1"
        )
        
        id2 = experiment_repository.save_experiment(
            config=ExperimentConfig(chunk_size=200, k=3, use_reranking=False),
            metrics={"precision_at_3": 0.75},
            description="Эксперимент 2"
        )
        
        experiments = experiment_repository.list_experiments()
        
        assert len(experiments) >= 2
        experiment_ids = [exp.id for exp in experiments]
        assert id1 in experiment_ids
        assert id2 in experiment_ids
    
    def test_compare_experiments(self, experiment_repository, sample_experiment_config, sample_metrics):
        """Тест: сравнение экспериментов по метрикам"""
        # Эксперимент 1: chunk_size=300, k=5, с reranking
        id1 = experiment_repository.save_experiment(
            config=sample_experiment_config,
            metrics=sample_metrics,
            description="С reranking"
        )
        
        # Эксперимент 2: chunk_size=200, k=3, без reranking
        id2 = experiment_repository.save_experiment(
            config=ExperimentConfig(chunk_size=200, k=3, use_reranking=False),
            metrics={"precision_at_3": 0.75, "latency_ms": 1000},
            description="Без reranking"
        )
        
        comparison = experiment_repository.compare_experiments([id1, id2])
        
        assert "experiments" in comparison
        assert len(comparison["experiments"]) == 2
        assert "metrics_comparison" in comparison
        assert "precision_at_3" in comparison["metrics_comparison"]
    
    def test_get_experiments_by_config(self, experiment_repository, sample_experiment_config, sample_metrics):
        """Тест: получение экспериментов по конфигурации"""
        # Сохраняем эксперименты с разными конфигурациями
        experiment_repository.save_experiment(
            config=sample_experiment_config,
            metrics=sample_metrics,
            description="Эксперимент 1"
        )
        
        experiment_repository.save_experiment(
            config=ExperimentConfig(chunk_size=200, k=3, use_reranking=False),
            metrics={"precision_at_3": 0.75},
            description="Эксперимент 2"
        )
        
        # Ищем эксперименты с chunk_size=300
        experiments = experiment_repository.get_experiments_by_config(
            chunk_size=300
        )
        
        assert len(experiments) >= 1
        assert all(exp.config.chunk_size == 300 for exp in experiments)
    
    def test_experiment_timestamp(self, experiment_repository, sample_experiment_config, sample_metrics):
        """Тест: проверка timestamp при сохранении эксперимента"""
        before = datetime.now()
        experiment_id = experiment_repository.save_experiment(
            config=sample_experiment_config,
            metrics=sample_metrics,
            description="Тест timestamp"
        )
        after = datetime.now()
        
        experiment = experiment_repository.get_experiment(experiment_id)
        
        assert experiment.timestamp >= before
        assert experiment.timestamp <= after
    
    def test_experiment_config_preservation(self, experiment_repository, sample_experiment_config, sample_metrics):
        """Тест: сохранение всех параметров конфигурации"""
        experiment_id = experiment_repository.save_experiment(
            config=sample_experiment_config,
            metrics=sample_metrics,
            description="Тест конфигурации"
        )
        
        experiment = experiment_repository.get_experiment(experiment_id)
        
        assert experiment.config.chunk_size == sample_experiment_config.chunk_size
        assert experiment.config.k == sample_experiment_config.k
        assert experiment.config.use_reranking == sample_experiment_config.use_reranking
        assert experiment.config.embedding_model == sample_experiment_config.embedding_model
        assert experiment.config.embedding_dim == sample_experiment_config.embedding_dim
    
    def test_experiment_metrics_preservation(self, experiment_repository, sample_experiment_config, sample_metrics):
        """Тест: сохранение всех метрик"""
        experiment_id = experiment_repository.save_experiment(
            config=sample_experiment_config,
            metrics=sample_metrics,
            description="Тест метрик"
        )
        
        experiment = experiment_repository.get_experiment(experiment_id)
        
        assert experiment.metrics == sample_metrics
        assert experiment.metrics["precision_at_3"] == 0.85
        assert experiment.metrics["faithfulness"] == 0.88
        assert experiment.metrics["latency_ms"] == 1200
    
    def test_get_nonexistent_experiment(self, experiment_repository):
        """Тест: получение несуществующего эксперимента"""
        experiment = experiment_repository.get_experiment("nonexistent_id")
        
        assert experiment is None
    
    def test_experiment_description(self, experiment_repository, sample_experiment_config, sample_metrics):
        """Тест: сохранение описания эксперимента"""
        description = "Тест влияния chunk_size на Precision@3"
        experiment_id = experiment_repository.save_experiment(
            config=sample_experiment_config,
            metrics=sample_metrics,
            description=description
        )
        
        experiment = experiment_repository.get_experiment(experiment_id)
        
        assert experiment.description == description
    
    def test_list_experiments_empty(self, experiment_repository):
        """Тест: получение списка экспериментов при пустом хранилище"""
        experiments = experiment_repository.list_experiments()
        
        assert experiments == []
    
    def test_compare_single_experiment(self, experiment_repository, sample_experiment_config, sample_metrics):
        """Тест: сравнение одного эксперимента"""
        experiment_id = experiment_repository.save_experiment(
            config=sample_experiment_config,
            metrics=sample_metrics,
            description="Один эксперимент"
        )
        
        comparison = experiment_repository.compare_experiments([experiment_id])
        
        assert len(comparison["experiments"]) == 1
        assert comparison["experiments"][0].id == experiment_id

