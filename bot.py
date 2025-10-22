# bot.py
import requests
import json
import time
import threading # <-- ДОБАВЛЕНО
from datetime import datetime, timedelta # <-- ДОБАВЛЕНО
from config import BOT_TOKEN
from logger_config import get_logger
from handlers.base_handler import handle_callback_query, handle_message_input
from handlers.notes_handler import handle_notes_callback, handle_notes_message_input, set_cancel_keyboard_func
from handlers.tasks_handler import handle_tasks_callback, handle_tasks_message_input, set_cancel_keyboard_func as set_cancel_keyboard_func_tasks, set_keep_current_text_keyboard_func, set_keep_current_deadline_keyboard_func # Импортируем для задач
from handlers.reminders_handler import handle_reminders_callback, handle_reminders_message_input, set_cancel_keyboard_func as set_cancel_keyboard_func_reminders # Импортируем для напоминаний
from modules.notes import get_all_notes
from modules.tasks import get_all_tasks # Импортируем для генерации клавиатуры
from modules.reminders import get_all_reminders, delete_reminder # Импортируем для планировщика
from modules.reminders import format_reminders_list # Импортируем для генерации клавиатуры
from database import get_db # Импортируем для планировщика

logger = get_logger()

# --- Глобальные переменные ---
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
OFFSET_FILE = "bot_offset.txt"

# --- Состояния пользователей ---
# Используем (user_id, chat_id) как ключ для уникальности
user_states = {}

# --- Импортируем клавиатуры ---
# (Это плохая практика - держать их тут. Нужно в keyboards/)
def get_main_reply_keyboard():
    keyboard = [[{"text": "📝 Заметки"}, {"text": "✅ Задачи"}], [{"text": "⏰ Напоминания"}, {"text": "🌤️ Погода"}], [{"text": "⚙️ Настройки"}]]
    return {"keyboard": keyboard, "resize_keyboard": True, "one_time_keyboard": False}

def get_notes_inline_keyboard(notes):
    keyboard = []
    if notes:
        for note in notes:
            note_row = [{"text": f"✏️ {note['id']}", "callback_data": f"edit_note_{note['id']}"},
                        {"text": f"🗑️ {note['id']}", "callback_data": f"delete_note_{note['id']}"}]
            keyboard.append(note_row)
    keyboard.append([{"text": "➕ Добавить заметку", "callback_data": "add_note_prompt"}])
    return {"inline_keyboard": keyboard}

def get_tasks_inline_keyboard(tasks): # <-- Обновлённая функция: 3 кнопки
    keyboard = []
    if tasks:
        for task in tasks:
            # Определяем текст кнопки статуса
            status_text = "✅ Выполнено" if task['is_completed'] else "⏳ Не выполнено"
            status_callback = f"toggle_task_status_{task['id']}"
            # Кнопки для одной задачи (теперь 3 кнопки)
            task_row = [
                # Одна кнопка "✏️ [ID]" для редактирования
                {"text": f"✏️ {task['id']}", "callback_data": f"edit_task_{task['id']}"},
                {"text": status_text, "callback_data": status_callback},
                {"text": f"🗑️ {task['id']}", "callback_data": f"delete_task_{task['id']}"},
            ]
            keyboard.append(task_row)

    # Кнопка для добавления новой задачи
    keyboard.append([
        {"text": "➕ Добавить задачу", "callback_data": "add_task_prompt"}
    ])
    # Кнопка "❌ Отмена" убрана

    return {"inline_keyboard": keyboard}

def get_reminders_inline_keyboard(reminders): # <-- Новая функция для напоминаний
    keyboard = []
    if reminders:
        for reminder in reminders:
            recurring_text = "🔄 Ежедневное" if reminder['is_recurring'] else "📅 Однократное"
            recurring_callback = f"toggle_reminder_type_{reminder['id']}"
            # Кнопки для одного напоминания
            reminder_row = [
                {"text": recurring_text, "callback_data": recurring_callback},
                {"text": f"🗑️ {reminder['id']}", "callback_data": f"delete_reminder_{reminder['id']}"},
            ]
            keyboard.append(reminder_row)

    # Кнопка для добавления нового напоминания
    keyboard.append([
        {"text": "➕ Добавить напоминание", "callback_data": "add_reminder_prompt"}
    ])
    # Кнопка "❌ Отмена" убрана

    return {"inline_keyboard": keyboard}

