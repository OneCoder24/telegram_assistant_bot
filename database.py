# database.py
import sqlite3
import os
from datetime import datetime
from config import DATABASE_PATH

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_tables()

    def get_connection(self):
        """Возвращает соединение с базой данных."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_tables(self):
        """Создает таблицы, если они не существуют."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                deadline TEXT,
                is_completed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                is_recurring BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Обновляем таблицу settings: используем user_id как PRIMARY KEY
        # main_city будет использоваться как default_city для погоды
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                main_city TEXT DEFAULT 'Moscow', -- Используется как default_city для погоды
                daily_weather_time TEXT, -- HH:MM
                daily_weather_enabled BOOLEAN DEFAULT 0,
                master_message_time TEXT, -- HH:MM
                master_message_enabled BOOLEAN DEFAULT 0
            )
        ''')

        conn.commit()
        conn.close()

    # --- CRUD для Заметок ---
    def add_note(self, user_id, text):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO notes (user_id, text) VALUES (?, ?)", (user_id, text))
        note_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return note_id

    def get_all_notes(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, text, created_at FROM notes WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = cursor.fetchall()
        notes = [{"id": row["id"], "text": row["text"], "created_at": row["created_at"]} for row in rows]
        conn.close()
        return notes

    def update_note(self, user_id, note_id, new_text):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE notes SET text = ? WHERE id = ? AND user_id = ?", (new_text, note_id, user_id))
        conn.commit()
        conn.close()

    def delete_note(self, user_id, note_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
        conn.commit()
        conn.close()

    # --- CRUD для Задач ---
    def add_task(self, user_id, text, deadline=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tasks (user_id, text, deadline) VALUES (?, ?, ?)", (user_id, text, deadline))
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id

    def get_all_tasks(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, text, deadline, is_completed, created_at FROM tasks WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = cursor.fetchall()
        tasks = []
        for row in rows:
            tasks.append({
                "id": row["id"],
                "text": row["text"],
                "deadline": row["deadline"],
                "is_completed": bool(row["is_completed"]),
                "created_at": row["created_at"]
            })
        conn.close()
        return tasks

    def update_task(self, user_id, task_id, new_text=None, new_deadline=None, is_completed=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        updates = []
        params = []

        if new_text is not None:
            updates.append("text = ?")
            params.append(new_text)
        if new_deadline is not None:
            updates.append("deadline = ?")
            params.append(new_deadline)
        if is_completed is not None:
            updates.append("is_completed = ?")
            params.append(int(is_completed))

        if updates:
            sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
            params.extend([task_id, user_id])
            cursor.execute(sql, params)
            conn.commit()
        conn.close()

    def delete_task(self, user_id, task_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        conn.commit()
        conn.close()

    # --- CRUD для Напоминаний ---
    def add_reminder(self, user_id, text, remind_at, is_recurring=False):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO reminders (user_id, text, remind_at, is_recurring) VALUES (?, ?, ?, ?)", (user_id, text, remind_at, int(is_recurring)))
        reminder_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return reminder_id

    def get_all_reminders(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, text, remind_at, is_recurring, created_at FROM reminders WHERE user_id = ? ORDER BY remind_at ASC", (user_id,))
        rows = cursor.fetchall()
        reminders = []
        for row in rows:
            reminders.append({
                "id": row["id"],
                "text": row["text"],
                "remind_at": row["remind_at"],
                "is_recurring": bool(row["is_recurring"]),
                "created_at": row["created_at"]
            })
        conn.close()
        return reminders

    def update_reminder_type(self, user_id, reminder_id, is_recurring):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE reminders SET is_recurring = ? WHERE id = ? AND user_id = ?", (int(is_recurring), reminder_id, user_id))
        conn.commit()
        conn.close()

    def delete_reminder(self, user_id, reminder_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", (reminder_id, user_id))
        conn.commit()
        conn.close()

    # --- НОВАЯ ФУНКЦИЯ ДЛЯ ПЛАНИРОВЩИКА НАПОМИНАНИЙ ---
    def get_reminders_for_time_check(self, check_time):
        """
        Получает все напоминания, время remind_at которых <= check_time.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, text, remind_at, is_recurring, created_at FROM reminders WHERE remind_at <= ? ORDER BY remind_at ASC", (check_time.strftime('%Y-%m-%d %H:%M:%S'),))
        rows = cursor.fetchall()
        reminders = []
        for row in rows:
            reminders.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "text": row["text"],
                "remind_at": row["remind_at"],
                "is_recurring": bool(row["is_recurring"]),
                "created_at": row["created_at"]
            })
        conn.close()
        return reminders

    # --- CRUD для Настроек ---
    def get_settings(self, user_id):
        """Получает настройки пользователя. Если их нет, возвращает значения по умолчанию."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            settings = {
                "main_city": row["main_city"], # Используется как default_city для погоды
                "daily_weather_time": row["daily_weather_time"],
                "daily_weather_enabled": bool(row["daily_weather_enabled"]),
                "master_message_time": row["master_message_time"],
                "master_message_enabled": bool(row["master_message_enabled"]),
            }
        else:
            # Если настроек нет, возвращаем значения по умолчанию
            settings = {
                "main_city": "Moscow", # Используется как default_city для погоды
                "daily_weather_time": "08:00",
                "daily_weather_enabled": False,
                "master_message_time": "09:00",
                "master_message_enabled": False,
            }
        conn.close()
        return settings

    def update_setting(self, user_id, key, value):
        """Обновляет конкретное значение настроек пользователя."""
        conn = self.get_connection()
        cursor = conn.cursor()
        # Используем INSERT OR REPLACE или INSERT ... ON CONFLICT для обновления/создания
        cursor.execute(f"UPDATE settings SET {key} = ? WHERE user_id = ?", (value, user_id))
        if cursor.rowcount == 0:
            # Если UPDATE не затронул ни одной строки, значит записи не было, делаем INSERT
            # Предполагаем, что user_id всегда передаётся
            cursor.execute(f"INSERT INTO settings (user_id, {key}) VALUES (?, ?)", (user_id, value))
        conn.commit()
        conn.close()

# Глобальный экземпляр менеджера базы данных
from config import DATABASE_PATH
db_manager = DatabaseManager(DATABASE_PATH)

# Функция для импорта в другие модули
def get_db():
    return db_manager