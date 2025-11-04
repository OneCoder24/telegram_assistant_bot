# handlers/reminders_handler.py
from logger_config import get_logger
from modules.reminders import get_all_reminders, add_reminder, update_reminder_type, delete_reminder, get_reminder_by_id, format_reminders_list
from utils.reminders_datetime_parser import parse_reminder_time
from datetime import datetime

logger = get_logger()

def handle_reminders_callback(data, chat_id, message_id, user_id, user_states, send_message_func, edit_message_text_func, get_reminders_keyboard_func): # user_id теперь передаётся
    """Обрабатывает callback_query, связанные с напоминаниями."""
    if data.startswith("toggle_reminder_type_"):
        reminder_id = int(data.split("_")[3])
        # Передаём user_id в get_reminder_by_id
        reminder_info = get_reminder_by_id(user_id, reminder_id) # <--- ИЗМЕНЕНО
        if reminder_info is not None:
            new_type = not reminder_info['is_recurring']
            # Передаём user_id в update_reminder_type
            success = update_reminder_type(user_id, reminder_id, new_type) # <--- ИЗМЕНЕНО
            if success:
                type_text = "ежедневное" if new_type else "однократное"
                send_message_func(chat_id, f"Напоминание с ID {reminder_id} теперь {type_text}.")
                logger.info(f"Пользователь {user_id} изменил тип напоминания (ID: {reminder_id}) на {type_text}.")
            else:
                send_message_func(chat_id, f"Ошибка при изменении типа напоминания с ID {reminder_id}.")
                logger.error(f"Ошибка при изменении типа напоминания (ID: {reminder_id}) пользователем {user_id}.")
        else:
            send_message_func(chat_id, f"Напоминание с ID {reminder_id} не найдено.")

        # Передаём user_id в _refresh_reminders_menu
        _refresh_reminders_menu(chat_id, user_states, send_message_func, get_reminders_keyboard_func, user_id) # <--- ИЗМЕНЕНО

    elif data.startswith("delete_reminder_"):
        reminder_id = int(data.split("_")[2])
        # Передаём user_id в delete_reminder
        success = delete_reminder(user_id, reminder_id) # <--- ИЗМЕНЕНО
        if success:
            send_message_func(chat_id, f"Напоминание с ID {reminder_id} удалено.")
            logger.info(f"Пользователь {user_id} удалил напоминание (ID: {reminder_id}).")
        else:
            send_message_func(chat_id, f"Ошибка при удалении напоминания с ID {reminder_id}.")
            logger.error(f"Ошибка при удалении напоминания (ID: {reminder_id}) пользователем {user_id}.")

        # Передаём user_id в _refresh_reminders_menu
        _refresh_reminders_menu(chat_id, user_states, send_message_func, get_reminders_keyboard_func, user_id) # <--- ИЗМЕНЕНО

    elif data == 'add_reminder_prompt':
        # Отправляем подсказку по форматам
        formats_help = (
            "Введите текст напоминания и время в одном из следующих форматов:\n"
            "• 5 мин\n"
            "• 1 ч\n"
            "• 18:15 (сегодня в 18:15)\n"
            "• завтра 10:00\n"
            "• 15 октября (в 23:55, время по умолчанию из настроек)\n"
        )
        send_message_func(chat_id, formats_help)
        # Устанавливаем состояние ожидания текста и времени нового напоминания
        user_states[(user_id, chat_id)] = "waiting_for_reminder_text_and_time"
        # Отправляем НОВОЕ сообщение с просьбой ввести текст и время
        send_message_func(chat_id, "Введите текст напоминания и время:", get_cancel_inline_keyboard_func("reminders_menu"))

    elif data == 'reminders_menu':
        # Сброс состояния при возврате в меню
        if user_states.get((user_id, chat_id)) and user_states[(user_id, chat_id)].startswith("waiting_for_reminder_"):
            user_states.pop((user_id, chat_id), None)
            send_message_func(chat_id, "Добавление напоминания отменено.")
            logger.info(f"Добавление напоминания отменено пользователем {user_id} через inline-кнопку.")

        # Передаём user_id в _refresh_reminders_menu
        _refresh_reminders_menu(chat_id, user_states, edit_message_text_func, get_reminders_keyboard_func, user_id, message_id=message_id) # <--- ИЗМЕНЕНО

