"""
Обработчики дополнительных функций

Given: Пользователь запрашивает дополнительные функции
When: Пользователь нажимает кнопки "Получить совет по маркетингу" или "Получить мотивацию"
Then: Бот отправляет соответствующие сообщения через ChatGPT API
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.keyboards.reply import get_main_keyboard
from bot.states.marketing_states import MarketingAdviceStates
from bot.services.chatgpt_service import chatgpt_service

router = Router(name="extras")


@router.message(F.text == "Получить совет по маркетингу")
async def cmd_marketing_advice_start(message: Message, state: FSMContext):
    """
    Начало процесса получения совета по маркетингу
    
    Given: Пользователь нажал кнопку "Получить совет по маркетингу"
    When: Сообщение обрабатывается
    Then: Бот запрашивает описание проблемы и переводит в FSM состояние
    """
    await message.answer(
        "📝 Опишите вашу проблему или вопрос по маркетингу:\n\n"
        "Например: 'Как увеличить продажи?' или 'Как привлечь новых клиентов?'",
        reply_markup=None  # Убираем клавиатуру для ввода текста
    )
    await state.set_state(MarketingAdviceStates.waiting_for_problem)


@router.message(MarketingAdviceStates.waiting_for_problem)
async def process_marketing_problem(message: Message, state: FSMContext):
    """
    Обработка описания проблемы и получение совета от ChatGPT
    
    Given: Пользователь в состоянии waiting_for_problem
    When: Пользователь отправляет описание проблемы
    Then: Бот отправляет запрос в ChatGPT и возвращает совет
    """
    problem_description = message.text.strip()
    
    # Валидация описания
    if not problem_description:
        await message.answer(
            "❌ Описание проблемы не может быть пустым. Попробуйте еще раз.\n\n"
            "💡 Или отправьте /start для отмены."
        )
        return
    
    # Отправка сообщения о том, что бот думает
    thinking_msg = await message.answer("🤔 Думаю над решением...")
    
    # Получение совета от ChatGPT
    advice = await chatgpt_service.get_marketing_advice(problem_description)
    
    # Удаление сообщения "Думаю..."
    await thinking_msg.delete()
    
    # Отправка совета
    await message.answer(
        f"📈 Совет по маркетингу:\n\n{advice}",
        reply_markup=get_main_keyboard()
    )
    
    # Очистка FSM состояния
    await state.clear()


@router.message(F.text == "Получить мотивацию")
async def cmd_motivation(message: Message):
    """
    Обработка запроса мотивации
    
    Given: Пользователь нажал кнопку "Получить мотивацию"
    When: Сообщение обрабатывается
    Then: Бот отправляет мотивационное сообщение через ChatGPT API
    """
    # Отправка сообщения о том, что бот думает
    thinking_msg = await message.answer("💭 Генерирую мотивацию...")
    
    # Получение мотивации от ChatGPT
    motivation = await chatgpt_service.get_motivation()
    
    # Удаление сообщения "Генерирую..."
    await thinking_msg.delete()
    
    # Отправка мотивации
    await message.answer(
        f"💬 {motivation}\n\n💪 У тебя все получится!",
        reply_markup=get_main_keyboard()
    )
