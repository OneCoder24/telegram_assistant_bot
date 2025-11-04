# handlers/notes_handler.py
from logger_config import get_logger
from modules.notes import get_all_notes, add_note, update_note, delete_note, format_notes_list, get_note_text_by_id
from datetime import datetime

logger = get_logger()

def handle_notes_callback(data, chat_id, message_id, user_id, user_states, send_message_func, edit_message_text_func, get_notes_keyboard_func): # user_id теперь передаётся
    """Обрабатывает callback_query, связанные с заметками."""
    # Сброс состояния при возврате в меню ЗАМЕТОК (не в главное меню!)
    if data == 'notes_menu':
        # Сбрасываем любое состояние, связанное с заметками для (user_id, chat_id)
        if user_states.get((user_id, chat_id)) and user_states[(user_id, chat_id)].startswith("waiting_for_note_"):
            user_states.pop((user_id, chat_id), None)
            # Отправляем сообщение, что действие отменено
            send_message_func(chat_id, "Действие с заметкой отменено.")
            logger.info(f"Действие с заметкой отменено пользователем {user_id} через inline-кнопку.")

    elif data.startswith("edit_note_"):
        note_id = int(data.split("_")[2])
        # Передаём user_id в get_note_text_by_id
        note_text = get_note_text_by_id(user_id, note_id) # <--- ИЗМЕНЕНО
        if note_text is not None:
            # Устанавливаем состояние ожидания нового текста для редактирования
            user_states[(user_id, chat_id)] = f"waiting_for_note_edit_text_{note_id}"
            # Отправляем сообщение с просьбой ввести новый текст и старым текстом в формате кода (HTML <code>)
            escaped_text = _escape_html(note_text) # Экранируем HTML-символы в старом тексте
            message_text = f"Введите новый текст для заметки {note_id}:\nТекущий текст:\n<code>{escaped_text}</code>"
            send_message_func(chat_id, message_text, get_cancel_inline_keyboard_func("notes_menu"), parse_mode='HTML')
        else:
            send_message_func(chat_id, f"Заметка с ID {note_id} не найдена.")
            # Передаём user_id в _refresh_notes_menu
            _refresh_notes_menu(chat_id, user_states, send_message_func, get_notes_keyboard_func, user_id) # <--- ИЗМЕНЕНО

    elif data.startswith("delete_note_"):
        note_id = int(data.split("_")[2])
        # Передаём user_id в delete_note
        success = delete_note(user_id, note_id) # <--- ИЗМЕНЕНО
        if success:
            send_message_func(chat_id, f"Заметка с ID {note_id} удалена.")
            logger.info(f"Пользователь {user_id} удалил заметку (ID: {note_id}).")
        else:
            send_message_func(chat_id, f"Ошибка при удалении заметки с ID {note_id}.")
            logger.error(f"Ошибка при удалении заметки (ID: {note_id}) пользователем {user_id}.")

        # Передаём user_id в _refresh_notes_menu
        _refresh_notes_menu(chat_id, user_states, send_message_func, get_notes_keyboard_func, user_id) # <--- ИЗМЕНЕНО

    elif data == 'add_note_prompt':
        # Устанавливаем состояние пользователя
        user_states[(user_id, chat_id)] = "waiting_for_note_text"
        # Отправляем НОВОЕ сообщение с просьбой ввести текст и inline-клавиатурой "Отмена"
        send_message_func(chat_id, "Введите текст новой заметки:", get_cancel_inline_keyboard_func("notes_menu"))

    # elif data == 'notes_menu': # Уже обработано выше
    #     _refresh_notes_menu(chat_id, user_states, edit_message_text_func, get_notes_keyboard_func, message_id=message_id, user_id=user_id)


