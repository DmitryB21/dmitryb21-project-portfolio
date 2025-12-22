"""
QueryAPI - REST API для запросов к агенту
"""

from typing import Optional, List
from datetime import datetime
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.agent.agent import AgentController, AgentResponse, Source


class QueryRequest(BaseModel):
    """Запрос к агенту"""
    query: str = Field(..., description="Вопрос пользователя", min_length=1)
    k: int = Field(default=3, ge=1, le=10, description="Количество retrieved документов")
    ground_truth_relevant: Optional[List[str]] = Field(
        default=None,
        description="Список ID релевантных чанков для расчёта Precision@K"
    )
    
    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Валидация query"""
        if not v or not v.strip():
            raise ValueError("Query не может быть пустым")
        return v.strip()


class SourceResponse(BaseModel):
    """Ответ с источником"""
    text: str
    id: str
    metadata: dict


class QueryResponse(BaseModel):
    """Ответ агента"""
    answer: str
    sources: List[SourceResponse]
    metrics: dict


def create_app(agent_controller: Optional[AgentController] = None) -> FastAPI:
    """
    Создание FastAPI приложения с QueryAPI
    
    Args:
        agent_controller: Экземпляр AgentController (для тестирования можно передать мок)
    
    Returns:
        FastAPI приложение
    """
    app = FastAPI(
        title="Neuro_Doc_Assistant API",
        description="REST API для работы с AI-агентом документации",
        version="1.0.0"
    )
    
    # Храним контроллер в состоянии приложения
    if agent_controller is None:
        # В production здесь будет инициализация реального контроллера
        # Для тестов передаём через параметр
        raise ValueError("agent_controller должен быть передан при создании приложения")
    
    app.state.agent_controller = agent_controller
    
    @app.post("/ask", response_model=QueryResponse, status_code=status.HTTP_200_OK)
    async def ask_question(request: QueryRequest) -> QueryResponse:
        """
        Обработка запроса пользователя
        
        Args:
            request: Запрос с вопросом и параметрами
        
        Returns:
            Ответ агента с источниками и метриками
        """
        try:
            # Получаем контроллер из состояния приложения
            controller: AgentController = app.state.agent_controller
            
            # Вызываем агента (метод ask не является async)
            response: AgentResponse = controller.ask(
                query=request.query,
                k=request.k,
                ground_truth_relevant=request.ground_truth_relevant
            )
            
            # Преобразуем ответ в формат API
            sources = [
                SourceResponse(
                    text=source.text,
                    id=source.id,
                    metadata=source.metadata
                )
                for source in response.sources
            ]
            
            return QueryResponse(
                answer=response.answer,
                sources=sources,
                metrics=response.metrics
            )
        
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            import traceback
            import logging
            error_traceback = traceback.format_exc()
            # Логируем полную ошибку для отладки
            logger = logging.getLogger(__name__)
            logger.error(f"ERROR in /ask endpoint: {str(e)}")
            logger.error(f"Traceback: {error_traceback}")
            # Также выводим в консоль для немедленного просмотра
            print(f"\n{'='*80}")
            print(f"ERROR in /ask endpoint: {str(e)}")
            print(f"{'='*80}")
            print(f"Traceback:\n{error_traceback}")
            print(f"{'='*80}\n")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при обработке запроса: {str(e)}"
            )
    
    @app.get("/health", status_code=status.HTTP_200_OK)
    async def health_check() -> dict:
        """
        Проверка здоровья сервиса
        
        Returns:
            Статус сервиса
        """
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "Neuro_Doc_Assistant API"
        }
    
    return app

