"""
Сервис для работы с ChatGPT API

Given: Сервис инициализирован с API ключом
When: Выполняются запросы к ChatGPT API
Then: Возвращаются ответы от ChatGPT
"""

import os
import aiohttp
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения при импорте модуля
load_dotenv()


class ChatGPTService:
    """
    Сервис для работы с OpenAI ChatGPT API
    
    Инкапсулирует логику взаимодействия с ChatGPT API
    """
    
    def __init__(self):
        """Инициализация сервиса"""
        # Получаем ключ динамически при каждом обращении
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-3.5-turbo"  # Можно использовать gpt-4, если доступен
    
    def _get_api_key(self) -> Optional[str]:
        """Получение API ключа из переменных окружения"""
        return os.getenv("OPENAI_API_KEY")
    
    async def get_marketing_advice(self, problem_description: str) -> Optional[str]:
        """
        Получение совета по маркетингу от ChatGPT
        
        Given: Пользователь описал проблему по маркетингу
        When: Вызывается get_marketing_advice с описанием проблемы
        Then: Возвращается совет от ChatGPT
        
        Args:
            problem_description: Описание проблемы (например, "Как увеличить продажи?")
            
        Returns:
            Совет от ChatGPT или None в случае ошибки
        """
        api_key = self._get_api_key()
        if not api_key:
            return "❌ API ключ OpenAI не настроен. Обратитесь к администратору."
        
        prompt = (
            f"Ты опытный маркетолог. Пользователь задал вопрос: '{problem_description}'\n\n"
            "Дай краткий, практичный совет по маркетингу (максимум 200 слов). "
            "Ответ должен быть конкретным и полезным."
        )
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Ты опытный маркетолог, дающий практичные советы."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 300,
                    "temperature": 0.7
                }
                
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        advice = data["choices"][0]["message"]["content"].strip()
                        return advice
                    else:
                        error_text = await response.text()
                        return f"❌ Ошибка API: {response.status}. {error_text[:100]}"
        
        except Exception as e:
            return f"❌ Ошибка при обращении к ChatGPT: {str(e)}"
    
    async def get_motivation(self) -> Optional[str]:
        """
        Получение мотивационной фразы от ChatGPT
        
        Given: Пользователь запросил мотивацию
        When: Вызывается get_motivation
        Then: Возвращается мотивационная фраза от ChatGPT
        
        Returns:
            Мотивационная фраза или None в случае ошибки
        """
        api_key = self._get_api_key()
        if not api_key:
            return "❌ API ключ OpenAI не настроен. Обратитесь к администратору."
        
        prompt = (
            "Сгенерируй короткую мотивационную фразу для менеджера по продажам "
            "(максимум 50 слов). Фраза должна быть вдохновляющей и связанной с продажами и достижениями."
        )
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Ты мотивационный спикер, вдохновляющий менеджеров по продажам."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 100,
                    "temperature": 0.9
                }
                
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        motivation = data["choices"][0]["message"]["content"].strip()
                        return motivation
                    else:
                        error_text = await response.text()
                        return f"❌ Ошибка API: {response.status}. {error_text[:100]}"
        
        except Exception as e:
            return f"❌ Ошибка при обращении к ChatGPT: {str(e)}"


# Глобальный экземпляр сервиса
chatgpt_service = ChatGPTService()
