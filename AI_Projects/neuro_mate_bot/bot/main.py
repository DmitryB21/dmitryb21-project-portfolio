"""
Главный файл для запуска бота

Given: Установлены все зависимости и настроен .env файл
When: Запускается main.py
Then: Бот подключается к Telegram API и начинает обработку сообщений
"""

import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Импорт роутеров
from bot.handlers import start, tasks, report, errors, deals, extras

# Загрузка переменных окружения
load_dotenv()

# Получение токена из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не найден в переменных окружения. Проверьте файл .env")


async def main():
    """
    Основная функция для запуска бота
    
    Given: Бот инициализирован
    When: Функция main() вызывается
    Then: Бот начинает polling и обрабатывает сообщения
    """
    # Инициализация бота и диспетчера
    bot = Bot(token=TELEGRAM_TOKEN)
    
    # Используем MemoryStorage для FSM (в памяти)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация роутеров (порядок важен!)
    dp.include_router(start.router)
    dp.include_router(tasks.router)
    dp.include_router(deals.router)
    dp.include_router(report.router)
    dp.include_router(extras.router)
    # Обработчик ошибок должен быть последним
    dp.include_router(errors.router)
    
    # Запуск polling
    print("🤖 Бот запущен...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        print("👋 Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())

