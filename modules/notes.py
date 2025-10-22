# modules/notes.py
from logger_config import get_logger
from database import get_db

logger = get_logger()
db = get_db() # Получаем глобальный экземпляр DatabaseManager

def get_all_notes(user_id):
    """
    Получает все заметки из базы данных для конкретного пользователя.
    """
    try:
        notes = db.get_all_notes(user_id) # Передаём user_id
        logger.debug(f"Получено {len(notes)} заметок из БД для user_id {user_id}.")
        return notes
    except Exception as e:
        logger.error(f"Ошибка при получении заметок для user_id {user_id}: {e}")
        return []

def add_note(user_id, text):
    """
    Добавляет новую заметку в базу данных для конкретного пользователя.
    """
    if not text or not text.strip():
        logger.warning(f"Попытка добавить заметку с пустым текстом для user_id {user_id}.")
        return None

    try:
        note_id = db.add_note(user_id, text.strip())
        logger.info(f"Добавлена новая заметка (ID: {note_id}) для user_id {user_id}.")
        return note_id
    except Exception as e:
        logger.error(f"Ошибка при добавлении заметки для user_id {user_id}: {e}")
        return None

def update_note(user_id, note_id, new_text):
    """
    Обновляет текст заметки по ID для конкретного пользователя.
    """
    if not new_text or not new_text.strip():
        logger.warning(f"Попытка обновить заметку (ID: {note_id}) с пустым текстом для user_id {user_id}.")
        return False

    try:
        db.update_note(user_id, note_id, new_text.strip())
        logger.info(f"Заметка (ID: {note_id}) обновлена для user_id {user_id}.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении заметки (ID: {note_id}) для user_id {user_id}: {e}")
        return False

def delete_note(user_id, note_id):
    """
    Удаляет заметку по ID для конкретного пользователя.
    """
    try:
        db.delete_note(user_id, note_id)
        logger.info(f"Заметка (ID: {note_id}) удалена для user_id {user_id}.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении заметки (ID: {note_id}) для user_id {user_id}: {e}")
        return False

def format_notes_list(notes):
    """
    Форматирует список заметок в строку для отправки пользователю.
    """
    if not notes:
        return "У вас пока нет заметок."

    formatted_lines = []
    for note in notes:
        # Проверяем, что note['text'] не None
        text_display = (note['text'] or "")[:100] # Используем пустую строку, если None
        formatted_lines.append(f"{note['id']}. {text_display}")

    return "\n".join(formatted_lines)

def get_note_text_by_id(user_id, note_id):
    """
    Получает текст заметки по ID для конкретного пользователя. Полезно для редактирования.
    """
    try:
        all_notes = db.get_all_notes(user_id) # Передаём user_id
        for note in all_notes:
            if note['id'] == note_id:
                return note['text']
        logger.warning(f"Заметка с ID {note_id} не найдена для user_id {user_id}.")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении заметки (ID: {note_id}) для user_id {user_id}: {e}")
        return None
