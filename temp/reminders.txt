# modules/reminders.py
from logger_config import get_logger
from database import get_db
from datetime import datetime

logger = get_logger()
db = get_db() # Получаем глобальный экземпляр DatabaseManager

def get_all_reminders(user_id):
    """
    Получает все активные напоминания из базы данных для конкретного пользователя.
    """
    try:
        reminders = db.get_all_reminders(user_id) # Передаём user_id
        logger.debug(f"Получено {len(reminders)} напоминаний из БД для user_id {user_id}.")
        return reminders
    except Exception as e:
        logger.error(f"Ошибка при получении напоминаний для user_id {user_id}: {e}")
        return []

def add_reminder(user_id, text, remind_at, is_recurring=False):
    """
    Добавляет новое напоминание в базу данных для конкретного пользователя.
    """
    if not text or not text.strip():
        logger.warning(f"Попытка добавить напоминание с пустым текстом для user_id {user_id}.")
        return None # Возвращаем None, если текст пуст

    try:
        reminder_id = db.add_reminder(user_id, text.strip(), remind_at, is_recurring) # Убираем лишние пробелы, передаём user_id
        logger.info(f"Добавлено новое напоминание (ID: {reminder_id}) для user_id {user_id}.")
        return reminder_id
    except Exception as e:
        logger.error(f"Ошибка при добавлении напоминания для user_id {user_id}: {e}")
        return None

def update_reminder_type(user_id, reminder_id, is_recurring):
    """
    Обновляет тип напоминания (однократное/ежедневное) по ID для конкретного пользователя.
    """
    try:
        db.update_reminder_type(user_id, reminder_id, is_recurring) # Передаём user_id
        type_str = "ежедневное" if is_recurring else "однократное"
        logger.info(f"Тип напоминания (ID: {reminder_id}) изменён на {type_str} для user_id {user_id}.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при изменении типа напоминания (ID: {reminder_id}) для user_id {user_id}: {e}")
        return False

def delete_reminder(user_id, reminder_id):
    """
    Удаляет напоминание по ID для конкретного пользователя.
    """
    try:
        db.delete_reminder(user_id, reminder_id) # Передаём user_id
        logger.info(f"Напоминание (ID: {reminder_id}) удалено для user_id {user_id}.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении напоминания (ID: {reminder_id}) для user_id {user_id}: {e}")
        return False

def get_reminder_by_id(user_id, reminder_id):
    """
    Получает информацию о напоминании по ID для конкретного пользователя. Полезно для проверки/изменения.
    """
    try:
        all_reminders = db.get_all_reminders(user_id) # Передаём user_id
        for reminder in all_reminders:
            if reminder['id'] == reminder_id:
                return reminder
        logger.warning(f"Напоминание с ID {reminder_id} не найдено для user_id {user_id}.")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении напоминания (ID: {reminder_id}) для user_id {user_id}: {e}")
        return None

# Пример функции для форматирования списка напоминаний в строку для отправки пользователю
def format_reminders_list(reminders):
    """
    Форматирует список напоминаний в строку для отправки пользователю.
    """
    if not reminders:
        return "У вас пока нет активных напоминаний."

    formatted_lines = []
    for reminder in reminders:
        recurring_marker = " [ЕЖЕДНЕВНО]" if reminder['is_recurring'] else ""
        # Обрезаем текст до 100 символов, но не добавляем многоточие
        text_display = (reminder['text'] or "")[:100] # Используем пустую строку, если None
        formatted_lines.append(f"{reminder['id']}. {text_display} ({reminder['remind_at']}){recurring_marker}")

    return "\n".join(formatted_lines)
