"""
Обработчики сделок

Given: Пользователь взаимодействует со сделками
When: Пользователь добавляет/просматривает сделки
Then: Операции выполняются согласно требованиям
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.keyboards.reply import get_main_keyboard
from bot.keyboards.deal_inline import get_deal_keyboard
from bot.states.deal_states import DealAddStates, DealChangeStatusStates
from bot.services.deal_service import deal_service

router = Router(name="deals")


@router.message(F.text == "Добавить сделку")
async def cmd_add_deal(message: Message, state: FSMContext):
    """
    Начало процесса добавления сделки
    
    Given: Пользователь в начальном состоянии
    When: Пользователь нажимает "Добавить сделку"
    Then: Бот переводит пользователя в состояние waiting_for_title
    """
    await message.answer(
        "📝 Введите название сделки:",
        reply_markup=None  # Убираем клавиатуру для ввода текста
    )
    await state.set_state(DealAddStates.waiting_for_title)


@router.message(DealAddStates.waiting_for_title)
async def process_deal_title(message: Message, state: FSMContext):
    """
    Обработка названия сделки
    
    Given: Пользователь в состоянии waiting_for_title
    When: Пользователь отправляет название сделки
    Then: Сохраняется название и переход в waiting_for_amount
    """
    title = message.text.strip()
    
    # Валидация названия
    if not title:
        await message.answer(
            "❌ Название сделки не может быть пустым. Попробуйте еще раз.\n\n"
            "💡 Или отправьте /start для отмены."
        )
        return
    
    # Сохранение названия в FSM data
    await state.update_data(title=title)
    
    # Переход к следующему шагу
    await message.answer(
        f"✅ Название сохранено: {title}\n\n"
        "💰 Теперь введите сумму сделки в рублях:\n\n"
        "Например: 85000 или 85000.50"
    )
    await state.set_state(DealAddStates.waiting_for_amount)


@router.message(DealAddStates.waiting_for_amount)
async def process_deal_amount(message: Message, state: FSMContext):
    """
    Обработка суммы сделки
    
    Given: Пользователь в состоянии waiting_for_amount
    When: Пользователь отправляет сумму
    Then: Сохраняется сумма и переход в waiting_for_status
    """
    amount_str = message.text.strip()
    data = await state.get_data()
    title = data.get("title")
    
    # Простая валидация суммы (более детальная в сервисе)
    try:
        float(amount_str.replace(",", "."))
    except ValueError:
        await message.answer(
            "❌ Неверный формат суммы. Используйте число (например: 85000 или 85000.50)\n\n"
            "💡 Или отправьте /start для отмены."
        )
        return
    
    # Сохранение суммы в FSM data
    await state.update_data(amount=amount_str)
    
    # Создаем Inline-клавиатуру для выбора статуса
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Открыта", callback_data="deal_status_Открыта")
    builder.button(text="В процессе", callback_data="deal_status_В процессе")
    builder.button(text="Закрыта", callback_data="deal_status_Закрыта")
    builder.adjust(1)
    
    await message.answer(
        f"✅ Сумма сохранена: {amount_str} руб.\n\n"
        "📊 Выберите статус сделки:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(DealAddStates.waiting_for_status)


@router.callback_query(DealAddStates.waiting_for_status, F.data.startswith("deal_status_"))
async def process_deal_status(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора статуса сделки и сохранение
    
    Given: Пользователь в состоянии waiting_for_status
    When: Пользователь выбирает статус через Inline-кнопку
    Then: Сделка сохраняется
    """
    try:
        # Извлечение статуса из callback_data (формат: "deal_status_Открыта")
        # Используем replace для правильной обработки статусов с пробелами
        if not callback.data.startswith("deal_status_"):
            raise ValueError("Неверный формат callback_data")
        status = callback.data.replace("deal_status_", "", 1)
    except (ValueError, AttributeError):
        await callback.answer("❌ Ошибка: неверный формат данных.", show_alert=True)
        return
    
    data = await state.get_data()
    title = data.get("title")
    amount_str = data.get("amount")
    
    try:
        # Создание сделки через сервис (валидация внутри)
        deal = deal_service.create_deal(
            user_id=callback.from_user.id,
            title=title,
            amount_str=amount_str,
            status=status
        )
        
        # Форматирование суммы
        amount_formatted = f"{deal.amount:,.0f}".replace(",", " ")
        
        # Успешное создание сделки
        await callback.message.edit_text(
            f"✅ Сделка '{deal.title}' создана!\n\n"
            f"💰 Сумма: {amount_formatted} руб.\n"
            f"📊 Статус: {deal.status}",
            reply_markup=None
        )
        
        await callback.answer("✅ Сделка успешно добавлена!")
        
        # Очистка FSM состояния
        await state.clear()
        
        # Отправляем главное меню
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_main_keyboard()
        )
        
    except ValueError as e:
        # Ошибка валидации
        await callback.answer(f"❌ {str(e)}", show_alert=True)


@router.message(DealAddStates.waiting_for_status)
async def process_deal_status_text(message: Message, state: FSMContext):
    """
    Обработка статуса сделки через текстовое сообщение (fallback)
    """
    await message.answer(
        "📊 Пожалуйста, выберите статус с помощью кнопок выше.\n\n"
        "💡 Или отправьте /start для отмены."
    )