def get_cancel_inline_keyboard(target_menu="notes_menu"):
    return {"inline_keyboard": [[{"text": "❌ Отмена", "callback_data": target_menu}]]}

def get_keep_current_text_keyboard(task_id, target_menu="tasks_menu"):
    """Клавиатура с кнопкой 'Оставить текущий текст'. Используется в tasks_handler."""
    # Эта функция будет вызываться из tasks_handler
    # Она генерирует клавиатуру с двумя кнопками: "Оставить..." и "❌ Отмена"
    # callback_data для первой кнопки: keep_current_text_{task_id}
    # callback_data для второй кнопки: target_menu (например, tasks_menu)
    return {"inline_keyboard": [[{"text": "Оставить текущий текст", "callback_data": f"keep_current_text_{task_id}"}], [{"text": "❌ Отмена", "callback_data": target_menu}]]}

def get_keep_current_deadline_keyboard(task_id, target_menu="tasks_menu"):
    """Клавиатура с кнопкой 'Оставить текущую дату'. Используется в tasks_handler."""
    # Эта функция будет вызываться из tasks_handler
    # Она генерирует клавиатуру с двумя кнопками: "Оставить..." и "❌ Отмена"
    # callback_data для первой кнопки: keep_current_deadline_{task_id}
    # callback_data для второй кнопки: target_menu (например, tasks_menu)
    return {"inline_keyboard": [[{"text": "Оставить текущую дату", "callback_data": f"keep_current_deadline_{task_id}"}], [{"text": "❌ Отмена", "callback_data": target_menu}]]}

def get_weather_inline_keyboard():
    return {"inline_keyboard": [[{"text": "❌ Отмена", "callback_data": "main_menu"}]]}

# --- Устанавливаем функцию для notes_handler, tasks_handler и reminders_handler ---
set_cancel_keyboard_func(get_cancel_inline_keyboard)
set_cancel_keyboard_func_tasks(get_cancel_inline_keyboard) # Устанавливаем для задач
set_cancel_keyboard_func_reminders(get_cancel_inline_keyboard) # Устанавливаем для напоминаний
# Устанавливаем функции клавиатуры "Оставить..." для tasks_handler
set_keep_current_text_keyboard_func(get_keep_current_text_keyboard)
set_keep_current_deadline_keyboard_func(get_keep_current_deadline_keyboard)

# --- ФУНКЦИИ ОТПРАВКИ СООБЩЕНИЙ ---
def send_message(chat_id, text, reply_markup=None, parse_mode=None): # <-- Добавлен parse_mode
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode: # <-- Добавляем parse_mode в payload, если он указан
        payload["parse_mode"] = parse_mode
    try:
        response = requests.post(url, json=payload)
        if not response.json().get("ok"):
            logger.error(f"Ошибка при отправке сообщения: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при отправке сообщения: {e}")
        return None

def edit_message_text(chat_id, message_id, text, reply_markup=None, parse_mode=None): # <-- Добавлен parse_mode
    url = f"{BASE_URL}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode: # <-- Добавляем parse_mode в payload, если он указан
        payload["parse_mode"] = parse_mode
    try:
        response = requests.post(url, json=payload)
        if not response.json().get("ok"):
            logger.error(f"Ошибка при редактировании сообщения: {response.json()}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при редактировании сообщения: {e}")

def answer_callback_query(callback_query_id, text=None):
    url = f"{BASE_URL}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    try:
        requests.post(url, json=payload)
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при ответе на callback_query: {e}")

# --- ЗАГРУЗКА/СОХРАНЕНИЕ OFFSET'а ---
def load_offset():
    try:
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return 0

def save_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

