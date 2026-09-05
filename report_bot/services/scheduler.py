"""
Планировщик задач для автоотправки ежедневных отчётов, напоминаний и опросников.
Использует APScheduler для запуска генерации отчётов, проверки напоминаний и отправки опросников по расписанию.
"""
import logging
from datetime import date, datetime, timedelta

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import database as db
from services.groq_client import GroqClient, load_report_prompt

logger = logging.getLogger(__name__)

# Глобальный планировщик
scheduler = AsyncIOScheduler()

# Глобальный клиент для Groq
groq_client = GroqClient()


async def send_task_survey(bot: Bot, user_id: int) -> None:
    """Отправляет опросник с задачами перед генерацией отчёта"""
    try:
        # Получаем задачи, выполненные сегодня
        completed_tasks = await db.get_completed_tasks_today(user_id)
        
        if not completed_tasks:
            logger.info(f"У пользователя {user_id} нет выполненных задач за сегодня — опросник не отправлен")
            return
        
        # Формируем опросник с кнопками
        lines = ["📊 <b>Опросник перед отчётом</b>\n\n"]
        lines.append("Отметьте задачи, которые нужно включить в отчёт:\n")
        
        keyboard = []
        for task in completed_tasks:
            completed_time = datetime.fromisoformat(task["completed_at"]).strftime("%H:%M")
            lines.append(f"✅ #{task['id']} <code>{completed_time}</code> — {task['text']}")
            
            # Кнопка для включения в отчёт
            keyboard.append([
                InlineKeyboardButton(
                    f"📋 Включить #{task['id']} в отчёт",
                    callback_data=f"survey_include_{task['id']}"
                )
            ])
        
        # Кнопка "Пропустить все"
        keyboard.append([
            InlineKeyboardButton(
                "❌ Не включать ничего",
                callback_data="survey_skip_all"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await bot.send_message(
            chat_id=user_id,
            text="\n".join(lines),
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        
        logger.info(f"Отправлен опросник пользователю {user_id} с {len(completed_tasks)} задачами")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке опросника пользователю {user_id}: {e}")


async def send_daily_report(bot: Bot, user_id: int) -> None:
    """
    Генерирует и отправляет ежедневный отчёт пользователю.
    
    Args:
        bot: Экземпляр бота для отправки сообщений
        user_id: ID пользователя
    """
    today = date.today()
    
    try:
        # Проверяем, есть ли заметки за сегодня
        notes = await db.get_notes_by_date(user_id, today)
        if not notes:
            logger.info(f"У пользователя {user_id} нет заметок за сегодня — отчёт не отправлен")
            return
        
        # Формируем текст заметок для промпта
        notes_lines = []
        for note in notes:
            timestamp = note["timestamp"][11:16]  # HH:MM
            notes_lines.append(f"[{timestamp}] {note['text']}")
        
        notes_text = "\n".join(notes_lines)
        
        # Загружаем промпт
        prompt_template = load_report_prompt()
        system_prompt = prompt_template.replace("{date}", today.strftime("%d.%m.%Y"))
        
        # Генерируем отчёт через LLM
        report_text = await groq_client.generate_report(system_prompt, notes_text)
        
        if not report_text:
            logger.warning(f"Не удалось сгенерировать отчёт для пользователя {user_id}")
            return
        
        # Сохраняем отчёт в БД
        await db.save_report(user_id, today, report_text)
        
        # Отправляем отчёт
        await bot.send_message(
            chat_id=user_id,
            text=f"📋 <b>Ежедневный отчёт за {today.strftime('%d.%m.%Y')}</b>\n\n{report_text}",
            parse_mode="HTML"
        )
        logger.info(f"Отправлен ежедневный отчёт пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке ежедневного отчёта пользователю {user_id}: {e}")


async def send_morning_tasks(bot: Bot, user_id: int) -> None:
    """Отправляет список всех задач пользователю утром"""
    try:
        # Получаем все задачи пользователя
        tasks = await db.get_all_tasks(user_id)
        
        if not tasks:
            logger.info(f"У пользователя {user_id} нет задач — утренний список не отправлен")
            return
        
        # Формируем список задач
        lines = ["☀️ <b>Доброе утро! Ваши задачи:</b>\n"]
        
        # Разделяем на выполненные и невыполненные
        pending_tasks = [t for t in tasks if not t["completed"]]
        completed_tasks = [t for t in tasks if t["completed"]]
        
        if pending_tasks:
            lines.append("\n<b>⏳ Невыполненные:</b>")
            for task in pending_tasks:
                created = datetime.fromisoformat(task["created_at"]).strftime("%d.%m")
                lines.append(f"• #{task['id']} <code>{created}</code> — {task['text']}")
        
        if completed_tasks:
            lines.append("\n<b>✅ Выполненные:</b>")
            for task in completed_tasks:
                completed_time = datetime.fromisoformat(task["completed_at"]).strftime("%d.%m %H:%M") if task.get("completed_at") else ""
                lines.append(f"• #{task['id']} <code>{completed_time}</code> — {task['text']}")
        
        lines.append(f"\n<i>Всего: {len(tasks)} задач</i>")
        
        # Отправляем список
        await bot.send_message(
            chat_id=user_id,
            text="\n".join(lines),
            parse_mode="HTML"
        )
        
        logger.info(f"Отправлен утренний список задач пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке утренних задач пользователю {user_id}: {e}")


async def check_and_send_reminders(bot: Bot) -> None:
    """Проверяет и отправляет напоминания, которые пора отправить"""
    try:
        due_reminders = await db.get_due_reminders()
        
        for reminder in due_reminders:
            try:
                # Отправляем напоминание
                await bot.send_message(
                    chat_id=reminder["user_id"],
                    text=f"⏰ <b>Напоминание:</b>\n\n{reminder['text']}",
                    parse_mode="HTML"
                )
                
                # Помечаем как отправленное
                await db.mark_reminder_sent(reminder["id"])
                
                logger.info(f"Отправлено напоминание #{reminder['id']} пользователю {reminder['user_id']}")
                
            except Exception as e:
                logger.error(f"Ошибка при отправке напоминания #{reminder['id']}: {e}")
        
        if due_reminders:
            logger.info(f"Проверено и отправлено {len(due_reminders)} напоминаний")
            
    except Exception as e:
        logger.error(f"Ошибка при проверке напоминаний: {e}")


async def schedule_daily_reports(bot: Bot) -> None:
    """
    Настраивает расписание отправки отчётов и утренних задач для всех пользователей.
    Читает настройки времени из БД и создаёт задачи для каждого пользователя.
    """
    try:
        users = await db.get_all_users_with_settings()
        
        for user in users:
            user_id = user["user_id"]
            report_time = user["report_time"]
            morning_tasks_time = user["morning_tasks_time"]
            
            # Парсим время отчёта (формат HH:MM)
            hour, minute = map(int, report_time.split(":"))
            
            # Создаём задачу для отправки опросника за 10 минут до отчёта
            survey_hour = hour
            survey_minute = minute - 10
            if survey_minute < 0:
                survey_minute += 60
                survey_hour -= 1
            
            scheduler.add_job(
                send_task_survey,
                trigger=CronTrigger(hour=survey_hour, minute=survey_minute),
                args=[bot, user_id],
                id=f"task_survey_{user_id}",
                name=f"Task survey for user {user_id}",
                replace_existing=True
            )
            
            # Создаём задачу для отправки отчёта
            scheduler.add_job(
                send_daily_report,
                trigger=CronTrigger(hour=hour, minute=minute),
                args=[bot, user_id],
                id=f"daily_report_{user_id}",
                name=f"Daily report for user {user_id}",
                replace_existing=True
            )
            
            # Парсим время утренних задач (формат HH:MM)
            morning_hour, morning_minute = map(int, morning_tasks_time.split(":"))
            
            # Создаём задачу для отправки утренних задач
            scheduler.add_job(
                send_morning_tasks,
                trigger=CronTrigger(hour=morning_hour, minute=morning_minute),
                args=[bot, user_id],
                id=f"morning_tasks_{user_id}",
                name=f"Morning tasks for user {user_id}",
                replace_existing=True
            )
            
            logger.info(f"Запланированы утренние задачи ({morning_tasks_time}), опросник и отчёт ({report_time}) для пользователя {user_id}")
        
        logger.info(f"Всего запланировано пользователей: {len(users)}")
        
    except Exception as e:
        logger.error(f"Ошибка при настройке расписания: {e}")


async def update_user_schedule(bot: Bot, user_id: int, new_time: str) -> None:
    """
    Обновляет расписание отчётов для конкретного пользователя.
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        new_time: Новое время в формате HH:MM
    """
    try:
        hour, minute = map(int, new_time.split(":"))
        
        # Удаляем старую задачу (если есть)
        job_id = f"daily_report_{user_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        
        # Создаём новую задачу
        scheduler.add_job(
            send_daily_report,
            trigger=CronTrigger(hour=hour, minute=minute),
            args=[bot, user_id],
            id=job_id,
            name=f"Daily report for user {user_id}",
            replace_existing=True
        )
        
        logger.info(f"Обновлено расписание для пользователя {user_id}: {new_time}")
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении расписания для пользователя {user_id}: {e}")


def start_scheduler() -> None:
    """Запускает планировщик задач"""
    if not scheduler.running:
        scheduler.start()
        logger.info("Планировщик запущен")


def add_reminder_checker(bot: Bot) -> None:
    """Добавляет задачу проверки напоминаний каждые 30 секунд"""
    scheduler.add_job(
        check_and_send_reminders,
        trigger=IntervalTrigger(seconds=30),
        args=[bot],
        id="reminder_checker",
        name="Check and send reminders",
        replace_existing=True
    )
    logger.info("Добавлена задача проверки напоминаний (каждые 30 секунд)")


async def health_check(bot: Bot) -> None:
    """Периодическая проверка активности бота"""
    try:
        # Простой вызов API для поддержания соединения
        await bot.get_me()
        logger.debug("Health check: OK")
    except Exception as e:
        logger.warning(f"Health check failed: {e}")


def add_health_check(bot: Bot) -> None:
    """Добавляет задачу проверки здоровья каждые 5 минут"""
    scheduler.add_job(
        health_check,
        trigger=IntervalTrigger(minutes=5),
        args=[bot],
        id="health_check",
        name="Bot health check",
        replace_existing=True
    )
    logger.info("Добавлена задача проверки здоровья (каждые 5 минут)")


def shutdown_scheduler() -> None:
    """Останавливает планировщик задач"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Планировщик остановлен")
