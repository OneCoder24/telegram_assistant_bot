"""
Точка входа Telegram-бота для генерации рабочих отчётов.
Использует python-telegram-bot вместо aiogram для лучшей совместимости с VPN.
"""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

from config import Config, validate_config
import database as db
from services.groq_client import GroqClient, load_report_prompt
from services.scheduler import (
    start_scheduler,
    shutdown_scheduler,
    schedule_daily_reports,
    send_daily_report,
    add_reminder_checker,
    add_health_check
)
from handlers.reminders import (
    cmd_add_reminder,
    cmd_list_reminders,
    callback_delete_reminder,
    handle_reminder_text,
    handle_reminder_voice
)
from handlers.tasks import (
    cmd_add_task,
    cmd_list_tasks,
    callback_task_complete,
    callback_task_edit,
    callback_task_delete,
    handle_task_text,
    handle_task_edit_text,
    handle_task_voice
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Глобальный клиент для Groq
groq_client = GroqClient()


# === Обработчики команд ===

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие и краткая инструкция"""
    welcome_text = """
👋 Привет! Я бот для ведения рабочих заметок и генерации отчётов.

📝 <b>Как пользоваться:</b>
• Просто пиши текст — я сохраню как заметку
• Отправь голосовое — я распознаю и сохраню
• Фото с подписью — подпись сохранится

📋 <b>Команды:</b>
Используй кнопки ниже или пиши команды вручную!

Начни записывать заметки, а я помогу составить отчёт! 🚀
"""
    
    # Создаём клавиатуру с основными командами
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("📋 Отчёт"), KeyboardButton("📝 Заметки")],
            [KeyboardButton("⏰ Напоминания"), KeyboardButton("➕ Добавить напоминание")],
            [KeyboardButton("✅ Задачи"), KeyboardButton("➕ Добавить задачу")],
            [KeyboardButton("🗑 Очистить всё"), KeyboardButton("⚙️ Настройки")]
        ],
        resize_keyboard=True,  # Автоматический размер
        one_time_keyboard=False  # Постоянная клавиатура
    )
    
    await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=keyboard)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Список команд с описаниями"""
    user_id = update.effective_user.id
    current_time = await db.get_report_time(user_id)
    morning_time = await db.get_morning_tasks_time(user_id)
    
    help_text = f"""
📋 <b>Доступные команды:</b>

/start — Приветствие и инструкция
/help — Этот список команд

/report — Отчёт за сегодня
/report yesterday — Отчёт за вчера
/report YYYY-MM-DD — Отчёт за конкретную дату

/list — Заметки за сегодня (без LLM)
/clear — Удалить заметки за сегодня

/settime HH:MM — Установить время автоотправки отчёта
Текущее время: {current_time}

/setmorningtime HH:MM — Установить время утреннего списка задач
Текущее время: {morning_time}

💡 <b>Совет:</b> просто пиши текст или отправляй голосовые — всё сохранится!
"""
    await update.message.reply_text(help_text, parse_mode="HTML")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать все заметки за сегодня с кнопками удаления"""
    user_id = update.effective_user.id
    today = date.today()
    
    notes = await db.get_notes_by_date(user_id, today)
    
    if not notes:
        await update.message.reply_text("📭 За сегодня заметок нет.")
        return
    
    # Формируем список заметок с ID и inline-кнопками удаления
    lines = [f"📝 <b>Заметки за {today.strftime('%d.%m.%Y')}:</b>\n"]
    
    # Создаём inline-клавиатуру с кнопками удаления и исправления для каждой заметки
    keyboard = []
    for i, note in enumerate(notes):
        timestamp = note["timestamp"][11:16]  # Извлекаем HH:MM из ISO формата
        note_type = {"text": "📝", "voice": "🎤", "photo": "📷"}.get(note["type"], "📝")
        lines.append(f"#{note['id']} {note_type} <code>{timestamp}</code> — {note['text']}")
        
        # Кнопки удаления и исправления для каждой заметки
        keyboard.append([
            InlineKeyboardButton(
                f"✏️ Исправить #{note['id']}",
                callback_data=f"edit_note_{note['id']}"
            ),
            InlineKeyboardButton(
                f"🗑 Удалить #{note['id']}",
                callback_data=f"delete_note_{note['id']}"
            )
        ])
    
    lines.append(f"\n<i>Всего: {len(notes)} заметок</i>")
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=reply_markup
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление заметок за сегодня с подтверждением"""
    user_id = update.effective_user.id
    today = date.today()
    
    # Проверяем, есть ли заметки
    notes = await db.get_notes_by_date(user_id, today)
    if not notes:
        await update.message.reply_text("За сегодня заметок нет — нечего удалять.")
        return
    
    # Создаём inline-кнопку подтверждения
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data="clear_confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="clear_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Удалить {len(notes)} заметок за сегодня?",
        reply_markup=reply_markup
    )


