"""
@file: agent.py
@description: AgentController - основной orchestrator для всех модулей
@dependencies: app.agent.state_machine, app.agent.decision_log, app.retrieval.*, app.generation.*, app.evaluation.*
@created: 2024-12-19
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import time
from app.agent.state_machine import AgentStateMachine, AgentState
from app.agent.decision_log import DecisionLog
from app.agent.query_validator import QueryValidator, QueryValidationResult
from app.retrieval.retriever import Retriever, RetrievedChunk
from app.retrieval.metadata_filter import MetadataFilter
from app.reranking.reranker import Reranker, RerankedChunk
from app.generation.prompt_builder import PromptBuilder
from app.generation.gigachat_client import LLMClient
from app.evaluation.metrics import MetricsCollector
from app.evaluation.ragas_evaluator import RAGASEvaluator
from app.monitoring.prometheus_metrics import PrometheusMetrics
from app.storage.experiment_repository import ExperimentRepository, ExperimentConfig


@dataclass
class Source:
    """
    Представление источника (чанка) в ответе агента.
    
    Attributes:
        text: Текст чанка
        id: Идентификатор чанка
        metadata: Метаданные (document_id, category, file_path)
    """
    text: str
    id: str
    metadata: Dict[str, Any]


@dataclass
class AgentResponse:
    """
    Ответ агента на запрос пользователя.
    
    Attributes:
        answer: Текст ответа
        sources: Список источников (чанков)
        metrics: Метрики качества (precision_at_3, faithfulness, answer_relevancy)
    """
    answer: str
    sources: List[Source]
    metrics: Dict[str, float]


class AgentController:
    """
    Основной контроллер агента.
    
    Отвечает за:
    - Оркестрацию всех модулей (Retrieval, Generation, Evaluation)
    - Управление state machine
    - Формирование AgentResponse
    - Трассировку решений через DecisionLog
    """
    
    def __init__(
        self,
        retriever: Retriever,
        metadata_filter: MetadataFilter,
        prompt_builder: PromptBuilder,
        llm_client: LLMClient,
        metrics_collector: MetricsCollector,
        ragas_evaluator: RAGASEvaluator,
        reranker: Optional[Reranker] = None,
        prometheus_metrics: Optional[PrometheusMetrics] = None,
        experiment_repository: Optional[ExperimentRepository] = None
    ):
        """
        Инициализация AgentController.
        
        Args:
            retriever: Retriever для semantic search
            metadata_filter: MetadataFilter для фильтрации чанков
            prompt_builder: PromptBuilder для формирования prompt
            llm_client: LLMClient для генерации ответов
            metrics_collector: MetricsCollector для расчёта метрик
            ragas_evaluator: RAGASEvaluator для оценки качества
            reranker: Reranker для переупорядочивания чанков (опционально)
            prometheus_metrics: PrometheusMetrics для мониторинга (опционально)
            experiment_repository: ExperimentRepository для сохранения экспериментов (опционально)
        """
        self.retriever = retriever
        self.metadata_filter = metadata_filter
        self.reranker = reranker
        self.prompt_builder = prompt_builder
        self.llm_client = llm_client
        self.metrics_collector = metrics_collector
        self.ragas_evaluator = ragas_evaluator
        self.prometheus_metrics = prometheus_metrics
        self.experiment_repository = experiment_repository
        
        self.state_machine = AgentStateMachine()
        self.decision_log = DecisionLog()
        self.query_validator = QueryValidator()
    
    def ask(
        self,
        query: str,
        k: int = 3,
        ground_truth_relevant: Optional[List[str]] = None,
        use_metadata_filter: bool = False,
        metadata_filter_kwargs: Optional[Dict[str, Any]] = None,
        use_reranking: bool = False,
        rerank_top_k: Optional[int] = None
    ) -> AgentResponse:
        """
        Обрабатывает запрос пользователя через полный pipeline.
        
        Args:
            query: Запрос пользователя
            k: Количество retrieved чанков (3, 5, 8)
            ground_truth_relevant: Список ID релевантных чанков для расчёта Precision@K (опционально)
            use_metadata_filter: Использовать ли фильтрацию по метаданным
            metadata_filter_kwargs: Параметры для MetadataFilter (source, category и др.)
            use_reranking: Использовать ли reranking для переупорядочивания чанков
            rerank_top_k: Количество чанков после reranking (если None, используется k)
            
        Returns:
            AgentResponse с answer, sources, metrics
        """
        # Начинаем измерение latency для Prometheus
        start_time = time.time()
        if self.prometheus_metrics:
            self.prometheus_metrics.increment_active_requests()
            self.prometheus_metrics.record_request()
        
        # Логируем начало обработки
        self.decision_log.log_decision(
            state=self.state_machine.current_state.value,
            action="receive_query",
            input_data=f"query: {query}",
            output_data=None,
            metadata={"k": k}
        )
        
        # Переход: IDLE → VALIDATE_QUERY
        self.state_machine.transition_to(AgentState.VALIDATE_QUERY)
        
        # Валидация запроса (UC-2: уточнение контекста)
        validation_result = self.query_validator.validate(query)
        
        if not validation_result.is_valid:
            # Невалидный запрос (пустой)
            self.state_machine.transition_to(AgentState.RETURN_RESPONSE)
            if self.prometheus_metrics:
                end_to_end_latency = time.time() - start_time
                self.prometheus_metrics.record_latency(end_to_end_latency)
                self.prometheus_metrics.decrement_active_requests()
            return AgentResponse(
                answer=validation_result.clarification_question or "Пожалуйста, уточните ваш вопрос.",
                sources=[],
                metrics={}
            )
        
        if validation_result.needs_clarification:
            # Требуется уточнение контекста (UC-2)
            self.state_machine.transition_to(AgentState.REQUEST_CLARIFICATION)
            self.decision_log.log_decision(
                state=self.state_machine.current_state.value,
                action="request_clarification",
                input_data=query,
                output_data=validation_result.clarification_question,
                metadata={"reason": validation_result.reason}
            )
            
            # Переход: REQUEST_CLARIFICATION → RETURN_RESPONSE
            self.state_machine.transition_to(AgentState.RETURN_RESPONSE)
            
            if self.prometheus_metrics:
                end_to_end_latency = time.time() - start_time
                self.prometheus_metrics.record_latency(end_to_end_latency)
                self.prometheus_metrics.decrement_active_requests()
            
            return AgentResponse(
                answer=validation_result.clarification_question,
                sources=[],
                metrics={"needs_clarification": True}
            )
        
        # Запрос валиден и не требует уточнения
        self.decision_log.log_decision(
            state=self.state_machine.current_state.value,
            action="validate_query",
            input_data=query,
            output_data="valid",
            metadata={}
        )
        
        # Переход: VALIDATE_QUERY → RETRIEVE
        self.state_machine.transition_to(AgentState.RETRIEVE)
        self.decision_log.log_decision(
            state=self.state_machine.current_state.value,
            action="retrieve_chunks",
            input_data=query,
            output_data=None,
            metadata={"k": k}
        )
        
        # Шаг 1: Retrieval
        retrieval_start = time.time()
        retrieved_chunks = self.retriever.retrieve(query, k=k)
        if self.prometheus_metrics:
            retrieval_latency = time.time() - retrieval_start
            self.prometheus_metrics.record_retrieval_latency(retrieval_latency)
        
        if not retrieved_chunks:
            # Если нет результатов, возвращаем ответ об отсутствии информации
            self.state_machine.transition_to(AgentState.RETURN_RESPONSE)
            return AgentResponse(
                answer="В документации не найдено информации для ответа на этот вопрос.",
                sources=[],
                metrics={}
            )
        
        self.decision_log.log_decision(
            state=self.state_machine.current_state.value,
            action="retrieve_chunks",
            input_data=query,
            output_data=f"{len(retrieved_chunks)} chunks retrieved",
            metadata={"k": k, "retrieved_count": len(retrieved_chunks)}
        )
        
        # Шаг 2: Metadata Filter (опционально)
        if use_metadata_filter and metadata_filter_kwargs:
            self.state_machine.transition_to(AgentState.METADATA_FILTER)
            filtered_chunks = self.metadata_filter.filter(retrieved_chunks, **metadata_filter_kwargs)
            retrieved_chunks = filtered_chunks
            self.decision_log.log_decision(
                state=self.state_machine.current_state.value,
                action="filter_chunks",
                input_data=f"{len(retrieved_chunks)} chunks",
                output_data=f"{len(filtered_chunks)} chunks after filter",
                metadata=metadata_filter_kwargs
            )
        
        # Шаг 3: Reranking (опционально)
        if use_reranking and self.reranker:
            rerank_k = rerank_top_k if rerank_top_k is not None else k
            reranked_chunks = self.reranker.rerank(query=query, chunks=retrieved_chunks, top_k=rerank_k)
            
            # Конвертируем RerankedChunk обратно в RetrievedChunk для совместимости
            retrieved_chunks = [
                RetrievedChunk(
                    id=chunk.id,
                    text=chunk.text,
                    score=chunk.rerank_score,  # Используем rerank_score как новый score
                    metadata=chunk.metadata
                )
                for chunk in reranked_chunks
            ]
            
            self.decision_log.log_decision(
                state=self.state_machine.current_state.value,
                action="rerank_chunks",
                input_data=f"{len(retrieved_chunks)} chunks before rerank",
                output_data=f"{len(reranked_chunks)} chunks after rerank",
                metadata={"rerank_top_k": rerank_k}
            )
        
        # Переход: RETRIEVE/METADATA_FILTER/RERANK → GENERATE
        self.state_machine.transition_to(AgentState.GENERATE)
        self.decision_log.log_decision(
            state=self.state_machine.current_state.value,
            action="build_prompt",
            input_data=f"{len(retrieved_chunks)} chunks",
            output_data="prompt built",
            metadata={}
        )
        
        # Шаг 4: Build prompt
        prompt = self.prompt_builder.build_prompt(query, retrieved_chunks)
        
        # Шаг 5: Generate answer
        generation_start = time.time()
        answer = self.llm_client.generate_answer(prompt)
        if self.prometheus_metrics:
            generation_latency = time.time() - generation_start
            self.prometheus_metrics.record_generation_latency(generation_latency)
        
        self.decision_log.log_decision(
            state=self.state_machine.current_state.value,
            action="generate_answer",
            input_data="prompt",
            output_data=f"answer: {answer[:50]}...",
            metadata={}
        )
        
        # Переход: GENERATE → VALIDATE_ANSWER
        self.state_machine.transition_to(AgentState.VALIDATE_ANSWER)
        
        # Шаг 6: Calculate metrics
        metrics = {}
        
        # Precision@K (если есть ground truth)
        if ground_truth_relevant:
            precision = self.metrics_collector.calculate_precision_at_k(
                retrieved_chunks=retrieved_chunks,
                ground_truth_relevant=ground_truth_relevant,
                k=k
            )
            metrics["precision_at_3"] = precision
        
        # RAGAS метрики
        contexts = [chunk.text for chunk in retrieved_chunks]
        ragas_metrics = self.ragas_evaluator.evaluate_all(
            question=query,
            answer=answer,
            contexts=contexts,
            ground_truth=None
        )
        metrics.update(ragas_metrics)
        
        self.decision_log.log_decision(
            state=self.state_machine.current_state.value,
            action="calculate_metrics",
            input_data="answer + chunks",
            output_data=f"metrics: {metrics}",
            metadata={}
        )
        
        # Переход: VALIDATE_ANSWER → LOG_METRICS
        self.state_machine.transition_to(AgentState.LOG_METRICS)
        self.decision_log.log_decision(
            state=self.state_machine.current_state.value,
            action="log_metrics",
            input_data=metrics,
            output_data="logged",
            metadata={}
        )
        
        # Переход: LOG_METRICS → RETURN_RESPONSE
        self.state_machine.transition_to(AgentState.RETURN_RESPONSE)
        
        # Сохранение эксперимента (если experiment_repository настроен)
        if self.experiment_repository:
            end_to_end_latency = time.time() - start_time
            
            # Добавляем latency метрики
            experiment_metrics = metrics.copy()
            experiment_metrics["latency_ms"] = end_to_end_latency * 1000
            if self.prometheus_metrics:
                # Получаем retrieval и generation latency из Prometheus (если доступно)
                # Для упрощения используем общий latency
                pass
            
            # Создаём конфигурацию эксперимента
            # Примечание: chunk_size и embedding_model берутся из конфигурации системы
            # Для текущей реализации используем значения по умолчанию
            experiment_config = ExperimentConfig(
                chunk_size=300,  # TODO: Получать из конфигурации Chunker
                k=k,
                use_reranking=use_reranking,
                embedding_model="GigaChat-Embeddings-V1",  # TODO: Получать из EmbeddingService
                embedding_dim=1536  # TODO: Получать из конфигурации
            )
            
            self.experiment_repository.save_experiment(
                config=experiment_config,
                metrics=experiment_metrics,
                description=f"Experiment: query='{query[:50]}...', k={k}, reranking={use_reranking}"
            )
        
        # Формируем источники
        sources = [
            Source(
                text=chunk.text,
                id=chunk.id,
                metadata=chunk.metadata
            )
            for chunk in retrieved_chunks
        ]
        
        # Переход: RETURN_RESPONSE → IDLE
        self.state_machine.transition_to(AgentState.IDLE)
        
        # Записываем end-to-end latency для Prometheus
        if self.prometheus_metrics:
            end_to_end_latency = time.time() - start_time
            self.prometheus_metrics.record_latency(end_to_end_latency)
            self.prometheus_metrics.decrement_active_requests()
        
        return AgentResponse(
            answer=answer,
            sources=sources,
            metrics=metrics
        )

