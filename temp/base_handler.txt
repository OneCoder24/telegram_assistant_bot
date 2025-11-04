# handlers/base_handler.py
from logger_config import get_logger
from modules.notes import get_all_notes, format_notes_list
from modules.tasks import get_all_tasks, format_tasks_list # Добавлен импорт для задач
from modules.reminders import get_all_reminders, format_reminders_list # Добавлен импорт для напоминаний
from handlers.notes_handler import handle_notes_callback, handle_notes_message_input
from handlers.tasks_handler import handle_tasks_callback, handle_tasks_message_input # Добавлен импорт обработчиков задач
from handlers.reminders_handler import handle_reminders_callback, handle_reminders_message_input # Добавлен импорт обработчиков напоминаний
from database import get_db

logger = get_logger()
db = get_db()

def handle_main_menu_reply(chat_id, user_id, text, user_states): # user_id уже передаётся
    """Обрабатывает нажатие reply-кнопок главного меню."""
    # Сбрасываем текущее состояние, используя (user_id, chat_id) как ключ
    # Также сбрасываем временные данные
    temp_text_key_add = (user_id, chat_id, 'temp_task_text_for_add')
    current_state = user_states.pop((user_id, chat_id), None)
    temp_text = user_states.pop(temp_text_key_add, None)
    if current_state:
        logger.info(f"Действие {current_state} отменено пользователем {user_id} через reply-кнопку.")
    if temp_text:
        logger.info(f"Временный текст задачи ({temp_text}) сброшен пользователем {user_id} через reply-кнопку.")

    # --- Заглушка для каждого модуля ---
    if text == "📝 Заметки":
        # Передаём user_id в get_all_notes
        notes = get_all_notes(user_id) # <--- ИЗМЕНЕНО
        notes_text = format_notes_list(notes)
        return notes_text, "notes_keyboard"
    elif text == "✅ Задачи": # <-- Добавлено
        # Передаём user_id в get_all_tasks
        tasks = get_all_tasks(user_id) # <--- ИЗМЕНЕНО
        tasks_text = format_tasks_list(tasks)
        return tasks_text, "tasks_keyboard"
    elif text == "⏰ Напоминания": # <-- Добавлено
        # Передаём user_id в get_all_reminders
        reminders = get_all_reminders(user_id) # <--- ИЗМЕНЕНО
        reminders_text = format_reminders_list(reminders)
        return reminders_text, "reminders_keyboard"
    elif text == "🌤️ Погода":
        return "Модуль погоды (заглушка).", "weather_keyboard"
    elif text == "⚙️ Настройки":
        return "Модуль настроек (заглушка).", "settings_keyboard"

    return None, None # Если текст не совпадает

def handle_callback_query(callback_query, user_states, user_id): # Добавляем user_id
    """Обрабатывает callback_query, распределяя по модулям."""
    data = callback_query["data"]
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    # user_id = callback_query["from"]["id"] # <-- УБРАНО, теперь передаётся как аргумент

    logger.info(f"Получен callback_query от {user_id}: {data}")

    # Если callback_data относится к заметкам, передаём в notes_handler
    if data.startswith(("edit_note_", "delete_note_", "add_note_prompt", "notes_menu")):
        return "notes", data

    # Если callback_data относится к задачам, передаём в tasks_handler
    if data.startswith(("edit_task_", "keep_current_text_", "keep_current_deadline_", "toggle_task_status_", "delete_task_", "add_task_prompt", "tasks_menu")): # <-- Добавлено
        return "tasks", data

    # Если callback_data относится к напоминаниям, передаём в reminders_handler
    if data.startswith(("toggle_reminder_type_", "delete_reminder_", "add_reminder_prompt", "reminders_menu")): # <-- Добавлено
        return "reminders", data

    elif data == 'main_menu':
        # Возвращаем текст и тип клавиатуры
        return "main_menu", ("Глaвное меню:", "main_keyboard")

    return None, None # Не обработано в base_handler

def handle_message_input(message, user_states, user_id): # Добавляем user_id
    """Обрабатывает текстовые сообщения, распределяя по модулям."""
    text = message.get("text", "")
    chat_id = message["chat"]["id"]
    # user_id = message["from"]["id"] # <-- УБРАНО, теперь передаётся как аргумент

    # --- ПРИОРИТЕТ 1: Проверяем, является ли сообщение нажатием reply-кнопки главного меню ---
    if text in ["📝 Заметки", "✅ Задачи", "⏰ Напоминания", "🌤️ Погода", "⚙️ Настройки"]: # <-- "✅ Задачи" и "⏰ Напоминания" добавлены
        # Обрабатываем в base_handler
        text_to_send, keyboard_type = handle_main_menu_reply(chat_id, user_id, text, user_states)
        # Возвращаем тип меню и (text, keyboard_type)
        if text_to_send is not None:
            return "main_reply", (text_to_send, keyboard_type)
        else:
            # Если текст не совпадает, возвращаем None
            return None, None

    # --- ПРИОРИТЕТ 2: Проверяем, находится ли пользователь в состоянии ожидания ввода ---
    current_state = user_states.get((user_id, chat_id))
    if current_state and current_state.startswith("waiting_for_note_"):
        # Передаём в notes_handler
        return "notes", text
    # Добавляем проверку для задач
    if current_state and current_state.startswith("waiting_for_task_"): # <-- Добавлено
        # Передаём в tasks_handler
        return "tasks", text
    # Добавляем проверку для напоминаний
    if current_state and current_state.startswith("waiting_for_reminder_"): # <-- Добавлено
        # Передаём в reminders_handler
        return "reminders", text

    # --- ПРИОРИТЕТ 3: Обработка команды /start ---
    if text == "/start":
        # Возвращаем текст и тип клавиатуры
        return "start", ("Привет! Это ваш личный ассистент.", "main_keyboard")

    return None, None # Не обработано