# test_db.py
import os
import sys
# Добавляем путь к корню проекта, чтобы можно было импортировать из config и database
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATABASE_PATH, LOG_DIR
from database import get_db
from logger_config import get_logger

logger = get_logger()

def test_database():
    print("--- Тестирование модуля базы данных ---")
    print(f"Путь к базе данных: {DATABASE_PATH}")
    print(f"Путь к папке логов: {LOG_DIR}")

    # Проверяем, существует ли база данных (она должна создаться при импорте database)
    if os.path.exists(DATABASE_PATH):
        print(f"[OK] Файл базы данных существует: {DATABASE_PATH}")
        logger.info(f"Файл базы данных подтвержден: {DATABASE_PATH}")
    else:
        print(f"[ERROR] Файл базы данных НЕ существует: {DATABASE_PATH}")
        logger.error(f"Файл базы данных НЕ найден: {DATABASE_PATH}")
        return

    # Получаем экземпляр менеджера базы данных
    db = get_db()

    # --- Тестируем Заметки ---
    print("\n--- Тестируем Заметки ---")
    initial_notes = db.get_all_notes()
    print(f"Начальное количество заметок: {len(initial_notes)}")

    test_note_text = "Тестовая заметка от test_db.py"
    note_id = db.add_note(test_note_text)
    print(f"Добавлена заметка с ID: {note_id}")

    updated_notes = db.get_all_notes()
    print(f"Количество заметок после добавления: {len(updated_notes)}")

    if updated_notes and updated_notes[0]['text'] == test_note_text:
        print("[OK] Заметка успешно добавлена и найдена.")
        logger.info("Тест заметки пройден успешно.")
    else:
        print("[ERROR] Заметка не была добавлена корректно.")
        logger.error("Тест заметки не удался.")

    # Удаляем тестовую заметку
    if note_id:
        db.delete_note(note_id)
        print(f"Тестовая заметка (ID: {note_id}) удалена.")

    # --- Тестируем Задачи ---
    print("\n--- Тестируем Задачи ---")
    initial_tasks = db.get_all_tasks()
    print(f"Начальное количество задач: {len(initial_tasks)}")

    test_task_text = "Тестовая задача от test_db.py"
    task_deadline = "2025-12-31 23:59:59"
    task_id = db.add_task(test_task_text, task_deadline)
    print(f"Добавлена задача с ID: {task_id}")

    updated_tasks = db.get_all_tasks()
    print(f"Количество задач после добавления: {len(updated_tasks)}")

    if updated_tasks and updated_tasks[0]['text'] == test_task_text and updated_tasks[0]['deadline'] == task_deadline:
        print("[OK] Задача успешно добавлена и найдена.")
        logger.info("Тест задачи пройден успешно.")
    else:
        print("[ERROR] Задача не была добавлена корректно.")
        logger.error("Тест задачи не удался.")

    # Удаляем тестовую задачу
    if task_id:
        db.delete_task(task_id)
        print(f"Тестовая задача (ID: {task_id}) удалена.")

    # --- Тестируем Напоминания ---
    print("\n--- Тестируем Напоминания ---")
    initial_reminders = db.get_all_reminders()
    print(f"Начальное количество напоминаний: {len(initial_reminders)}")

    test_reminder_text = "Тестовое напоминание от test_db.py"
    test_reminder_time = "2025-10-20 10:00:00" # Завтра в 10:00
    reminder_id = db.add_reminder(test_reminder_text, test_reminder_time, is_recurring=False)
    print(f"Добавлено напоминание с ID: {reminder_id}")

    updated_reminders = db.get_all_reminders()
    print(f"Количество напоминаний после добавления: {len(updated_reminders)}")

    if updated_reminders and updated_reminders[0]['text'] == test_reminder_text and updated_reminders[0]['remind_at'] == test_reminder_time:
        print("[OK] Напоминание успешно добавлено и найдено.")
        logger.info("Тест напоминания пройден успешно.")
    else:
        print("[ERROR] Напоминание не было добавлено корректно.")
        logger.error("Тест напоминания не удался.")

    # Меняем тип напоминания на ежедневное и проверяем
    if reminder_id:
        db.update_reminder_type(reminder_id, is_recurring=True)
        updated_reminders_after_change = db.get_all_reminders()
        found_reminder = next((r for r in updated_reminders_after_change if r['id'] == reminder_id), None)
        if found_reminder and found_reminder['is_recurring']:
            print("[OK] Тип напоминания успешно изменён на ежедневное.")
            logger.info("Тест изменения типа напоминания пройден успешно.")
        else:
            print("[ERROR] Тип напоминания не был изменён корректно.")
            logger.error("Тест изменения типа напоминания не удался.")

        # Удаляем тестовое напоминание
        db.delete_reminder(reminder_id)
        print(f"Тестовое напоминание (ID: {reminder_id}) удалено.")

    # --- Тестируем Настройки ---
    print("\n--- Тестируем Настройки ---")
    settings = db.get_settings()
    if settings:
        print(f"[OK] Настройки успешно получены: {settings}")
        logger.info("Тест получения настроек пройден успешно.")
    else:
        print("[ERROR] Не удалось получить настройки.")
        logger.error("Тест получения настроек не удался.")

    # Обновляем настройку и проверяем
    new_city = "TestCityForDB"
    db.update_setting('main_city', new_city)
    updated_settings = db.get_settings()
    if updated_settings and updated_settings['main_city'] == new_city:
        print(f"[OK] Настройка успешно обновлена. Новый город: {updated_settings['main_city']}")
        logger.info("Тест обновления настроек пройден успешно.")
        # Восстанавливаем значение по умолчанию
        db.update_setting('main_city', 'Moscow')
        print("Настройка города восстановлена в 'Moscow'.")
    else:
        print("[ERROR] Настройка не была обновлена корректно.")
        logger.error("Тест обновления настроек не удался.")

    print("\n--- Тестирование завершено ---")

if __name__ == "__main__":
    test_database()
