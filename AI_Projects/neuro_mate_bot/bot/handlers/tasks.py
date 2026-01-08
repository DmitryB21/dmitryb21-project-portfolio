"""
Обработчики задач

Given: Пользователь взаимодействует с задачами
When: Пользователь добавляет/просматривает/изменяет/удаляет задачу
Then: Операции выполняются согласно тестовым сценариям
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.keyboards.reply import get_main_keyboard
from bot.keyboards.inline import get_task_keyboard
from bot.states.task_states import TaskAddStates
from bot.services.task_service import task_service

router = Router(name="tasks")


@router.message(F.text == "Добавить задачу")
async def cmd_add_task(message: Message, state: FSMContext):
    """
    Начало процесса добавления задачи
    
    Given: Пользователь в начальном состоянии
    When: Пользователь нажимает "➕ Добавить задачу"
    Then: Бот переводит пользователя в состояние waiting_for_title
    """
    await message.answer(
        "📝 Введите название задачи:",
        reply_markup=None  # Убираем клавиатуру для ввода текста
    )
    await state.set_state(TaskAddStates.waiting_for_title)


@router.message(TaskAddStates.waiting_for_title)
async def process_task_title(message: Message, state: FSMContext):
    """
    Обработка названия задачи
    
    Given: Пользователь в состоянии waiting_for_title
    When: Пользователь отправляет название задачи
    Then: 
        - Если название валидно, сохраняется и переход в waiting_for_time
        - Если название пустое, отправляется ошибка
    """
    title = message.text.strip()
    
    # Валидация названия
    if not title:
        await message.answer(
            "❌ Название задачи не может быть пустым. Попробуйте еще раз.\n\n"
            "💡 Или отправьте /start для отмены."
        )
        return
    
    # Сохранение названия в FSM data
    await state.update_data(title=title)
    
    # Переход к следующему шагу
    await message.answer(
        f"✅ Название сохранено: {title}\n\n"
        "⏰ Теперь введите время выполнения задачи в формате:\n"
        "📅 HH:MM\n\n"
        "Например: 18:00"
    )
    await state.set_state(TaskAddStates.waiting_for_time)


@router.message(TaskAddStates.waiting_for_time)
async def process_task_time(message: Message, state: FSMContext):
    """
    Обработка времени задачи и сохранение
    
    Given: Пользователь в состоянии waiting_for_time
    When: Пользователь отправляет время
    Then: 
        - Если время валидно, задача сохраняется
        - Если формат неверный, отправляется ошибка
    """
    time_str = message.text.strip()
    data = await state.get_data()
    title = data.get("title")
    
    try:
        # Попытка создать задачу через сервис (валидация внутри)
        task = task_service.create_task(
            user_id=message.from_user.id,
            title=title,
            time_str=time_str
        )
        
        # Форматирование времени для сообщения
        time_formatted = task.time.strftime("%H:%M")
        
        # Успешное создание задачи
        await message.answer(
            f"✅ Задача '{task.title}' добавлена на {time_formatted}\n\n"
            f"📋 Статус: {task.status}",
            reply_markup=get_main_keyboard()
        )
        
        # Очистка FSM состояния
        await state.clear()
        
    except ValueError as e:
        # Ошибка валидации
        await message.answer(
            f"❌ {str(e)}\n\n"
            "💡 Или отправьте /start для отмены."
        )


@router.message(F.text == "Просмотреть задачи")
async def cmd_list_tasks(message: Message):
    """
    Показ списка задач пользователя
    
    Given: У пользователя есть задачи (или нет)
    When: Пользователь нажимает "Просмотреть задачи"
    Then: Бот показывает список задач с Inline-кнопками
    """
    user_id = message.from_user.id
    tasks = task_service.get_user_tasks(user_id)
    
    if not tasks:
        await message.answer(
            "📭 У вас пока нет задач.\n\n"
            "Добавьте задачу, нажав кнопку 'Добавить задачу'",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Формирование списка задач
    tasks_text = "📋 Ваши задачи:\n\n"
    
    for idx, task in enumerate(tasks, 1):
        time_formatted = task.time.strftime("%H:%M")
        status_emoji = "✅" if task.status == "Выполнена" else "❌"
        
        tasks_text += (
            f"{idx}. {task.title}\n"
            f"   📅 {time_formatted}\n"
            f"   {status_emoji} {task.status}\n\n"
        )
    
    # Отправка сообщения со списком задач
    # Для каждой задачи нужно отправить отдельное сообщение с Inline-кнопками
    # Или использовать один список с кнопками для всех задач
    await message.answer(
        tasks_text,
        reply_markup=get_main_keyboard()
    )
    
    # Отправляем каждую задачу отдельным сообщением с кнопками
    for task in tasks:
        time_formatted = task.time.strftime("%H:%M")
        status_emoji = "✅" if task.status == "Выполнена" else "❌"
        
        task_text = (
            f"📌 {task.title}\n"
            f"📅 {time_formatted}\n"
            f"{status_emoji} {task.status}"
        )
        
        await message.answer(
            task_text,
            reply_markup=get_task_keyboard(task.id, task.status)
        )


@router.callback_query(F.data.startswith("task_complete_"))
async def process_task_complete(callback: CallbackQuery):
    """
    Обработка изменения статуса задачи на "Выполнена"
    
    Given: Пользователь просматривает задачу со статусом "Не выполнена"
    When: Пользователь нажимает кнопку "✅ Выполнена"
    Then: Статус задачи изменяется на "Выполнена", сообщение обновляется
    """
    try:
        # Извлечение ID задачи из callback_data
        task_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат данных.")
        return
    
    # Получение задачи
    task = task_service.get_task_by_id(task_id)
    
    if not task:
        await callback.answer("❌ Задача не найдена. Возможно, она была удалена.")
        return
    
    # Проверка прав доступа
    if task.user_id != callback.from_user.id:
        await callback.answer("❌ У вас нет доступа к этой задаче.")
        return
    
    # Обновление статуса
    updated_task = task_service.update_task_status(task_id, "Выполнена")
    
    if not updated_task:
        await callback.answer("❌ Ошибка при обновлении задачи.")
        return
    
    # Ответ на callback
    await callback.answer(f"✅ Задача '{updated_task.title}' отмечена как выполненная")
    
    # Проверка количества выполненных задач для уведомления
    user_stats = task_service.get_task_statistics(callback.from_user.id)
    if user_stats["completed"] == 2:
        await callback.message.answer("🎉 Ты выполнил 2 задачи! Ты крут!")
    
    # Обновление сообщения
    time_formatted = updated_task.time.strftime("%H:%M")
    task_text = (
        f"📌 {updated_task.title}\n"
        f"📅 {time_formatted}\n"
        f"✅ {updated_task.status}"
    )
    
    await callback.message.edit_text(
        task_text,
        reply_markup=get_task_keyboard(updated_task.id, updated_task.status)
    )


@router.callback_query(F.data.startswith("task_delete_"))
async def process_task_delete(callback: CallbackQuery):
    """
    Обработка удаления задачи
    
    Given: Пользователь просматривает задачу
    When: Пользователь нажимает кнопку "🗑 Удалить"
    Then: Задача удаляется, сообщение обновляется
    """
    try:
        # Извлечение ID задачи из callback_data
        task_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат данных.")
        return
    
    # Получение задачи перед удалением (для сообщения)
    task = task_service.get_task_by_id(task_id)
    
    if not task:
        await callback.answer("❌ Задача не найдена. Возможно, она была удалена.")
        return
    
    # Проверка прав доступа
    if task.user_id != callback.from_user.id:
        await callback.answer("❌ У вас нет доступа к этой задаче.")
        return
    
    # Удаление задачи
    deleted = task_service.delete_task(task_id)
    
    if not deleted:
        await callback.answer("❌ Ошибка при удалении задачи.")
        return
    
    # Ответ на callback
    await callback.answer(f"🗑 Задача '{task.title}' удалена")
    
    # Удаление сообщения или обновление
    await callback.message.delete()

