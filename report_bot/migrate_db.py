"""
Скрипт миграции базы данных для добавления новых колонок.
Запускается автоматически при старте бота.
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)


def migrate_database(db_path: str = "bot.db") -> None:
    """Выполняет миграцию базы данных"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем существование таблицы settings
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        if not cursor.fetchone():
            logger.info("Таблица settings не существует, миграция не требуется")
            conn.close()
            return
        
        # Проверяем существование колонки morning_tasks_time
        cursor.execute("PRAGMA table_info(settings)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "morning_tasks_time" not in columns:
            logger.info("Добавляю колонку morning_tasks_time в таблицу settings")
            conn.execute('ALTER TABLE settings ADD COLUMN morning_tasks_time TEXT NOT NULL DEFAULT "08:50"')
            conn.commit()
            logger.info("Колонка morning_tasks_time добавлена успешно")
        else:
            logger.info("Колонка morning_tasks_time уже существует")
        
        # Проверяем существование колонки report_type в таблице reports
        cursor.execute("PRAGMA table_info(reports)")
        reports_columns = [row[1] for row in cursor.fetchall()]
        
        if "report_type" not in reports_columns:
            logger.info("Добавляю колонку report_type в таблицу reports")
            conn.execute('ALTER TABLE reports ADD COLUMN report_type TEXT NOT NULL DEFAULT "daily"')
            conn.commit()
            logger.info("Колонка report_type добавлена успешно")
        else:
            logger.info("Колонка report_type уже существует")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Ошибка при миграции базы данных: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_database()
    print("Миграция завершена")
