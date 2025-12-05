"""
Сервис для экспорта результатов тематического моделирования
"""
import logging

logger = logging.getLogger(__name__)


class ExportService:
    """Сервис для экспорта результатов тематического моделирования"""
    
    # Старые методы export_clustering_results и export_classification_results удалены
    # - используется только тематическое моделирование через topic_modeling_service


# Создаем глобальный экземпляр сервиса
export_service = ExportService()
