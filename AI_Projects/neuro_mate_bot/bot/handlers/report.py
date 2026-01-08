"""
Обработчик команды /report

Given: Пользователь отправляет команду /report
When: Команда обрабатывается
Then: Бот отправляет отчет по закрытым сделкам за сессию
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from bot.keyboards.reply import get_main_keyboard
from bot.services.deal_service import deal_service

router = Router(name="report")


@router.message(Command("report"))
async def cmd_report(message: Message):
    """
    Показ отчета по закрытым сделкам
    
    Given: У пользователя есть закрытые сделки (или нет)
    When: Пользователь отправляет /report
    Then: Бот показывает количество закрытых сделок и общую сумму
    """
    user_id = message.from_user.id
    stats = deal_service.get_closed_deals_statistics(user_id)
    
    if stats["count"] == 0:
        await message.answer(
            "📊 У вас пока нет закрытых сделок за текущую сессию.\n\n"
            "Добавьте сделку, нажав кнопку 'Добавить сделку'",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Форматирование суммы
    total_amount_formatted = f"{stats['total_amount']:,.0f}".replace(",", " ")
    
    # Формирование отчета согласно требованиям
    count = stats['count']
    if count == 1:
        deals_word = "сделку"
    elif 2 <= count <= 4:
        deals_word = "сделки"
    else:
        deals_word = "сделок"
    
    report_text = (
        f"📊 За текущую сессию ты закрыл {count} {deals_word} "
        f"на сумму {total_amount_formatted} рублей!"
    )
    
    await message.answer(
        report_text,
        reply_markup=get_main_keyboard()
    )
