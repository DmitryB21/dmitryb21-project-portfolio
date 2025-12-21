"""
Скрипт для автоматизации запуска экспериментов с разными конфигурациями.

Использование:
    python scripts/run_experiments.py --queries queries.txt --output results.json
    python scripts/run_experiments.py --query "Какой SLA у сервиса платежей?" --configs all
"""

import argparse
import json
import os
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage.experiment_repository import ExperimentRepository, ExperimentConfig
from app.agent.agent import AgentController
from app.retrieval.retriever import Retriever
from app.retrieval.metadata_filter import MetadataFilter
from app.reranking.reranker import Reranker
from app.generation.prompt_builder import PromptBuilder
from app.generation.gigachat_client import LLMClient
from app.evaluation.metrics import MetricsCollector
from app.evaluation.ragas_evaluator import RAGASEvaluator
from app.ingestion.embedding_service import EmbeddingService
from qdrant_client import QdrantClient
from unittest.mock import MagicMock


def create_agent_controller_for_experiment(
    chunk_size: int,
    k: int,
    use_reranking: bool,
    embedding_dim: int = 1536
) -> AgentController:
    """
    Создаёт AgentController с заданной конфигурацией для эксперимента.
    
    Args:
        chunk_size: Размер чанков (не используется напрямую, но фиксируется в конфиге)
        k: Количество retrieved документов
        use_reranking: Использовать ли reranking
        embedding_dim: Размерность векторов
    
    Returns:
        AgentController с заданной конфигурацией
    """
    # Инициализация зависимостей (используем моки для тестов)
    # В production здесь будут реальные сервисы
    qdrant_client = MagicMock()
    embedding_service = MagicMock()
    embedding_service.get_embedding.return_value = [0.0] * embedding_dim
    
    retriever = Retriever(
        qdrant_client=qdrant_client,
        embedding_service=embedding_service,
        collection_name="neuro_docs"
    )
    
    metadata_filter = MetadataFilter()
    
    reranker = Reranker() if use_reranking else None
    
    prompt_builder = PromptBuilder()
    
    llm_client = LLMClient(
        api_key=os.getenv("GIGACHAT_API_KEY", ""),
        api_url=os.getenv("GIGACHAT_API_URL", "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"),
        mock_mode=True  # Для экспериментов используем mock mode
    )
    
    metrics_collector = MetricsCollector()
    ragas_evaluator = RAGASEvaluator(mock_mode=True)
    
    controller = AgentController(
        retriever=retriever,
        metadata_filter=metadata_filter,
        prompt_builder=prompt_builder,
        llm_client=llm_client,
        metrics_collector=metrics_collector,
        ragas_evaluator=ragas_evaluator,
        reranker=reranker
    )
    
    return controller


def get_experiment_configs(config_type: str = "all") -> List[Dict[str, Any]]:
    """
    Возвращает список конфигураций для экспериментов.
    
    Args:
        config_type: Тип конфигураций ("all", "chunk_size", "k", "reranking", "minimal")
    
    Returns:
        Список словарей с параметрами конфигураций
    """
    if config_type == "minimal":
        # Минимальный набор для быстрого тестирования
        return [
            {"chunk_size": 300, "k": 3, "use_reranking": False},
            {"chunk_size": 300, "k": 3, "use_reranking": True},
        ]
    
    elif config_type == "chunk_size":
        # Эксперименты с разными размерами чанков
        return [
            {"chunk_size": 200, "k": 3, "use_reranking": False},
            {"chunk_size": 300, "k": 3, "use_reranking": False},
            {"chunk_size": 400, "k": 3, "use_reranking": False},
        ]
    
    elif config_type == "k":
        # Эксперименты с разными значениями K
        return [
            {"chunk_size": 300, "k": 3, "use_reranking": False},
            {"chunk_size": 300, "k": 5, "use_reranking": False},
            {"chunk_size": 300, "k": 8, "use_reranking": False},
        ]
    
    elif config_type == "reranking":
        # Эксперименты с reranking
        return [
            {"chunk_size": 300, "k": 3, "use_reranking": False},
            {"chunk_size": 300, "k": 3, "use_reranking": True},
            {"chunk_size": 300, "k": 5, "use_reranking": False},
            {"chunk_size": 300, "k": 5, "use_reranking": True},
        ]
    
    else:  # "all"
        # Полный набор экспериментов
        configs = []
        
        # Разные chunk_size
        for chunk_size in [200, 300, 400]:
            for k in [3, 5, 8]:
                for use_reranking in [False, True]:
                    configs.append({
                        "chunk_size": chunk_size,
                        "k": k,
                        "use_reranking": use_reranking
                    })
        
        return configs