def handle_reminders_message_input(text, chat_id, user_id, user_states, send_message_func, edit_message_text_func, get_reminders_keyboard_func): # user_id теперь передаётся
    """Обрабатывает текстовые сообщения для напоминаний."""
    current_state = user_states.get((user_id, chat_id))

    # Обработка добавления нового напоминания
    if current_state == "waiting_for_reminder_text_and_time":
        # Пытаемся распарсить время из всего введённого текста
        parsed_time = parse_reminder_time(text)
        if parsed_time:
            # Всё, что идёт до времени, считаем текстом напоминания
            # Это грубое извлечение, можно улучшить регулярными выражениями
            # Пока что просто уберём время из конца строки
            import re
            # Паттерн для времени HH:MM
            time_pattern = r'\b\d{1,2}:\d{2}\b'
            # Паттерн для "N мин" / "N ч" / "N час"
            time_delta_pattern = r'\b\d+\s*(мин|ч|час)\b'
            # Паттерн для "DD месяц"
            date_pattern = r'\b\d{1,2}\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\b'
            # Паттерн для "завтра HH:MM"
            tomorrow_pattern = r'\bзавтра\s+\d{1,2}:\d{2}\b'

            # Объединяем паттерны
            full_pattern = f'({time_pattern}|{time_delta_pattern}|{date_pattern}|{tomorrow_pattern})$'
            match = re.search(full_pattern, text.strip(), re.IGNORECASE)
            if match:
                time_part = match.group(1).strip()
                text_part = text[:match.start()].strip()
                if not text_part:
                    # Если текст до времени пуст, используем всё, кроме времени
                    text_part = text.replace(time_part, '').strip()
            else:
                # Если формат не определён, используем весь текст как текст напоминания
                text_part = text.strip()

            if text_part:
                reminder_text = text_part
                # Передаём user_id в add_reminder
                reminder_id = add_reminder(user_id, reminder_text, parsed_time) # <--- ИЗМЕНЕНО
                if reminder_id:
                    send_message_func(chat_id, f"Напоминание '{reminder_text[:30]}...' добавлено на {parsed_time}.")
                    logger.info(f"Пользователь {user_id} добавил напоминание (ID: {reminder_id}) на {parsed_time}.")
                else:
                    send_message_func(chat_id, "Ошибка при добавлении напоминания.")
                    logger.error(f"Ошибка при добавлении напоминания пользователем {user_id}.")
            else:
                send_message_func(chat_id, "Не удалось извлечь текст напоминания. Попробуйте снова.", get_cancel_inline_keyboard_func("reminders_menu"))
                return # Остаемся в состоянии ожидания
        else:
            send_message_func(chat_id, f"Неверный формат времени: '{text}'. Используйте подсказки. Попробуйте снова.", get_cancel_inline_keyboard_func("reminders_menu"))
            return # Остаемся в состоянии ожидания

        # После добавления (успешного или неудачного) - возвращаемся в меню напоминаний
        user_states.pop((user_id, chat_id), None) # Сбрасываем состояние
        # Передаём user_id в _refresh_reminders_menu
        _refresh_reminders_menu(chat_id, user_states, send_message_func, get_reminders_keyboard_func, user_id) # <--- ИЗМЕНЕНО
        return # Выходим

def _refresh_reminders_menu(chat_id, user_states, send_or_edit_func, get_keyboard_func, user_id, message_id=None): # Добавляем user_id
    """Вспомогательная функция для обновления меню напоминаний."""
    # Передаём user_id в get_all_reminders
    reminders = get_all_reminders(user_id) # <--- ИЗМЕНЕНО
    reminders_text = format_reminders_list(reminders)
    keyboard = get_keyboard_func(reminders)
    if message_id:
        # Редактируем существующее сообщение
        send_or_edit_func(chat_id, message_id, reminders_text, keyboard)
    else:
        # Отправляем новое сообщение
        send_or_edit_func(chat_id, reminders_text, keyboard)

# Вспомогательная функция для клавиатуры отмены, нужно будет получить из bot.py
get_cancel_inline_keyboard_func = None
def set_cancel_keyboard_func(func):
    global get_cancel_inline_keyboard_func
    get_cancel_inline_keyboard_func = func