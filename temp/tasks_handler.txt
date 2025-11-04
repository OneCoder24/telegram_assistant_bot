# handlers/tasks_handler.py
from logger_config import get_logger
from modules.tasks import get_all_tasks, add_task, update_task, delete_task, get_task_by_id, format_tasks_list, check_overdue_tasks
from utils.datetime_parser import parse_deadline
from datetime import datetime

logger = get_logger()

# --- Вспомогательные функции для клавиатуры "Оставить...", нужно будет получить из bot.py ---
get_keep_current_text_keyboard_func = None
def set_keep_current_text_keyboard_func(func):
    global get_keep_current_text_keyboard_func
    get_keep_current_text_keyboard_func = func

get_keep_current_deadline_keyboard_func = None
def set_keep_current_deadline_keyboard_func(func):
    global get_keep_current_deadline_keyboard_func
    get_keep_current_deadline_keyboard_func = func

# Вспомогательная функция для клавиатуры отмены, нужно будет получить из bot.py
get_cancel_inline_keyboard_func = None
def set_cancel_keyboard_func(func):
    global get_cancel_inline_keyboard_func
    get_cancel_inline_keyboard_func = func

def handle_tasks_callback(data, chat_id, message_id, user_id, user_states, send_message_func, edit_message_text_func, get_tasks_keyboard_func): # user_id теперь передаётся
    """Обрабатывает callback_query, связанные с задачами."""
    if data.startswith("edit_task_"):
        task_id = int(data.split("_")[2])
        # Передаём user_id в get_task_by_id
        task_info = get_task_by_id(user_id, task_id) # <--- ИЗМЕНЕНО
        if task_info is not None:
            # Начинаем двухэтапное редактирование
            # Устанавливаем состояние для редактирования текста
            user_states[(user_id, chat_id)] = f"waiting_for_task_text_edit_{task_id}"
            old_text = task_info['text']
            escaped_text = _escape_html(old_text) # Экранируем HTML-символы в старом тексте
            # Отправляем сообщение с просьбой ввести новый текст и старым текстом в формате кода (HTML <code>)
            # Используем parse_mode='HTML'
            message_text = f"Введите новый текст для задачи {task_id}:\nТекущий текст:\n<code>{escaped_text}</code>"
            # Отправляем сообщение с клавиатурой "Оставить текущий текст"
            # Используем функцию, переданную из bot.py
            if get_keep_current_text_keyboard_func:
                keyboard = get_keep_current_text_keyboard_func(task_id, "tasks_menu")
            else:
                # Если функция не установлена, используем стандартную клавиатуру с отменой
                keyboard = get_cancel_inline_keyboard_func("tasks_menu")
            send_message_func(chat_id, message_text, keyboard, parse_mode='HTML')
        else:
            send_message_func(chat_id, f"Задача с ID {task_id} не найдена.")
            # Передаём user_id в _refresh_tasks_menu
            _refresh_tasks_menu(chat_id, user_states, send_message_func, get_tasks_keyboard_func, user_id) # <--- ИЗМЕНЕНО

    elif data.startswith("keep_current_text_"):
        task_id = int(data.split("_")[3])
        # Передаём user_id в get_task_by_id
        task_info = get_task_by_id(user_id, task_id) # <--- ИЗМЕНЕНО
        if task_info:
            # Переходим к редактированию дедлайна, сохраняя старый текст
            user_states[(user_id, chat_id)] = f"waiting_for_task_deadline_edit_{task_id}"
            current_deadline = task_info['deadline']
            deadline_str = current_deadline if current_deadline else "Не установлен"
            message_text = f"Введите новый дедлайн для задачи {task_id} (например, '24.10'):\nТекущий дедлайн: {deadline_str}"
            # Отправляем сообщение с клавиатурой "Оставить текущую дату"
            # Используем функцию, переданную из bot.py
            if get_keep_current_deadline_keyboard_func:
                keyboard = get_keep_current_deadline_keyboard_func(task_id, "tasks_menu")
            else:
                # Если функция не установлена, используем стандартную клавиатуру с отменой
                keyboard = get_cancel_inline_keyboard_func("tasks_menu")
            send_message_func(chat_id, message_text, keyboard, parse_mode=None)
        else:
            send_message_func(chat_id, f"Задача с ID {task_id} не найдена.")
            # Передаём user_id в _refresh_tasks_menu
            _refresh_tasks_menu(chat_id, user_states, send_message_func, get_tasks_keyboard_func, user_id) # <--- ИЗМЕНЕНО

    elif data.startswith("keep_current_deadline_"):
        task_id = int(data.split("_")[3])
        # Завершаем редактирование, ничего не обновляя
        user_states.pop((user_id, chat_id), None)
        send_message_func(chat_id, f"Редактирование задачи {task_id} завершено.")
        # Передаём user_id в _refresh_tasks_menu
        _refresh_tasks_menu(chat_id, user_states, send_message_func, get_tasks_keyboard_func, user_id) # <--- ИЗМЕНЕНО

    elif data.startswith("toggle_task_status_"):
        task_id = int(data.split("_")[3])
        # Передаём user_id в get_task_by_id
        task_info = get_task_by_id(user_id, task_id) # <--- ИЗМЕНЕНО
        if task_info is not None:
            new_status = not task_info['is_completed']
            # Передаём user_id в update_task
            success = update_task(user_id, task_id, is_completed=new_status) # <--- ИЗМЕНЕНО
            if success:
                status_text = "выполнена" if new_status else "не выполнена"
                send_message_func(chat_id, f"Задача с ID {task_id} отмечена как {status_text}.")
                logger.info(f"Пользователь {user_id} изменил статус задачи (ID: {task_id}) на {status_text}.")
            else:
                send_message_func(chat_id, f"Ошибка при изменении статуса задачи с ID {task_id}.")
                logger.error(f"Ошибка при изменении статуса задачи (ID: {task_id}) пользователем {user_id}.")
        else:
            send_message_func(chat_id, f"Задача с ID {task_id} не найдена.")

        # Передаём user_id в _refresh_tasks_menu
        _refresh_tasks_menu(chat_id, user_states, send_message_func, get_tasks_keyboard_func, user_id) # <--- ИЗМЕНЕНО

    elif data.startswith("delete_task_"):
        task_id = int(data.split("_")[2])
        # Передаём user_id в delete_task
        success = delete_task(user_id, task_id) # <--- ИЗМЕНЕНО
        if success:
            send_message_func(chat_id, f"Задача с ID {task_id} удалена.")
            logger.info(f"Пользователь {user_id} удалил задачу (ID: {task_id}).")
        else:
            send_message_func(chat_id, f"Ошибка при удалении задачи с ID {task_id}.")
            logger.error(f"Ошибка при удалении задачи (ID: {task_id}) пользователем {user_id}.")

        # Передаём user_id в _refresh_tasks_menu
        _refresh_tasks_menu(chat_id, user_states, send_message_func, get_tasks_keyboard_func, user_id) # <--- ИЗМЕНЕНО

    elif data == 'add_task_prompt':
        # Устанавливаем состояние ожидания текста новой задачи
        user_states[(user_id, chat_id)] = "waiting_for_task_text"
        # Отправляем НОВОЕ сообщение с просьбой ввести текст
        send_message_func(chat_id, "Введите текст новой задачи:", get_cancel_inline_keyboard_func("tasks_menu"))

    elif data == 'tasks_menu':
        # Сброс состояния при возврате в меню
        if user_states.get((user_id, chat_id)) and user_states[(user_id, chat_id)].startswith("waiting_for_task_"):
            user_states.pop((user_id, chat_id), None)
            # Также сбрасываем временные данные
            temp_text_key_add = (user_id, chat_id, 'temp_task_text_for_add')
            user_states.pop(temp_text_key_add, None)
            send_message_func(chat_id, "Действие с задачей отменено.")
            logger.info(f"Действие с задачей отменено пользователем {user_id} через inline-кнопку.")

        # Передаём user_id в _refresh_tasks_menu
        _refresh_tasks_menu(chat_id, user_states, edit_message_text_func, get_tasks_keyboard_func, user_id, message_id=message_id) # <--- ИЗМЕНЕНО