def run_experiment(
    query: str,
    config: Dict[str, Any],
    agent_controller: AgentController,
    experiment_repository: ExperimentRepository
) -> str:
    """
    Запускает один эксперимент с заданной конфигурацией.
    
    Args:
        query: Запрос для эксперимента
        config: Конфигурация эксперимента
        agent_controller: AgentController с нужной конфигурацией
        experiment_repository: Репозиторий для сохранения результатов
    
    Returns:
        ID сохранённого эксперимента
    """
    # Создаём конфигурацию эксперимента
    experiment_config = ExperimentConfig(
        chunk_size=config["chunk_size"],
        k=config["k"],
        use_reranking=config["use_reranking"],
        embedding_model=os.getenv("EMBEDDING_MODEL_VERSION", "GigaChat-Embeddings-V1"),
        embedding_dim=int(os.getenv("EMBEDDING_DIM", "1536"))
    )
    
    # Запускаем запрос через AgentController
    import time
    start_time = time.time()
    
    response = agent_controller.ask(
        query=query,
        k=config["k"],
        use_reranking=config["use_reranking"]
    )
    
    end_time = time.time()
    latency_ms = (end_time - start_time) * 1000
    
    # Извлекаем метрики из ответа
    metrics = response.metrics.copy()
    
    # Добавляем latency метрики
    metrics["latency_ms"] = latency_ms
    metrics["retrieval_latency_ms"] = metrics.get("retrieval_latency_ms", 0)
    metrics["generation_latency_ms"] = metrics.get("generation_latency_ms", 0)
    
    # Сохраняем эксперимент
    description = f"Query: {query[:50]}... | Config: chunk_size={config['chunk_size']}, k={config['k']}, reranking={config['use_reranking']}"
    experiment_id = experiment_repository.save_experiment(
        config=experiment_config,
        metrics=metrics,
        description=description
    )
    
    return experiment_id


