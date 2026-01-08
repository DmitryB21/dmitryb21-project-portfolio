"""
Обработчик команды /start

Given: Пользователь отправляет команду /start
When: Команда обрабатывается
Then: Бот отправляет приветственное сообщение и показывает главную клавиатуру
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from bot.keyboards.reply import get_main_keyboard

router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """
    Обработка команды /start
    
    Given: Пользователь отправляет /start
    When: Команда обрабатывается
    Then: 
        - FSM состояние сбрасывается (если было активно)
        - Отправляется приветственное сообщение
        - Показывается главная Reply-клавиатура
    """
    # Сброс FSM состояния (если пользователь был в процессе добавления задачи)
    await state.clear()
    
    # Приветственное сообщение
    welcome_text = (
        "👋 Привет! Я бот-помощник для менеджера по продажам и маркетолога.\n\n"
        "Я помогу вам:\n"
        "• Добавлять и управлять задачами\n"
        "• Добавлять и отслеживать сделки\n"
        "• Получать советы по маркетингу\n"
        "• Мотивироваться для достижения целей\n"
        "• Смотреть отчеты по закрытым сделкам\n\n"
        "Выберите действие:"
    )
    
    # Отправка сообщения с клавиатурой
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard()
    )