def handle_notes_message_input(text, chat_id, user_id, user_states, send_message_func, edit_message_text_func, get_notes_keyboard_func): # user_id теперь передаётся
    """Обрабатывает текстовые сообщения для заметок."""
    current_state = user_states.get((user_id, chat_id))

    if current_state == "waiting_for_note_text":
        if text.strip(): # Проверяем, что текст не пустой
            note_text = text
            # Передаём user_id в add_note
            note_id = add_note(user_id, note_text) # <--- ИЗМЕНЕНО
            if note_id: # Проверяем, успешно ли добавилась
                send_message_func(chat_id, f"Заметка '{note_text[:30]}...' добавлена (ID: {note_id}).")
                logger.info(f"Пользователь {user_id} добавил заметку (ID: {note_id}).")
            else:
                send_message_func(chat_id, "Ошибка при добавлении заметки.")
                logger.error(f"Ошибка при добавлении заметки пользователем {user_id}.")
        else:
            send_message_func(chat_id, "Текст заметки не может быть пустым. Попробуйте снова.", get_cancel_inline_keyboard_func("notes_menu"))
            return # Остаемся в состоянии ожидания

        # После добавления (успешного или неудачного, если текст был не пустой) - возвращаемся в меню заметок
        user_states.pop((user_id, chat_id), None) # Сбрасываем состояние
        # Передаём user_id в _refresh_notes_menu
        _refresh_notes_menu(chat_id, user_states, send_message_func, get_notes_keyboard_func, user_id) # <--- ИЗМЕНЕНО
        return # Выходим

    # Обработка редактирования заметки
    if current_state and current_state.startswith("waiting_for_note_edit_text_"):
        note_id = int(current_state.split("_")[-1]) # Извлекаем ID из "waiting_for_note_edit_text_123"
        if text.strip(): # Проверяем, что текст не пустой
            # Передаём user_id в update_note
            success = update_note(user_id, note_id, text.strip()) # <--- ИЗМЕНЕНО
            if success:
                send_message_func(chat_id, f"Заметка с ID {note_id} обновлена.")
                logger.info(f"Пользователь {user_id} обновил заметку (ID: {note_id}).")
            else:
                send_message_func(chat_id, f"Ошибка при обновлении заметки с ID {note_id}.")
                logger.error(f"Ошибка при обновлении заметки (ID: {note_id}) пользователем {user_id}.")
        else:
            send_message_func(chat_id, "Текст заметки не может быть пустым. Попробуйте снова.", get_cancel_inline_keyboard_func("notes_menu"))
            return # Остаемся в состоянии ожидания

        # После редактирования (успешного или неудачного, если текст был не пустой) - возвращаемся в меню заметок
        user_states.pop((user_id, chat_id), None) # Сбрасываем состояние
        # Передаём user_id в _refresh_notes_menu
        _refresh_notes_menu(chat_id, user_states, send_message_func, get_notes_keyboard_func, user_id) # <--- ИЗМЕНЕНО
        return # Выходим

# ... (остальные функции handlers/notes_handler.py, _refresh_notes_menu, _escape_html, set_cancel_keyboard_func) ...

def _refresh_notes_menu(chat_id, user_states, send_or_edit_func, get_keyboard_func, user_id): # Добавляем user_id
    """Вспомогательная функция для обновления меню заметок."""
    # Передаём user_id в get_all_notes
    notes = get_all_notes(user_id) # <--- ИЗМЕНЕНО
    notes_text = format_notes_list(notes)
    keyboard = get_keyboard_func(notes)
    # ... (логика отправки/редактирования) ...
    # Пример: send_or_edit_func(chat_id, notes_text, keyboard)
    # Если используется edit_message_text_func, нужно передать message_id
    # send_or_edit_func(chat_id, message_id, notes_text, keyboard)

def _escape_html(text):
    """Экранирует символы, которые могут нарушить HTML-разметку."""
    if text is None:
        return ""
    return (text.replace("&", "&amp;")
                .replace("<", "<")
                .replace(">", ">"))

# Вспомогательная функция для клавиатуры отмены, нужно будет получить из bot.py
get_cancel_inline_keyboard_func = None
def set_cancel_keyboard_func(func):
    global get_cancel_inline_keyboard_func
    get_cancel_inline_keyboard_func = func