def run_batch_experiments(
    queries: List[str],
    configs: List[Dict[str, Any]],
    output_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Запускает batch экспериментов с разными конфигурациями.
    
    Args:
        queries: Список запросов для экспериментов
        configs: Список конфигураций
        output_file: Путь к файлу для сохранения результатов (опционально)
    
    Returns:
        Словарь с результатами экспериментов
    """
    experiment_repository = ExperimentRepository(use_memory=True)
    experiment_ids = []
    
    print(f"🚀 Запуск batch экспериментов:")
    print(f"   - Запросов: {len(queries)}")
    print(f"   - Конфигураций: {len(configs)}")
    print(f"   - Всего экспериментов: {len(queries) * len(configs)}")
    print()
    
    total_experiments = len(queries) * len(configs)
    current_experiment = 0
    
    for query_idx, query in enumerate(queries, 1):
        print(f"📝 Запрос {query_idx}/{len(queries)}: {query[:60]}...")
        
        for config_idx, config in enumerate(configs, 1):
            current_experiment += 1
            print(f"   ⚙️  Конфигурация {config_idx}/{len(configs)}: "
                  f"chunk_size={config['chunk_size']}, k={config['k']}, "
                  f"reranking={config['use_reranking']} "
                  f"({current_experiment}/{total_experiments})")
            
            # Создаём AgentController с нужной конфигурацией
            agent_controller = create_agent_controller_for_experiment(
                chunk_size=config["chunk_size"],
                k=config["k"],
                use_reranking=config["use_reranking"]
            )
            
            # Запускаем эксперимент
            try:
                experiment_id = run_experiment(
                    query=query,
                    config=config,
                    agent_controller=agent_controller,
                    experiment_repository=experiment_repository
                )
                experiment_ids.append(experiment_id)
                print(f"      ✅ Эксперимент сохранён: {experiment_id[:8]}...")
            except Exception as e:
                print(f"      ❌ Ошибка: {e}")
        
        print()
    
    # Получаем все эксперименты
    all_experiments = experiment_repository.list_experiments()
    
    # Формируем результаты
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_experiments": len(experiment_ids),
        "queries": queries,
        "configs": configs,
        "experiments": [
            {
                "id": exp.id,
                "config": {
                    "chunk_size": exp.config.chunk_size,
                    "k": exp.config.k,
                    "use_reranking": exp.config.use_reranking,
                    "embedding_model": exp.config.embedding_model,
                    "embedding_dim": exp.config.embedding_dim
                },
                "metrics": exp.metrics,
                "timestamp": exp.timestamp.isoformat(),
                "description": exp.description
            }
            for exp in all_experiments
        ]
    }
    
    # Сохраняем результаты в файл, если указан
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"💾 Результаты сохранены в: {output_file}")
    
    return results


def main():
    """Главная функция для запуска скрипта"""
    parser = argparse.ArgumentParser(
        description="Запуск batch экспериментов с разными конфигурациями"
    )
    
    parser.add_argument(
        "--query",
        type=str,
        help="Один запрос для экспериментов"
    )
    
    parser.add_argument(
        "--queries",
        type=str,
        help="Путь к файлу с запросами (по одному на строку)"
    )
    
    parser.add_argument(
        "--configs",
        type=str,
        default="minimal",
        choices=["all", "minimal", "chunk_size", "k", "reranking"],
        help="Тип конфигураций для экспериментов (default: minimal)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="experiment_results.json",
        help="Путь к файлу для сохранения результатов (default: experiment_results.json)"
    )
    
    args = parser.parse_args()
    
    # Получаем запросы
    queries = []
    if args.query:
        queries = [args.query]
    elif args.queries:
        if not os.path.exists(args.queries):
            print(f"❌ Файл не найден: {args.queries}")
            sys.exit(1)
        with open(args.queries, 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip()]
    else:
        # Запросы по умолчанию
        queries = [
            "Какой SLA у сервиса платежей?",
            "Какие документы нужны для оформления отпуска?",
            "Как настроить VPN для удалённой работы?",
        ]
        print("ℹ️  Используются запросы по умолчанию")
    
    if not queries:
        print("❌ Нет запросов для экспериментов")
        sys.exit(1)
    
    # Получаем конфигурации
    configs = get_experiment_configs(args.configs)
    
    # Запускаем batch экспериментов
    results = run_batch_experiments(
        queries=queries,
        configs=configs,
        output_file=args.output
    )
    
    # Выводим краткую статистику
    print("\n" + "="*60)
    print("📊 СТАТИСТИКА ЭКСПЕРИМЕНТОВ")
    print("="*60)
    print(f"Всего экспериментов: {results['total_experiments']}")
    print(f"Уникальных конфигураций: {len(configs)}")
    print(f"Запросов: {len(queries)}")
    print()
    
    # Показываем лучшие результаты по метрикам
    if results['experiments']:
        print("🏆 Лучшие результаты по метрикам:")
        for metric_name in ["precision_at_3", "faithfulness", "answer_relevancy"]:
            best_exp = max(
                results['experiments'],
                key=lambda x: x['metrics'].get(metric_name, 0),
                default=None
            )
            if best_exp and metric_name in best_exp['metrics']:
                print(f"   {metric_name}: {best_exp['metrics'][metric_name]:.3f} "
                      f"(chunk_size={best_exp['config']['chunk_size']}, "
                      f"k={best_exp['config']['k']}, "
                      f"reranking={best_exp['config']['use_reranking']})")
    
    print("\n✅ Готово!")


if __name__ == "__main__":
    main()

