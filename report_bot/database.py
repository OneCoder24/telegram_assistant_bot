"""
Модуль работы с SQLite базой данных.
Инициализация таблиц и CRUD-операции для заметок, отчётов и настроек.
"""
import aiosqlite
from datetime import date, datetime
from typing import Optional
from config import Config


# Глобальное подключение к БД (инициализируется в init_db)
_db: Optional[aiosqlite.Connection] = None


async def init_db() -> None:
    """Инициализирует базу данных и создаёт таблицы"""
    global _db
    _db = await aiosqlite.connect(Config.DATABASE_PATH)
    _db.row_factory = aiosqlite.Row
    
    # Создаём таблицы
    await _db.executescript("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp DATETIME NOT NULL,
            text TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'text'
        );
        
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            text TEXT NOT NULL,
            created_at DATETIME NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY,
            report_time TEXT NOT NULL DEFAULT '18:00'
        );
        
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            reminder_time DATETIME NOT NULL,
            text TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            sent INTEGER NOT NULL DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at DATETIME
        );
        
        CREATE INDEX IF NOT EXISTS idx_notes_user_date 
        ON notes(user_id, date(timestamp));
        
        CREATE INDEX IF NOT EXISTS idx_reminders_user_time 
        ON reminders(user_id, reminder_time, sent);
        
        CREATE INDEX IF NOT EXISTS idx_tasks_user_completed 
        ON tasks(user_id, completed, date(created_at));
    """)
    await _db.commit()


async def close_db() -> None:
    """Закрывает подключение к БД"""
    global _db
    if _db:
        await _db.close()
        _db = None


def _get_db() -> aiosqlite.Connection:
    """Возвращает активное подключение к БД"""
    if _db is None:
        raise RuntimeError("База данных не инициализирована. Вызовите init_db()")
    return _db


# === Заметки ===

async def add_note(user_id: int, text: str, note_type: str = "text") -> int:
    """Добавляет заметку в БД, возвращает ID"""
    db = _get_db()
    cursor = await db.execute(
        "INSERT INTO notes (user_id, timestamp, text, type) VALUES (?, ?, ?, ?)",
        (user_id, datetime.now().isoformat(), text, note_type)
    )
    await db.commit()
    return cursor.lastrowid


async def get_notes_by_date(user_id: int, target_date: date) -> list[dict]:
    """Получает все заметки пользователя за указанную дату"""
    db = _get_db()
    cursor = await db.execute(
        """SELECT id, timestamp, text, type FROM notes 
           WHERE user_id = ? AND date(timestamp) = ?
           ORDER BY timestamp ASC""",
        (user_id, target_date.isoformat())
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def delete_notes_by_date(user_id: int, target_date: date) -> int:
    """Удаляет все заметки пользователя за дату, возвращает количество"""
    db = _get_db()
    cursor = await db.execute(
        "DELETE FROM notes WHERE user_id = ? AND date(timestamp) = ?",
        (user_id, target_date.isoformat())
    )
    await db.commit()
    return cursor.rowcount


async def update_note_text(user_id: int, note_id: int, new_text: str) -> bool:
    """Обновляет текст заметки, возвращает True если успешно"""
    db = _get_db()
    cursor = await db.execute(
        "UPDATE notes SET text = ? WHERE id = ? AND user_id = ?",
        (new_text, note_id, user_id)
    )
    await db.commit()
    return cursor.rowcount > 0


# === Напоминания ===

async def add_reminder(user_id: int, reminder_time: str, text: str) -> int:
    """Добавляет напоминание в БД, возвращает ID"""
    db = _get_db()
    cursor = await db.execute(
        "INSERT INTO reminders (user_id, reminder_time, text, created_at, sent) VALUES (?, ?, ?, ?, 0)",
        (user_id, reminder_time, text, datetime.now().isoformat())
    )
    await db.commit()
    return cursor.lastrowid


async def get_pending_reminders(user_id: int) -> list[dict]:
    """Получает все неотправленные напоминания пользователя"""
    db = _get_db()
    cursor = await db.execute(
        "SELECT id, reminder_time, text FROM reminders WHERE user_id = ? AND sent = 0 ORDER BY reminder_time ASC",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_due_reminders() -> list[dict]:
    """Получает все напоминания, которые пора отправить"""
    db = _get_db()
    now = datetime.now().isoformat()
    cursor = await db.execute(
        "SELECT id, user_id, reminder_time, text FROM reminders WHERE sent = 0 AND reminder_time <= ? ORDER BY reminder_time ASC",
        (now,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def mark_reminder_sent(reminder_id: int) -> None:
    """Помечает напоминание как отправленное"""
    db = _get_db()
    await db.execute(
        "UPDATE reminders SET sent = 1 WHERE id = ?",
        (reminder_id,)
    )
    await db.commit()


async def delete_reminder(user_id: int, reminder_id: int) -> bool:
    """Удаляет напоминание, возвращает True если успешно"""
    db = _get_db()
    cursor = await db.execute(
        "DELETE FROM reminders WHERE id = ? AND user_id = ?",
        (reminder_id, user_id)
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_all_reminders(user_id: int) -> list[dict]:
    """Получает все напоминания пользователя (отправленные и нет)"""
    db = _get_db()
    cursor = await db.execute(
        "SELECT id, reminder_time, text, sent FROM reminders WHERE user_id = ? ORDER BY reminder_time ASC",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# === Задачи ===

async def add_task(user_id: int, text: str) -> int:
    """Добавляет задачу в БД, возвращает ID"""
    db = _get_db()
    cursor = await db.execute(
        "INSERT INTO tasks (user_id, text, created_at, completed) VALUES (?, ?, ?, 0)",
        (user_id, text, datetime.now().isoformat())
    )
    await db.commit()
    return cursor.lastrowid


async def get_all_tasks(user_id: int) -> list[dict]:
    """Получает все задачи пользователя"""
    db = _get_db()
    cursor = await db.execute(
        "SELECT id, text, created_at, completed, completed_at FROM tasks WHERE user_id = ? ORDER BY completed ASC, created_at DESC",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_pending_tasks(user_id: int) -> list[dict]:
    """Получает невыполненные задачи пользователя"""
    db = _get_db()
    cursor = await db.execute(
        "SELECT id, text, created_at FROM tasks WHERE user_id = ? AND completed = 0 ORDER BY created_at DESC",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_completed_tasks_today(user_id: int) -> list[dict]:
    """Получает задачи, выполненные сегодня"""
    db = _get_db()
    today = date.today().isoformat()
    cursor = await db.execute(
        "SELECT id, text, completed_at FROM tasks WHERE user_id = ? AND completed = 1 AND date(completed_at) = ?",
        (user_id, today)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def mark_task_completed(user_id: int, task_id: int) -> bool:
    """Помечает задачу как выполненную"""
    db = _get_db()
    cursor = await db.execute(
        "UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ? AND user_id = ?",
        (datetime.now().isoformat(), task_id, user_id)
    )
    await db.commit()
    return cursor.rowcount > 0


async def mark_task_pending(user_id: int, task_id: int) -> bool:
    """Помечает задачу как невыполненную"""
    db = _get_db()
    cursor = await db.execute(
        "UPDATE tasks SET completed = 0, completed_at = NULL WHERE id = ? AND user_id = ?",
        (task_id, user_id)
    )
    await db.commit()
    return cursor.rowcount > 0


async def update_task_text(user_id: int, task_id: int, new_text: str) -> bool:
    """Обновляет текст задачи"""
    db = _get_db()
    cursor = await db.execute(
        "UPDATE tasks SET text = ? WHERE id = ? AND user_id = ?",
        (new_text, task_id, user_id)
    )
    await db.commit()
    return cursor.rowcount > 0


async def delete_task(user_id: int, task_id: int) -> bool:
    """Удаляет задачу"""
    db = _get_db()
    cursor = await db.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, user_id)
    )
    await db.commit()
    return cursor.rowcount > 0


# === Отчёты ===

async def save_report(user_id: int, report_date: date, text: str) -> int:
    """Сохраняет сгенерированный отчёт в БД"""
    db = _get_db()
    cursor = await db.execute(
        "INSERT INTO reports (user_id, date, text, created_at) VALUES (?, ?, ?, ?)",
        (user_id, report_date.isoformat(), text, datetime.now().isoformat())
    )
    await db.commit()
    return cursor.lastrowid


async def get_report(user_id: int, report_date: date) -> Optional[str]:
    """Получает последний отчёт за дату (если есть)"""
    db = _get_db()
    cursor = await db.execute(
        "SELECT text FROM reports WHERE user_id = ? AND date = ? ORDER BY created_at DESC LIMIT 1",
        (user_id, report_date.isoformat())
    )
    row = await cursor.fetchone()
    return row["text"] if row else None


# === Настройки ===

async def get_report_time(user_id: int) -> str:
    """Получает настроенное время отчёта для пользователя"""
    db = _get_db()
    cursor = await db.execute(
        "SELECT report_time FROM settings WHERE user_id = ?",
        (user_id,)
    )
    row = await cursor.fetchone()
    return row["report_time"] if row else Config.DEFAULT_REPORT_TIME


async def set_report_time(user_id: int, time_str: str) -> None:
    """Устанавливает время автоотправки отчёта"""
    db = _get_db()
    await db.execute(
        """INSERT INTO settings (user_id, report_time) VALUES (?, ?)
           ON CONFLICT(user_id) DO UPDATE SET report_time = excluded.report_time""",
        (user_id, time_str)
    )
    await db.commit()


async def get_all_users_with_settings() -> list[dict]:
    """Получает всех пользователей с их настройками времени"""
    db = _get_db()
    cursor = await db.execute(
        """SELECT DISTINCT n.user_id, COALESCE(s.report_time, ?) as report_time
           FROM notes n
           LEFT JOIN settings s ON n.user_id = s.user_id""",
        (Config.DEFAULT_REPORT_TIME,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