def handle_tasks_message_input(text, chat_id, user_id, user_states, send_message_func, edit_message_text_func, get_tasks_keyboard_func): # user_id теперь передаётся
    """Обрабатывает текстовые сообщения для задач."""
    current_state = user_states.get((user_id, chat_id))

    # Обработка добавления новой задачи
    if current_state == "waiting_for_task_text":
        if text.strip():
            task_text = text.strip()
            # Устанавливаем состояние ожидания дедлайна
            user_states[(user_id, chat_id)] = "waiting_for_task_deadline_after_add"
            # СОХРАНЯЕМ ВРЕМЕННО ТЕКСТ ЗАДАЧИ
            user_states[(user_id, chat_id, 'temp_task_text_for_add')] = task_text
            # Отправляем сообщение с просьбой ввести дедлайн
            send_message_func(chat_id, f"Задача '{task_text[:30]}...' добавлена. Введите дедлайн (например, '24.10') или 'нет', чтобы оставить без дедлайна.", get_cancel_inline_keyboard_func("tasks_menu"))
        else:
            send_message_func(chat_id, "Текст задачи не может быть пустым. Попробуйте снова.", get_cancel_inline_keyboard_func("tasks_menu"))

    elif current_state == "waiting_for_task_deadline_after_add":
        deadline = None
        if text.lower() != 'нет':
            # Используем парсер дат
            parsed_deadline = parse_deadline(text)
            if parsed_deadline:
                deadline = parsed_deadline
            else:
                # Используем функцию из bot.py для клавиатуры "Оставить..." или отмены
                keyboard = get_cancel_inline_keyboard_func("tasks_menu")
                send_message_func(chat_id, f"Неверный формат дедлайна: '{text}'. Используйте формат ДД.ММ (например, 24.10). Попробуйте снова.", keyboard)
                return # Остаемся в состоянии ожидания
        # Добавляем задачу с дедлайном (или без)
        # Получаем временно сохранённый текст
        temp_text_key = (user_id, chat_id, 'temp_task_text_for_add')
        saved_text = user_states.get(temp_text_key)
        if not saved_text:
             logger.error(f"Ошибка: текст задачи не найден в состоянии при добавлении дедлайна для {user_id}, {chat_id}")
             send_message_func(chat_id, "Ошибка при добавлении задачи. Попробуйте снова.")
             user_states.pop((user_id, chat_id), None)
             user_states.pop(temp_text_key, None) # Убедимся, что удалили
             # Передаём user_id в _refresh_tasks_menu
             _refresh_tasks_menu(chat_id, user_states, send_message_func, get_tasks_keyboard_func, user_id) # <--- ИЗМЕНЕНО
             return

        # Передаём user_id в add_task
        task_id = add_task(user_id, saved_text, deadline=deadline) # <--- ИЗМЕНЕНО
        if task_id:
            send_message_func(chat_id, f"Задача добавлена (ID: {task_id}).")
            logger.info(f"Пользователь {user_id} добавил задачу (ID: {task_id}).")
        else:
            send_message_func(chat_id, "Ошибка при добавлении задачи.")
            logger.error(f"Ошибка при добавлении задачи пользователем {user_id}.")

        # Сбрасываем все временные состояния
        user_states.pop((user_id, chat_id), None)
        user_states.pop(temp_text_key, None)
        # Передаём user_id в _refresh_tasks_menu
        _refresh_tasks_menu(chat_id, user_states, send_message_func, get_tasks_keyboard_func, user_id) # <--- ИЗМЕНЕНО

    # Обработка редактирования текста задачи
    elif current_state and current_state.startswith("waiting_for_task_text_edit_"):
        task_id = int(current_state.split("_")[-1])
        if text.strip():
            # Сохраняем новый текст и переходим к редактированию дедлайна
            # Передаём user_id в get_task_by_id
            task_info = get_task_by_id(user_id, task_id) # <--- ИЗМЕНЕНО
            if not task_info:
                 send_message_func(chat_id, f"Задача с ID {task_id} не найдена.")
                 user_states.pop((user_id, chat_id), None)
                 # Передаём user_id в _refresh_tasks_menu
                 _refresh_tasks_menu(chat_id, user_states, send_message_func, get_tasks_keyboard_func, user_id) # <--- ИЗМЕНЕНО
                 return

            # Передаём user_id в update_task
            success = update_task(user_id, task_id, new_text=text.strip()) # <--- ИЗМЕНЕНО
            if success:
                # Переходим к редактированию дедлайна
                user_states[(user_id, chat_id)] = f"waiting_for_task_deadline_edit_{task_id}"
                current_deadline = task_info['deadline'] # Берём дедлайн ДО обновления текста
                deadline_str = current_deadline if current_deadline else "Не установлен"
                message_text = f"Введите новый дедлайн для задачи {task_id} (например, '24.10'):\nТекущий дедлайн: {deadline_str}"
                # Отправляем сообщение с клавиатурой "Оставить текущую дату"
                # Используем функцию, переданную из bot.py
                if get_keep_current_deadline_keyboard_func:
                    keyboard = get_keep_current_deadline_keyboard_func(task_id, "tasks_menu")
                else:
                    # Если функция не установлена, используем стандартную клавиатуру с отменой
                    keyboard = get_cancel_inline_keyboard_func("tasks_menu")
                send_message_func(chat_id, message_text, keyboard, parse_mode=None)
                logger.info(f"Пользователь {user_id} обновил текст задачи (ID: {task_id}).")
            else:
                send_message_func(chat_id, f"Ошибка при обновлении текста задачи с ID {task_id}.")
                logger.error(f"Ошибка при обновлении текста задачи (ID: {task_id}) пользователем {user_id}.")
                # Возвращаемся в меню задач
                user_states.pop((user_id, chat_id), None)
                # Передаём user_id в _refresh_tasks_menu
                _refresh_tasks_menu(chat_id, user_states, send_message_func, get_tasks_keyboard_func, user_id) # <--- ИЗМЕНЕНО
        else:
            # Используем функцию из bot.py для клавиатуры "Оставить..." или отмены
            keyboard = get_cancel_inline_keyboard_func("tasks_menu")
            send_message_func(chat_id, "Текст задачи не может быть пустым. Попробуйте снова.", keyboard)
            return # Остаемся в состоянии ожидания

    # Обработка редактирования дедлайна задачи
    elif current_state and current_state.startswith("waiting_for_task_deadline_edit_"):
        task_id = int(current_state.split("_")[-1])
        # Используем парсер дат
        parsed_deadline = parse_deadline(text)
        if parsed_deadline:
            # Передаём user_id в update_task
            success = update_task(user_id, task_id, new_deadline=parsed_deadline) # <--- ИЗМЕНЕНО
            if success:
                send_message_func(chat_id, f"Дедлайн задачи с ID {task_id} обновлён.")
                logger.info(f"Пользователь {user_id} обновил дедлайн задачи (ID: {task_id}).")
            else:
                send_message_func(chat_id, f"Ошибка при обновлении дедлайна задачи с ID {task_id}.")
                logger.error(f"Ошибка при обновлении дедлайна задачи (ID: {task_id}) пользователем {user_id}.")
        else:
            # Используем функцию из bot.py для клавиатуры "Оставить..." или отмены
            if get_keep_current_deadline_keyboard_func:
                keyboard = get_keep_current_deadline_keyboard_func(task_id, "tasks_menu")
            else:
                # Если функция не установлена, используем стандартную клавиатуру с отменой
                keyboard = get_cancel_inline_keyboard_func("tasks_menu")
            send_message_func(chat_id, f"Неверный формат дедлайна: '{text}'. Используйте формат ДД.ММ (например, 24.10). Попробуйте снова.", keyboard, parse_mode=None)
            return # Остаемся в состоянии ожидания

        # После редактирования дедлайна, возвращаемся в меню задач
        user_states.pop((user_id, chat_id), None)
        # Передаём user_id в _refresh_tasks_menu
        _refresh_tasks_menu(chat_id, user_states, send_message_func, get_tasks_keyboard_func, user_id) # <--- ИЗМЕНЕНО

def _refresh_tasks_menu(chat_id, user_states, send_or_edit_func, get_keyboard_func, user_id, message_id=None): # Добавляем user_id
    """Вспомогательная функция для обновления меню задач."""
    # Передаём user_id в get_all_tasks
    tasks = get_all_tasks(user_id) # <--- ИЗМЕНЕНО
    tasks_text = format_tasks_list(tasks)
    keyboard = get_keyboard_func(tasks)
    if message_id:
        # Редактируем существующее сообщение
        send_or_edit_func(chat_id, message_id, tasks_text, keyboard)
    else:
        # Отправляем новое сообщение
        send_or_edit_func(chat_id, tasks_text, keyboard)

def _escape_html(text):
    """Экранирует символы, которые могут нарушить HTML-разметку."""
    if text is None:
        return ""
    return (text.replace("&", "&amp;")
                .replace("<", "<")
                .replace(">", ">"))