# --- ПЛАНИРОВЩИК НАПОМИНАНИЙ ---
def check_and_send_reminders(send_message_func, interval=30): # Интервал в секундах
    """
    Потоковая функция для проверки и отправки напоминаний.
    """
    logger.info("Планировщик напоминаний запущен.")
    db_scheduler = get_db() # Используем отдельный экземпляр DB для планировщика
    while True:
        try:
            now = datetime.now()
            # Получаем напоминания, время которых наступило
            # Используем новую функцию из database.py
            due_reminders = db_scheduler.get_reminders_for_time_check(now)

            for reminder in due_reminders:
                # reminder_time = datetime.fromisoformat(reminder['remind_at']) # Уже есть в результате запроса
                # Проверяем, наступило ли время напоминания
                # (Допускаем небольшую погрешность, так как проверка не постоянная)
                # Используем now-floor для избежания повторной отправки в пределах интервала проверки.
                check_time_floor = now - timedelta(seconds=interval)
                reminder_time = datetime.fromisoformat(reminder['remind_at'])
                if check_time_floor < reminder_time <= now:
                    user_id = reminder['user_id']
                    message_text = f"Напоминание: {reminder['text']}"
                    try:
                        # Отправляем сообщение
                        send_message_func(chat_id=user_id, text=message_text, reply_markup=None, parse_mode=None)
                        logger.info(f"Напоминание отправлено пользователю {user_id}: {reminder['text'][:30]}...")

                        # Обновляем время у ежедневного напоминания или удаляем однократное
                        if reminder['is_recurring']:
                            # Обновляем remind_at на следующий день
                            next_reminder_time = reminder_time + timedelta(days=1)
                            # Используем прямой вызов из db_manager для обновления
                            db_conn = db_scheduler.get_connection()
                            cursor = db_conn.cursor()
                            cursor.execute("UPDATE reminders SET remind_at = ? WHERE id = ? AND user_id = ?", (next_reminder_time.strftime('%Y-%m-%d %H:%M:%S'), reminder['id'], user_id))
                            db_conn.commit()
                            db_conn.close()
                            logger.debug(f"Время ежедневного напоминания (ID: {reminder['id']}) обновлено на {next_reminder_time.strftime('%Y-%m-%d %H:%M:%S')}.")
                        else:
                            # Удаляем однократное напоминание
                            # Используем функцию из modules/reminders
                            success = delete_reminder(user_id, reminder['id'])
                            if success:
                                logger.debug(f"Однократное напоминание (ID: {reminder['id']}) удалено из БД.")
                            else:
                                logger.error(f"Не удалось удалить однократное напоминание (ID: {reminder['id']}) из БД.")

                    except Exception as e:
                        logger.error(f"Ошибка отправки напоминания пользователю {user_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка в планировщике напоминаний: {e}")

        # Ждем заданный интервал перед следующей проверкой
        time.sleep(interval)

