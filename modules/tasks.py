# modules/tasks.py
from logger_config import get_logger
from database import get_db
from datetime import datetime

logger = get_logger()
db = get_db() # Получаем глобальный экземпляр DatabaseManager

def get_all_tasks(user_id):
    """
    Получает все задачи из базы данных для конкретного пользователя.
    """
    try:
        tasks = db.get_all_tasks(user_id) # Передаём user_id
        logger.debug(f"Получено {len(tasks)} задач из БД для user_id {user_id}.")
        return tasks
    except Exception as e:
        logger.error(f"Ошибка при получении задач для user_id {user_id}: {e}")
        return []

def add_task(user_id, text, deadline=None):
    """
    Добавляет новую задачу в базу данных для конкретного пользователя.
    """
    if not text or not text.strip():
        logger.warning(f"Попытка добавить задачу с пустым текстом для user_id {user_id}.")
        return None # Возвращаем None, если текст пуст

    try:
        task_id = db.add_task(user_id, text.strip(), deadline) # Убираем лишние пробелы, передаём user_id
        logger.info(f"Добавлена новая задача (ID: {task_id}) для user_id {user_id}.")
        return task_id
    except Exception as e:
        logger.error(f"Ошибка при добавлении задачи для user_id {user_id}: {e}")
        return None

def update_task(user_id, task_id, new_text=None, new_deadline=None, is_completed=None):
    """
    Обновляет поля задачи по ID для конкретного пользователя.
    """
    # Проверяем, есть ли что обновлять
    if new_text is None and new_deadline is None and is_completed is None:
        logger.warning(f"Попытка обновить задачу (ID: {task_id}) без изменений для user_id {user_id}.")
        return False

    try:
        db.update_task(user_id, task_id, new_text=new_text, new_deadline=new_deadline, is_completed=is_completed) # Передаём user_id
        logger.info(f"Задача (ID: {task_id}) обновлена для user_id {user_id}.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении задачи (ID: {task_id}) для user_id {user_id}: {e}")
        return False

def delete_task(user_id, task_id):
    """
    Удаляет задачу по ID для конкретного пользователя.
    """
    try:
        db.delete_task(user_id, task_id) # Передаём user_id
        logger.info(f"Задача (ID: {task_id}) удалена для user_id {user_id}.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении задачи (ID: {task_id}) для user_id {user_id}: {e}")
        return False

def get_task_by_id(user_id, task_id):
    """
    Получает информацию о задаче по ID для конкретного пользователя. Полезно для редактирования.
    """
    try:
        all_tasks = db.get_all_tasks(user_id) # Передаём user_id
        for task in all_tasks:
            if task['id'] == task_id:
                return task
        logger.warning(f"Задача с ID {task_id} не найдена для user_id {user_id}.")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении задачи (ID: {task_id}) для user_id {user_id}: {e}")
        return None

def check_overdue_tasks(user_id):
    """
    Проверяет, есть ли у пользователя невыполненные задачи с дедлайном на сегодня.
    Возвращает список ID таких задач.
    """
    try:
        all_tasks = db.get_all_tasks(user_id) # Передаём user_id
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        overdue_task_ids = []
        for task in all_tasks:
            if not task['is_completed'] and task['deadline']:
                try:
                    deadline_dt = datetime.fromisoformat(task['deadline'])
                    if today_start <= deadline_dt <= today_end:
                        overdue_task_ids.append(task['id'])
                except ValueError:
                    # Если формат даты неправильный, логируем и продолжаем
                    logger.warning(f"Неправильный формат дедлайна для задачи {task['id']} (user {user_id}): {task['deadline']}")
        logger.debug(f"Найдено {len(overdue_task_ids)} просроченных задач для user {user_id}: {overdue_task_ids}")
        return overdue_task_ids
    except Exception as e:
        logger.error(f"Ошибка при проверке просроченных задач для user {user_id}: {e}")
        return []

# Пример функции для форматирования списка задач в строку для отправки пользователю
def format_tasks_list(tasks):
    """
    Форматирует список задач в строку для отправки пользователю.
    Помечает просроченные невыполненные задачи.
    """
    if not tasks:
        return "У вас пока нет задач."

    formatted_lines = []
    now = datetime.now()
    for task in tasks:
        status = "✅" if task['is_completed'] else "⏳"
        # Проверяем просрочку
        is_overdue = False
        deadline_dt = None
        if task['deadline']:
            try:
                deadline_dt = datetime.fromisoformat(task['deadline'])
                if not task['is_completed'] and deadline_dt < now:
                    is_overdue = True
            except ValueError:
                # Если формат даты неправильный, логируем и продолжаем
                logger.warning(f"Неправильный формат дедлайна для задачи {task['id']}: {task['deadline']}")

        overdue_marker = " [ПРОСРОЧЕНО]" if is_overdue else ""
        deadline_str = f" ({deadline_dt.strftime('%d.%m.%Y %H:%M')})" if deadline_dt else " (без дедлайна)"
        # Обрезаем текст до 100 символов, но не добавляем многоточие
        text_display = (task['text'] or "")[:100] # Используем пустую строку, если None
        formatted_lines.append(f"{status} {task['id']}. {text_display}{deadline_str}{overdue_marker}")

    return "\n".join(formatted_lines)