@router.message(F.text == "Просмотреть сделки")
async def cmd_list_deals(message: Message):
    """
    Показ списка сделок пользователя
    
    Given: У пользователя есть сделки (или нет)
    When: Пользователь нажимает "Просмотреть сделки"
    Then: Бот показывает список сделок
    """
    user_id = message.from_user.id
    deals = deal_service.get_user_deals(user_id)
    
    if not deals:
        await message.answer(
            "📭 У вас пока нет сделок.\n\n"
            "Добавьте сделку, нажав кнопку 'Добавить сделку'",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Отправляем каждую сделку отдельным сообщением с кнопками
    for deal in deals:
        amount_formatted = f"{deal.amount:,.0f}".replace(",", " ")
        status_emoji = {
            "Открыта": "🔵",
            "В процессе": "🟡",
            "Закрыта": "🟢"
        }.get(deal.status, "⚪")
        
        deal_text = (
            f"📌 {deal.title}\n"
            f"💰 {amount_formatted} руб.\n"
            f"{status_emoji} {deal.status}"
        )
        
        await message.answer(
            deal_text,
            reply_markup=get_deal_keyboard(deal.id)
        )


@router.callback_query(F.data.startswith("deal_change_status_"))
async def cmd_change_deal_status(callback: CallbackQuery, state: FSMContext):
    """
    Начало процесса изменения статуса сделки
    
    Given: Пользователь просматривает сделку
    When: Пользователь нажимает "Изменить статус сделки"
    Then: Бот переводит пользователя в состояние waiting_for_status
    """
    try:
        # Извлечение ID сделки из callback_data
        deal_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат данных.", show_alert=True)
        return
    
    # Получение сделки
    deal = deal_service.get_deal_by_id(deal_id)
    
    if not deal:
        await callback.answer("❌ Сделка не найдена. Возможно, она была удалена.", show_alert=True)
        return
    
    # Проверка прав доступа
    if deal.user_id != callback.from_user.id:
        await callback.answer("❌ У вас нет доступа к этой сделке.", show_alert=True)
        return
    
    # Сохранение ID сделки в FSM data
    await state.update_data(deal_id=deal_id)
    
    # Создаем Inline-клавиатуру для выбора статуса
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Открыта", callback_data="deal_new_status_Открыта")
    builder.button(text="В процессе", callback_data="deal_new_status_В процессе")
    builder.button(text="Закрыта", callback_data="deal_new_status_Закрыта")
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"📊 Выберите новый статус для сделки '{deal.title}':",
        reply_markup=builder.as_markup()
    )
    
    await callback.answer()
    await state.set_state(DealChangeStatusStates.waiting_for_status)


@router.callback_query(DealChangeStatusStates.waiting_for_status, F.data.startswith("deal_new_status_"))
async def process_deal_status_change(callback: CallbackQuery, state: FSMContext):
    """
    Обработка изменения статуса сделки
    
    Given: Пользователь в состоянии waiting_for_status
    When: Пользователь выбирает новый статус через Inline-кнопку
    Then: Статус сделки обновляется
    """
    try:
        # Извлечение статуса из callback_data
        if not callback.data.startswith("deal_new_status_"):
            raise ValueError("Неверный формат callback_data")
        new_status = callback.data.replace("deal_new_status_", "", 1)
    except (ValueError, AttributeError):
        await callback.answer("❌ Ошибка: неверный формат данных.", show_alert=True)
        return
    
    data = await state.get_data()
    deal_id = data.get("deal_id")
    
    if not deal_id:
        await callback.answer("❌ Ошибка: ID сделки не найден.", show_alert=True)
        await state.clear()
        return
    
    # Получение сделки
    deal = deal_service.get_deal_by_id(deal_id)
    
    if not deal:
        await callback.answer("❌ Сделка не найдена.", show_alert=True)
        await state.clear()
        return
    
    # Обновление статуса
    updated_deal = deal_service.update_deal_status(deal_id, new_status)
    
    if not updated_deal:
        await callback.answer("❌ Ошибка при обновлении статуса.", show_alert=True)
        await state.clear()
        return
    
    # Форматирование суммы
    amount_formatted = f"{updated_deal.amount:,.0f}".replace(",", " ")
    status_emoji = {
        "Открыта": "🔵",
        "В процессе": "🟡",
        "Закрыта": "🟢"
    }.get(updated_deal.status, "⚪")
    
    # Обновление сообщения
    deal_text = (
        f"📌 {updated_deal.title}\n"
        f"💰 {amount_formatted} руб.\n"
        f"{status_emoji} {updated_deal.status}"
    )
    
    await callback.message.edit_text(
        deal_text,
        reply_markup=get_deal_keyboard(updated_deal.id)
    )
    
    await callback.answer(f"✅ Статус сделки изменен на '{new_status}'")
    
    # Очистка FSM состояния
    await state.clear()


@router.message(DealChangeStatusStates.waiting_for_status)
async def process_deal_status_change_text(message: Message, state: FSMContext):
    """
    Обработка статуса сделки через текстовое сообщение (fallback)
    """
    await message.answer(
        "📊 Пожалуйста, выберите статус с помощью кнопок выше.\n\n"
        "💡 Или отправьте /start для отмены."
    )