# --- ОБРАБОТКА ОБНОВЛЕНИЙ ---
def handle_update(update):
    """Обрабатывает одно обновление, распределяя по обработчикам."""
    if "callback_query" in update:
        callback_query = update["callback_query"]
        data = callback_query["data"]
        callback_query_id = callback_query["id"]
        answer_callback_query(callback_query_id)

        # Извлекаем user_id из callback_query
        user_id = callback_query["from"]["id"]
        chat_id = callback_query["message"]["chat"]["id"]
        message_id = callback_query["message"]["message_id"]

        module, result = handle_callback_query(callback_query, user_states, user_id)

        if module == "notes":
            # Передаём user_id
            handle_notes_callback(data, chat_id, message_id, user_id, user_states, send_message, edit_message_text, get_notes_inline_keyboard)
        elif module == "tasks": # <-- Добавлен обработчик задач
            # Передаём user_id
            handle_tasks_callback(data, chat_id, message_id, user_id, user_states, send_message, edit_message_text, get_tasks_inline_keyboard)
        elif module == "reminders": # <-- Добавлен обработчик напоминаний
            # Передаём user_id
            handle_reminders_callback(data, chat_id, message_id, user_id, user_states, send_message, edit_message_text, get_reminders_inline_keyboard)
        elif module == "main_menu":
            text, keyboard_type = result
            if keyboard_type == "main_keyboard":
                keyboard = get_main_reply_keyboard()
            else:
                keyboard = None # или дефолт
            send_message(chat_id, text, keyboard)

    elif "message" in update:
        message = update["message"]
        text = message.get("text", "")

        # Извлекаем user_id из message
        user_id = message["from"]["id"]
        chat_id = message["chat"]["id"]

        module, result = handle_message_input(message, user_states, user_id)

        if module == "notes":
            # Передаём user_id
            handle_notes_message_input(text, chat_id, user_id, user_states, send_message, edit_message_text, get_notes_inline_keyboard)
        elif module == "tasks": # <-- Добавлен обработчик ввода задач
            # Передаём user_id
            handle_tasks_message_input(text, chat_id, user_id, user_states, send_message, edit_message_text, get_tasks_inline_keyboard)
        elif module == "reminders": # <-- Добавлен обработчик ввода напоминаний
            # Передаём user_id
            handle_reminders_message_input(text, chat_id, user_id, user_states, send_message, edit_message_text, get_reminders_inline_keyboard)
        elif module == "main_reply":
            text_to_send, keyboard_type = result # <-- ПРАВИЛЬНАЯ РАСПАКОВКА
            # text_to_send = str
            # keyboard_type = str
            if keyboard_type == "notes_keyboard":
                # Передаём user_id в get_all_notes
                notes = get_all_notes(user_id) # <--- ИЗМЕНЕНО
                keyboard = get_notes_inline_keyboard(notes)
            elif keyboard_type == "tasks_keyboard": # <-- Добавлено для задач
                # Передаём user_id в get_all_tasks
                tasks = get_all_tasks(user_id) # <--- ИЗМЕНЕНО
                keyboard = get_tasks_inline_keyboard(tasks)
            elif keyboard_type == "reminders_keyboard": # <-- Добавлено для напоминаний
                # Передаём user_id в get_all_reminders
                reminders = get_all_reminders(user_id) # <--- ИЗМЕНЕНО
                keyboard = get_reminders_inline_keyboard(reminders)
            elif keyboard_type == "tasks_keyboard":
                keyboard = get_main_reply_keyboard() # Заглушка
            elif keyboard_type == "reminders_keyboard":
                keyboard = get_main_reply_keyboard() # Заглушка
            elif keyboard_type == "weather_keyboard":
                keyboard = get_weather_inline_keyboard()
            elif keyboard_type == "settings_keyboard":
                keyboard = get_main_reply_keyboard() # Заглушка
            elif keyboard_type == "main_keyboard":
                keyboard = get_main_reply_keyboard()
            else:
                keyboard = None # или дефолтная клавиатура

            send_message(chat_id, text_to_send, keyboard)
        elif module == "start":
            text, keyboard_type = result # <-- ПРАВИЛЬНАЯ РАСПАКОВКА
            if keyboard_type == "main_keyboard":
                keyboard = get_main_reply_keyboard()
            else:
                keyboard = None # или дефолт
            send_message(chat_id, text, keyboard)

def main():
    print("Бот запущен (long polling)") # <-- Сообщение при запуске
    logger.info("Бот запущен (long polling)")

    # --- ЗАПУСК ПЛАНИРОВЩИКА НАПОМИНАНИЙ ---
    # Создаем и запускаем поток для проверки напоминаний
    reminder_thread = threading.Thread(target=check_and_send_reminders, args=(send_message,), daemon=True) # daemon=True означает, что поток завершится при завершении основного скрипта
    reminder_thread.start()

    # --- ОСНОВНОЙ ЦИКЛ ---
    offset = load_offset()
    while True:
        try:
            url = f"{BASE_URL}/getUpdates"
            params = {"offset": offset + 1, "timeout": 30}
            response = requests.get(url, params=params)
            updates = response.json()

            if updates.get("ok"):
                for update in updates.get("result", []):
                    handle_update(update)
                    offset = update["update_id"]
                    save_offset(offset)
            else:
                logger.error(f"Ошибка API: {updates}")

        except requests.exceptions.Timeout:
            logger.debug("Таймаут запроса getUpdates.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети: {e}")
            time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Бот остановлен пользователем.")
            break
        except Exception as e:
            logger.error(f"Непредвиденная ошибка: {e}")
            time.sleep(10)

    # Ожидание завершения потока (необязательно, так как daemon=True)
    # reminder_thread.join()

if __name__ == '__main__':
    main()