async def callback_clear_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Подтверждение удаления заметок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    today = date.today()
    
    deleted_count = await db.delete_notes_by_date(user_id, today)
    await query.edit_message_text(f"🗑 Удалено заметок: {deleted_count}")
    logger.info(f"Пользователь {user_id} удалил {deleted_count} заметок")


async def callback_clear_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отмена удаления заметок"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Удаление отменено.")


async def callback_survey_include(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Включение задачи в отчёт"""
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.split("_")[-1])
    user_id = query.from_user.id
    
    # Сохраняем список задач для отчёта в context.user_data
    if 'tasks_for_report' not in context.user_data:
        context.user_data['tasks_for_report'] = []
    
    if task_id not in context.user_data['tasks_for_report']:
        context.user_data['tasks_for_report'].append(task_id)
    
    await query.answer(f"✅ Задача #{task_id} будет включена в отчёт", show_alert=True)
    logger.info(f"Пользователь {user_id} включил задачу #{task_id} в отчёт")


async def callback_survey_skip_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пропустить все задачи в отчёте"""
    query = update.callback_query
    await query.answer()
    
    # Очищаем список задач для отчёта
    context.user_data['tasks_for_report'] = []
    
    await query.edit_message_text("❌ Задачи не будут включены в отчёт.")
    logger.info(f"Пользователь {query.from_user.id} пропустил все задачи в отчёте")


async def callback_delete_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление конкретной заметки"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID заметки из callback_data
    note_id = int(query.data.split("_")[-1])
    user_id = query.from_user.id
    
    try:
        # Удаляем заметку из БД
        import aiosqlite
        from config import Config
        
        async with aiosqlite.connect(Config.DATABASE_PATH) as db_conn:
            cursor = await db_conn.execute(
                "DELETE FROM notes WHERE id = ? AND user_id = ?",
                (note_id, user_id)
            )
            await db_conn.commit()
            
            if cursor.rowcount > 0:
                await query.edit_message_text(f"🗑 Заметка #{note_id} удалена.")
                logger.info(f"Пользователь {user_id} удалил заметку #{note_id}")
            else:
                await query.edit_message_text("❌ Заметка не найдена.")
    except Exception as e:
        logger.error(f"Ошибка при удалении заметки: {e}")
        await query.edit_message_text("⚠️ Ошибка при удалении заметки.")


async def callback_edit_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начало редактирования заметки"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID заметки из callback_data
    note_id = int(query.data.split("_")[-1])
    user_id = query.from_user.id
    
    # Сохраняем ID заметки в context.user_data
    context.user_data['editing_note_id'] = note_id
    
    await query.edit_message_text(
        f"✏️ Редактирование заметки #{note_id}\n\n"
        f"Отправьте новый текст заметки следующим сообщением."
    )
    logger.info(f"Пользователь {user_id} начал редактирование заметки #{note_id}")


async def cmd_settime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установка времени автоотправки отчёта"""
    import re
    user_id = update.effective_user.id
    
    # Парсим аргументы команды
    if not context.args:
        current_time = await db.get_report_time(user_id)
        await update.message.reply_text(
            f"⏰ Укажи время в формате HH:MM\n"
            f"Текущее время автоотправки: {current_time}\n\n"
            f"Пример: /settime 18:00"
        )
        return
    
    time_str = context.args[0].strip()
    
    # Проверяем формат времени
    if not re.match(r"^\d{2}:\d{2}$", time_str):
        await update.message.reply_text("❌ Неверный формат. Используй HH:MM (например, 18:00)")
        return
    
    hours, minutes = map(int, time_str.split(":"))
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        await update.message.reply_text("❌ Неверное время. Часы: 00-23, минуты: 00-59")
        return
    
    # Сохраняем в БД
    await db.set_report_time(user_id, time_str)
    await update.message.reply_text(f"✅ Время автоотправки отчёта установлено: {time_str}")
    logger.info(f"Пользователь {user_id} установил время отчёта: {time_str}")


async def cmd_setmorningtime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установка времени утреннего списка задач"""
    import re
    user_id = update.effective_user.id
    
    # Парсим аргументы команды
    if not context.args:
        current_time = await db.get_morning_tasks_time(user_id)
        await update.message.reply_text(
            f"⏰ Укажи время в формате HH:MM\n"
            f"Текущее время утреннего списка задач: {current_time}\n\n"
            f"Пример: /setmorningtime 08:50"
        )
        return
    
    time_str = context.args[0].strip()
    
    # Проверяем формат времени
    if not re.match(r"^\d{2}:\d{2}$", time_str):
        await update.message.reply_text("❌ Неверный формат. Используй HH:MM (например, 08:50)")
        return
    
    hours, minutes = map(int, time_str.split(":"))
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        await update.message.reply_text("❌ Неверное время. Часы: 00-23, минуты: 00-59")
        return
    
    # Сохраняем в БД
    await db.set_morning_tasks_time(user_id, time_str)
    await update.message.reply_text(f"✅ Время утреннего списка задач установлено: {time_str}")
    logger.info(f"Пользователь {user_id} установил время утренних задач: {time_str}")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Генерация отчёта за указанную дату"""
    from datetime import timedelta
    import re
    
    user_id = update.effective_user.id
    
    # Парсим аргументы команды
    args = " ".join(context.args) if context.args else ""
    
    # Определяем дату
    if not args:
        target_date = date.today()
    elif args.lower() == "yesterday":
        target_date = date.today() - timedelta(days=1)
    elif args.lower() == "today":
        target_date = date.today()
    elif re.match(r"^\d{4}-\d{2}-\d{2}$", args):
        try:
            target_date = date.fromisoformat(args)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты.")
            return
    else:
        await update.message.reply_text(
            "❌ Неверный формат даты.\n\n"
            "Примеры:\n"
            "/report — отчёт за сегодня\n"
            "/report yesterday — отчёт за вчера\n"
            "/report 2024-01-15 — отчёт за конкретную дату"
        )
        return
    
    # Уведомляем о начале генерации
    processing_msg = await update.message.reply_text("🤖 Генерирую отчёт...")
    
    try:
        # Получаем заметки за дату
        notes = await db.get_notes_by_date(user_id, target_date)
        
        if not notes:
            await processing_msg.edit_text(
                f"📭 За {target_date.strftime('%d.%m.%Y')} заметок нет. "
                f"Нечего включать в отчёт."
            )
            return
        
        # Формируем текст заметок для промпта
        notes_lines = []
        for note in notes:
            timestamp = note["timestamp"][11:16]  # HH:MM
            notes_lines.append(f"[{timestamp}] {note['text']}")
        
        notes_text = "\n".join(notes_lines)
        
        # Загружаем промпт
        prompt_template = load_report_prompt()
        system_prompt = prompt_template.replace("{date}", target_date.strftime("%d.%m.%Y"))
        
        # Генерируем отчёт через LLM
        report_text = await groq_client.generate_report(system_prompt, notes_text)
        
        if not report_text:
            await processing_msg.edit_text(
                "⚠️ Не удалось сгенерировать отчёт. Попробуйте позже."
            )
            return
        
        # Сохраняем отчёт в БД
        await db.save_report(user_id, target_date, report_text)
        
        # Отправляем отчёт
        await processing_msg.edit_text(
            f"📋 <b>Отчёт за {target_date.strftime('%d.%m.%Y')}</b>\n\n"
            f"{report_text}",
            parse_mode="HTML"
        )
        logger.info(f"Сгенерирован отчёт для пользователя {user_id} за {target_date}")
        
    except Exception as e:
        logger.error(f"Ошибка при генерации отчёта: {e}")
        await processing_msg.edit_text(
            "⚠️ Не удалось сгенерировать отчёт. Попробуйте позже."
        )


# === Обработчики заметок ===

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок меню"""
    text = update.message.text
    
    if text == "📋 Отчёт":
        await cmd_report(update, context)
    elif text == "📝 Заметки":
        await cmd_list(update, context)
    elif text == "🗑 Очистить всё":
        await cmd_clear(update, context)
    elif text == "⏰ Напоминания":
        await cmd_list_reminders(update, context)
    elif text == "➕ Добавить напоминание":
        await cmd_add_reminder(update, context)
    elif text == "✅ Задачи":
        await cmd_list_tasks(update, context)
    elif text == "➕ Добавить задачу":
        await cmd_add_task(update, context)
    elif text == "⚙️ Настройки":
        # Показываем текущие настройки
        user_id = update.effective_user.id
        current_time = await db.get_report_time(user_id)
        await update.message.reply_text(
            f"⚙️ <b>Настройки:</b>\n\n"
            f"⏰ Время автоотправки: <code>{current_time}</code>\n\n"
            f"Чтобы изменить время, отправьте:\n"
            f"<code>/settime 18:00</code>",
            parse_mode="HTML"
        )


async def cmd_delete_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление последней заметки"""
    user_id = update.effective_user.id
    today = date.today()
    
    notes = await db.get_notes_by_date(user_id, today)
    
    if not notes:
        await update.message.reply_text("📭 За сегодня заметок нет — нечего удалять.")
        return
    
    last_note = notes[-1]
    
    # Создаём inline-кнопку подтверждения
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"delete_note_{last_note['id']}"),
            InlineKeyboardButton("❌ Отмена", callback_data="clear_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    timestamp = last_note["timestamp"][11:16]
    note_type = {"text": "📝", "voice": "🎤", "photo": "📷"}.get(last_note["type"], "📝")
    
    await update.message.reply_text(
        f"Удалить последнюю заметку?\n\n"
        f"{note_type} <code>{timestamp}</code> — {last_note['text']}",
        parse_mode="HTML",
        reply_markup=reply_markup
    )


async def handle_text_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сохраняет текстовое сообщение как заметку или обновляет редактируемую заметку, или добавляет напоминание, или добавляет задачу"""
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    
    # Проверяем, находится ли пользователь в режиме добавления напоминания
    if context.user_data.get('adding_reminder'):
        await handle_reminder_text(update, context)
        return
    
    # Проверяем, находится ли пользователь в режиме добавления задачи
    if context.user_data.get('adding_task'):
        await handle_task_text(update, context)
        return
    
    # Проверяем, находится ли пользователь в режиме редактирования заметки
    editing_note_id = context.user_data.get('editing_note_id')
    
    if editing_note_id:
        # Режим редактирования — обновляем заметку
        try:
            success = await db.update_note_text(user_id, editing_note_id, update.message.text)
            
            if success:
                await update.message.reply_text(f"✅ Заметка #{editing_note_id} обновлена.")
                logger.info(f"Пользователь {user_id} обновил заметку #{editing_note_id}")
            else:
                await update.message.reply_text("❌ Заметка не найдена.")
            
            # Очищаем режим редактирования
            context.user_data.pop('editing_note_id', None)
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении заметки: {e}")
            await update.message.reply_text("⚠️ Ошибка при обновлении заметки.")
            context.user_data.pop('editing_note_id', None)
        
        return
    
    # Обычный режим — сохраняем как новую заметку
    try:
        note_id = await db.add_note(user_id, update.message.text, "text")
        await update.message.reply_text(f"✓ Заметка сохранена (#{note_id})")
        logger.info(f"Пользователь {user_id} добавил текстовую заметку #{note_id}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении заметки: {e}")
        await update.message.reply_text("⚠️ Не удалось сохранить заметку. Попробуйте позже.")


async def handle_task_edit_text_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обёртка для обработки редактирования задачи"""
    if context.user_data.get('editing_task_id'):
        await handle_task_edit_text(update, context)


async def handle_voice_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Скачивает голосовое сообщение, распознаёт через Whisper и сохраняет или обновляет заметку, или добавляет напоминание, или добавляет задачу"""
    if not update.message or not update.message.voice:
        return
    
    user_id = update.effective_user.id
    voice = update.message.voice
    
    # Проверяем, находится ли пользователь в режиме добавления напоминания
    if context.user_data.get('adding_reminder'):
        await handle_reminder_voice(update, context)
        return
    
    # Проверяем, находится ли пользователь в режиме добавления задачи
    if context.user_data.get('adding_task'):
        await handle_task_voice(update, context)
        return
    
    # Проверяем, находится ли пользователь в режиме редактирования
    editing_note_id = context.user_data.get('editing_note_id')
    
    # Уведомляем пользователя о начале обработки
    processing_msg = await update.message.reply_text("🎤 Распознаю голос...")
    
    try:
        # Скачиваем аудиофайл
        file = await voice.get_file()
        file_path = Path(f"temp_voice_{voice.file_id}.ogg")
        await file.download_to_drive(file_path)
        
        # Распознаём речь через Groq Whisper
        transcribed_text = await groq_client.transcribe_audio(file_path)
        
        # Удаляем временный файл
        file_path.unlink(missing_ok=True)
        
        if not transcribed_text:
            await processing_msg.edit_text("❌ Не расслышал, продиктуй текстом.")
            logger.warning(f"Не удалось распознать голос от пользователя {user_id}")
            return
        
        # Если в режиме редактирования — обновляем заметку
        if editing_note_id:
            success = await db.update_note_text(user_id, editing_note_id, transcribed_text)
            
            if success:
                await processing_msg.edit_text(
                    f"✅ Заметка #{editing_note_id} обновлена: {transcribed_text}"
                )
                logger.info(f"Пользователь {user_id} обновил заметку #{editing_note_id} голосом")
            else:
                await processing_msg.edit_text("❌ Заметка не найдена.")
            
            # Очищаем режим редактирования
            context.user_data.pop('editing_note_id', None)
            return
        
        # Обычный режим — сохраняем как новую заметку
        note_id = await db.add_note(user_id, transcribed_text, "voice")
        
        # Подтверждаем пользователю
        await processing_msg.edit_text(
            f"✓ Записал: {transcribed_text}\n\n(заметка #{note_id})"
        )
        logger.info(f"Пользователь {user_id} добавил голосовую заметку #{note_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке голосового сообщения: {e}")
        await processing_msg.edit_text("⚠️ Ошибка при распознавании голоса. Попробуйте позже.")
        context.user_data.pop('editing_note_id', None)


async def handle_photo_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сохраняет подпись к фото как заметку или обновляет редактируемую заметку"""
    if not update.message or not update.message.caption:
        await update.message.reply_text("📷 Фото без подписи — не сохраняю. Добавьте текст к фото.")
        return
    
    user_id = update.effective_user.id
    
    # Проверяем, находится ли пользователь в режиме редактирования
    editing_note_id = context.user_data.get('editing_note_id')
    
    try:
        # Если в режиме редактирования — обновляем заметку
        if editing_note_id:
            success = await db.update_note_text(user_id, editing_note_id, update.message.caption)
            
            if success:
                await update.message.reply_text(f"✅ Заметка #{editing_note_id} обновлена: {update.message.caption}")
                logger.info(f"Пользователь {user_id} обновил заметку #{editing_note_id} фото")
            else:
                await update.message.reply_text("❌ Заметка не найдена.")
            
            # Очищаем режим редактирования
            context.user_data.pop('editing_note_id', None)
            return
        
        # Обычный режим — сохраняем как новую заметку
        note_id = await db.add_note(user_id, update.message.caption, "photo")
        await update.message.reply_text(f"✓ Подпись к фото сохранена (#{note_id})")
        logger.info(f"Пользователь {user_id} добавил заметку с фото #{note_id}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении заметки с фото: {e}")
        await update.message.reply_text("⚠️ Не удалось сохранить заметку. Попробуйте позже.")
        context.user_data.pop('editing_note_id', None)


async def post_init(application: Application) -> None:
    """Действия после инициализации приложения"""
    # Инициализируем базу данных
    await db.init_db()
    logger.info("База данных инициализирована")
    
    # Запускаем планировщик
    start_scheduler()
    
    # Настраиваем расписание отчётов для всех пользователей
    await schedule_daily_reports(application.bot)
    logger.info("Расписание отчётов настроено")
    
    # Добавляем проверку напоминаний
    add_reminder_checker(application.bot)
    logger.info("Проверка напоминаний активирована")
    
    # Добавляем проверку здоровья
    add_health_check(application.bot)
    logger.info("Проверка здоровья активирована")


async def post_shutdown(application: Application) -> None:
    """Действия при остановке приложения"""
    # Останавливаем планировщик
    shutdown_scheduler()
    
    # Закрываем подключение к БД
    await db.close_db()
    logger.info("Бот остановлен, ресурсы освобождены")


def main() -> None:
    """Главная функция запуска бота"""
    # Проверяем конфигурацию
    try:
        validate_config()
        logger.info("Конфигурация загружена")
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        logger.error("Создайте .env файл на основе .env.example и заполните все необходимые значения")
        sys.exit(1)
    
    # Цикл с автоперезапуском при сбоях
    while True:
        try:
            # Импортируем httpx для настройки таймаутов
            from telegram.request import HTTPXRequest
            import httpx
            
            # Настраиваем httpx с увеличенными таймаутами и размером пула
            httpx_request = HTTPXRequest(
                connection_pool_size=100,  # Увеличенный пул соединений
                pool_timeout=60.0,         # Таймаут ожидания соединения (сек)
                connect_timeout=30.0,      # Таймаут установки соединения
                read_timeout=60.0,         # Таймаут чтения ответа
                write_timeout=30.0,        # Таймаут отправки данных
            )
            
            # Создаём приложение с кастомным request
            application = (
                Application.builder()
                .token(Config.BOT_TOKEN)
                .request(httpx_request)
                .post_init(post_init)
                .post_shutdown(post_shutdown)
                .build()
            )
            
            # Регистрируем обработчики команд
            application.add_handler(CommandHandler("start", cmd_start))
            application.add_handler(CommandHandler("help", cmd_help))
            application.add_handler(CommandHandler("list", cmd_list))
            application.add_handler(CommandHandler("clear", cmd_clear))
            application.add_handler(CommandHandler("settime", cmd_settime))
            application.add_handler(CommandHandler("setmorningtime", cmd_setmorningtime))
            application.add_handler(CommandHandler("report", cmd_report))
            
            # Регистрируем обработчики callback-кнопок
            application.add_handler(CallbackQueryHandler(callback_clear_confirm, pattern="^clear_confirm$"))
            application.add_handler(CallbackQueryHandler(callback_clear_cancel, pattern="^clear_cancel$"))
            application.add_handler(CallbackQueryHandler(callback_delete_note, pattern=r"^delete_note_\d+$"))
            application.add_handler(CallbackQueryHandler(callback_edit_note, pattern=r"^edit_note_\d+$"))
            application.add_handler(CallbackQueryHandler(callback_delete_reminder, pattern=r"^delete_reminder_\d+$"))
            application.add_handler(CallbackQueryHandler(callback_task_complete, pattern=r"^task_complete_\d+$"))
            application.add_handler(CallbackQueryHandler(callback_task_edit, pattern=r"^task_edit_\d+$"))
            application.add_handler(CallbackQueryHandler(callback_task_delete, pattern=r"^task_delete_\d+$"))
            application.add_handler(CallbackQueryHandler(callback_survey_include, pattern=r"^survey_include_\d+$"))
            application.add_handler(CallbackQueryHandler(callback_survey_skip_all, pattern="^survey_skip_all$"))
            
            # Регистрируем обработчики заметок (порядок важен!)
            application.add_handler(MessageHandler(filters.VOICE, handle_voice_note))
            application.add_handler(MessageHandler(filters.PHOTO, handle_photo_note))
            
            # Регистрируем обработчики кнопок меню (до обычных заметок!)
            application.add_handler(MessageHandler(filters.Regex("^(📋 Отчёт|📝 Заметки|🗑 Очистить всё|⏰ Напоминания|➕ Добавить напоминание|✅ Задачи|➕ Добавить задачу|⚙️ Настройки)$"), handle_menu_button))
            
            # Обычные текстовые заметки (должны быть последними!)
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_note))
            
            logger.info("Бот запущен")
            
            # Запускаем polling с таймаутом для предотвращения зависания
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                close_loop=False
            )
            
        except KeyboardInterrupt:
            logger.info("Бот остановлен пользователем")
            break
        except Exception as e:
            logger.error(f"Критическая ошибка бота: {e}")
            logger.info("Перезапуск через 5 секунд...")
            import time
            time.sleep(5)
            continue


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
