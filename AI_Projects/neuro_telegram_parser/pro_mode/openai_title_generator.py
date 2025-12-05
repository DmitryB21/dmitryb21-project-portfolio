"""
Генератор заголовков тем через OpenAI GPT API
"""
import logging
import asyncio
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai библиотека не установлена. Установите: pip install openai")


class OpenAITitleGenerator:
    """
    Генератор заголовков тем через OpenAI GPT API
    
    Использует OpenAI API для генерации заголовков тем на основе ключевых слов и примеров текстов.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.3,
        max_tokens: int = 50,
        timeout: float = 30.0
    ):
        """
        Инициализация генератора
        
        Args:
            api_key: OpenAI API ключ (если None, берется из OPENAI_API_KEY env)
            model: Название модели OpenAI (gpt-3.5-turbo, gpt-4, etc.)
            temperature: Температура генерации (0.3 для детерминированности)
            max_tokens: Максимальное количество токенов в ответе
            timeout: Таймаут запроса в секундах
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "openai библиотека не установлена. "
                "Установите: pip install openai"
            )
        
        # Получаем API ключ
        if api_key is None:
            api_key = os.getenv('OPENAI_API_KEY', '').strip()
        
        if not api_key:
            raise ValueError(
                "OpenAI API ключ не указан. "
                "Установите OPENAI_API_KEY в переменных окружения или передайте api_key"
            )
        
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        # Инициализируем клиент OpenAI
        self.client = AsyncOpenAI(api_key=self.api_key, timeout=self.timeout)
        
        logger.info(f"🔧 Инициализация OpenAI TitleGenerator: модель {model}")
    
    def _get_prompt(self, keywords: List[str], sample_texts: List[str]) -> str:
        """
        Формирует промпт для OpenAI GPT
        
        Args:
            keywords: Список ключевых слов темы
            sample_texts: Примеры текстов из темы
        
        Returns:
            Промпт для генерации заголовка
        """
        examples = sample_texts[:3]
        
        prompt = f"""Ты — помощник для генерации кратких информативных заголовков новостных событий на русском языке.

На основе ключевых слов и примеров сообщений создай краткий заголовок (до 10 слов):
Ключевые слова: {", ".join(keywords[:10])}
Примеры сообщений:
- {examples[0] if len(examples) > 0 else "Нет примеров"}
- {examples[1] if len(examples) > 1 else ""}
- {examples[2] if len(examples) > 2 else ""}

Требования к заголовку:
- Краткий и информативный (до 10 слов)
- На русском языке
- Без эмодзи и специальных символов
- Используй ключевые имена, места и события

Заголовок:"""
        
        return prompt
    
    async def generate_title(
        self,
        topic_id: int,
        keywords: List[str],
        sample_texts: List[str],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Генерация заголовка темы на основе ключевых слов и примеров сообщений
        
        Args:
            topic_id: ID темы (для логирования)
            keywords: Список ключевых слов темы
            sample_texts: Примеры сообщений из темы (минимум 3)
            temperature: Температура генерации (если None, используется self.temperature)
            max_tokens: Максимальное количество токенов (если None, используется self.max_tokens)
        
        Returns:
            Сгенерированный заголовок (очищенный от кавычек, переносов)
        """
        logger.info(f"   🔄 generate_title вызван для темы {topic_id}")
        logger.info(f"   📊 Параметры: keywords={len(keywords)}, sample_texts={len(sample_texts)}, max_tokens={max_tokens or self.max_tokens}")
        
        try:
            # Берем первые 3 примера (или меньше, если доступно меньше)
            examples = sample_texts[:3]
            logger.info(f"   📝 Используется {len(examples)} примеров текстов")
            
            # Формируем промпт
            prompt = self._get_prompt(keywords, sample_texts)
            logger.info(f"   📝 Промпт для темы {topic_id} подготовлен ({len(prompt)} символов)")
            
            # Параметры генерации
            gen_temperature = temperature if temperature is not None else self.temperature
            gen_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
            
            logger.info(f"   🚀 Начало генерации заголовка для темы {topic_id} через OpenAI {self.model}...")
            gen_start = asyncio.get_event_loop().time()
            
            # Генерируем ответ через OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты — помощник для генерации кратких информативных заголовков новостных событий на русском языке."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=gen_temperature,
                max_tokens=gen_max_tokens,
                timeout=self.timeout
            )
            
            gen_duration = asyncio.get_event_loop().time() - gen_start
            logger.info(f"   ⏱️ Генерация завершена за {gen_duration:.1f}с")
            
            # Извлекаем текст ответа
            if response.choices and len(response.choices) > 0:
                title = response.choices[0].message.content.strip()
            else:
                raise ValueError("Пустой ответ от OpenAI API")
            
            # Очистка от лишних символов
            title = title.replace("\n", " ").replace("\r", " ")
            title = title.replace('"', '').replace("'", "")
            
            # Удаляем кавычки в начале и конце, если есть
            if title.startswith('"') and title.endswith('"'):
                title = title[1:-1]
            if title.startswith("'") and title.endswith("'"):
                title = title[1:-1]
            
            # Обрезаем до 100 символов
            title = title[:100].strip()
            
            # Если заголовок пустой или слишком короткий, используем ключевые слова
            if not title or len(title) < 5:
                logger.warning(f"   ⚠️ Заголовок слишком короткий, используем ключевые слова")
                if keywords:
                    if len(keywords) >= 3:
                        title = f"{keywords[0]}, {keywords[1]} и {keywords[2]}"
                    elif len(keywords) == 2:
                        title = f"{keywords[0]} и {keywords[1]}"
                    else:
                        title = keywords[0] if keywords else "Тема"
                else:
                    title = f"Тема {topic_id}"
            
            logger.info(f"   ✅ Заголовок сгенерирован через OpenAI: {title[:50]}...")
            return title
            
        except asyncio.TimeoutError:
            logger.error(f"   ❌ Таймаут генерации заголовка для темы {topic_id} (>{self.timeout} сек)")
            # Fallback на ключевые слова
            if keywords:
                if len(keywords) >= 3:
                    return f"{keywords[0]}, {keywords[1]} и {keywords[2]}"
                elif len(keywords) == 2:
                    return f"{keywords[0]} и {keywords[1]}"
                else:
                    return keywords[0] if keywords else f"Тема {topic_id}"
            return f"Тема {topic_id}"
        except Exception as e:
            logger.error(f"   ❌ Ошибка генерации заголовка для темы {topic_id}: {e}")
            # Fallback на ключевые слова
            if keywords:
                if len(keywords) >= 3:
                    return f"{keywords[0]}, {keywords[1]} и {keywords[2]}"
                elif len(keywords) == 2:
                    return f"{keywords[0]} и {keywords[1]}"
                else:
                    return keywords[0] if keywords else f"Тема {topic_id}"
            return f"Тема {topic_id}"
    
    def release_model(self):
        """Освобождение ресурсов (для совместимости с локальными LLM)"""
        # OpenAI API не требует освобождения ресурсов
        pass

