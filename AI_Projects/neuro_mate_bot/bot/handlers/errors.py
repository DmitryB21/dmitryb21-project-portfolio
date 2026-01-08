"""
Обработчик неизвестных команд и ошибок

Given: Пользователь отправляет неизвестную команду или сообщение
When: Сообщение не обработано другими handlers
Then: Бот отправляет подсказку с доступными командами
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from bot.keyboards.reply import get_main_keyboard

router = Router(name="errors")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Обработка команды /help
    
    Given: Пользователь отправляет команду /help
    When: Команда обрабатывается
    Then: Бот отправляет справку с доступными командами
    """
    await message.answer(
        "📚 Справка по командам:\n\n"
        "Доступные команды:\n"
        "• /start - Начать работу с ботом\n"
        "• /report - Показать отчет по задачам\n"
        "• /help - Показать эту справку\n\n"
        "Или используйте кнопки меню:",
        reply_markup=get_main_keyboard()
    )


@router.message(F.text.startswith("/"))
async def cmd_unknown(message: Message):
    """
    Обработка неизвестных команд
    
    Given: Пользователь отправляет неизвестную команду (начинается с /)
    When: Команда не распознана другими handlers
    Then: Бот отправляет сообщение с доступными командами
    
    Note: Этот handler перехватывает все команды, которые не обработаны ранее
    """
    await message.answer(
        "❓ Неизвестная команда.\n\n"
        "Доступные команды:\n"
        "• /start - Начать работу с ботом\n"
        "• /report - Показать отчет по задачам\n"
        "• /help - Показать справку\n\n"
        "Или используйте кнопки меню:",
        reply_markup=get_main_keyboard()
    )


@router.message()
async def handle_unknown_message(message: Message):
    """
    Обработка неизвестных сообщений (fallback)
    
    Given: Пользователь отправляет сообщение, которое не обрабатывается
    When: Сообщение не попадает под другие handlers (не команда, не FSM состояние, не кнопка)
    Then: Бот отправляет подсказку
    
    Note: Этот handler должен быть последним в цепочке роутеров
    Он срабатывает только если сообщение не обработано другими handlers
    (FSM handlers имеют приоритет и обрабатываются раньше)
    """
    # Этот handler срабатывает только для сообщений,
    # которые не обработаны другими handlers (включая FSM)
    # Проверяем, что это текстовое сообщение (не команда)
    if message.text and not message.text.startswith("/"):
        await message.answer(
            "🤔 Я не понимаю эту команду.\n\n"
            "Используйте кнопки меню или команду /start для начала работы.",
            reply_markup=get_main_keyboard()
        )

