"""
Модуль для отслеживания статуса индексации
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class IndexingStatus(str, Enum):
    """Статус индексации"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IndexingProgressTracker:
    """Трекер прогресса индексации"""
    
    def __init__(self, status_file: Optional[Path] = None):
        """
        Инициализация трекера
        
        Args:
            status_file: Путь к файлу для сохранения статуса (если None, используется временный файл)
        """
        if status_file is None:
            # Используем временный файл в директории проекта
            project_root = Path(__file__).parent.parent.parent
            status_file = project_root / ".indexing_status.json"
        
        self.status_file = Path(status_file)
        # Создаём директорию, если не существует
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self._status: Dict[str, Any] = {
            "status": IndexingStatus.IDLE.value,
            "progress": 0.0,
            "current_step": "",
            "total_steps": 0,
            "current_step_number": 0,
            "message": "",
            "started_at": None,
            "completed_at": None,
            "error": None,
            "stats": {
                "documents_loaded": 0,
                "chunks_created": 0,
                "embeddings_generated": 0,
                "chunks_indexed": 0
            }
        }
        self._load_status()
    
    def _load_status(self):
        """Загрузка статуса из файла"""
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    loaded_status = json.load(f)
                    # Валидируем структуру статуса
                    if isinstance(loaded_status, dict):
                        # Проверяем наличие обязательных полей
                        required_fields = ["status", "progress", "current_step", "message"]
                        if all(field in loaded_status for field in required_fields):
                            self._status = loaded_status
                            # Убеждаемся, что stats существует
                            if "stats" not in self._status:
                                self._status["stats"] = {
                                    "documents_loaded": 0,
                                    "chunks_created": 0,
                                    "embeddings_generated": 0,
                                    "chunks_indexed": 0
                                }
                        else:
                            # Если структура неполная, используем дефолтный статус
                            print(f"Warning: Файл статуса имеет неполную структуру, используется дефолтный статус")
                    else:
                        # Если загруженные данные не словарь, используем дефолтный статус
                        print(f"Warning: Файл статуса имеет неправильный формат, используется дефолтный статус")
            except json.JSONDecodeError as e:
                # Если файл поврежден (невалидный JSON), используем дефолтный статус
                print(f"Warning: Файл статуса поврежден (невалидный JSON): {e}, используется дефолтный статус")
            except Exception as e:
                # Если не удалось загрузить, используем дефолтный статус
                print(f"Warning: Не удалось загрузить статус из файла: {e}, используется дефолтный статус")
    
    def _save_status(self):
        """Сохранение статуса в файл"""
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(self._status, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Не удалось сохранить статус индексации: {e}")
    
    def start(self, total_steps: int = 5):
        """Начало индексации"""
        self._status = {
            "status": IndexingStatus.RUNNING.value,
            "progress": 0.0,
            "current_step": "Инициализация",
            "total_steps": total_steps,
            "current_step_number": 0,
            "message": "Индексация начата",
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "error": None,
            "stats": {
                "documents_loaded": 0,
                "chunks_created": 0,
                "embeddings_generated": 0,
                "chunks_indexed": 0
            }
        }
        self._save_status()
    
    def update_step(self, step_number: int, step_name: str, message: str = "", progress: Optional[float] = None):
        """
        Обновление текущего шага
        
        Args:
            step_number: Номер шага (1-based)
            step_name: Название шага
            message: Сообщение о прогрессе
            progress: Прогресс в процентах (0-100), если None - вычисляется автоматически
        """
        self._status["current_step_number"] = step_number
        self._status["current_step"] = step_name
        self._status["message"] = message
        
        if progress is None:
            # Вычисляем прогресс автоматически
            if self._status["total_steps"] > 0:
                self._status["progress"] = (step_number / self._status["total_steps"]) * 100
        else:
            self._status["progress"] = progress
        
        self._save_status()
    
    def update_progress(self, progress: float, message: str = ""):
        """
        Обновление прогресса текущего шага
        
        Args:
            progress: Прогресс в процентах (0-100)
            message: Сообщение о прогрессе
        """
        self._status["progress"] = min(100.0, max(0.0, progress))
        if message:
            self._status["message"] = message
        self._save_status()
    
    def update_stats(self, **kwargs):
        """
        Обновление статистики
        
        Args:
            **kwargs: Статистика (documents_loaded, chunks_created, embeddings_generated, chunks_indexed)
        """
        self._status["stats"].update(kwargs)
        self._save_status()
    
    def complete(self, message: str = "Индексация завершена успешно"):
        """Завершение индексации"""
        self._status["status"] = IndexingStatus.COMPLETED.value
        self._status["progress"] = 100.0
        self._status["message"] = message
        self._status["completed_at"] = datetime.now().isoformat()
        self._save_status()
    
    def fail(self, error: str):
        """Ошибка при индексации"""
        self._status["status"] = IndexingStatus.FAILED.value
        self._status["message"] = f"Ошибка: {error}"
        self._status["error"] = error
        self._status["completed_at"] = datetime.now().isoformat()
        self._save_status()
    
    def reset(self):
        """Сброс статуса"""
        self._status = {
            "status": IndexingStatus.IDLE.value,
            "progress": 0.0,
            "current_step": "",
            "total_steps": 0,
            "current_step_number": 0,
            "message": "",
            "started_at": None,
            "completed_at": None,
            "error": None,
            "stats": {
                "documents_loaded": 0,
                "chunks_created": 0,
                "embeddings_generated": 0,
                "chunks_indexed": 0
            }
        }
        self._save_status()
    
    def get_status(self) -> Dict[str, Any]:
        """Получение текущего статуса"""
        self._load_status()  # Обновляем статус из файла
        return self._status.copy()


# Глобальный экземпляр трекера
_tracker: Optional[IndexingProgressTracker] = None


def get_tracker() -> IndexingProgressTracker:
    """Получение глобального экземпляра трекера"""
    global _tracker
    if _tracker is None:
        _tracker = IndexingProgressTracker()
    return _tracker

