"""
Обработчики для модуля напоминаний.
Добавление, просмотр и управление напоминаниями.
"""
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
from services.reminder_parser import parse_reminder
from services.groq_client import GroqClient

logger = logging.getLogger(__name__)

# Глобальный клиент для распознавания голоса
groq_client = GroqClient()


async def cmd_add_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавление напоминания — ожидает текст следующим сообщением"""
    context.user_data['adding_reminder'] = True
    await update.message.reply_text(
        "⏰ Режим добавления напоминания\n\n"
        "Отправьте текст напоминания на естественном языке.\n"
        "Примеры:\n"
        "• Завтра в 15:00 позвонить клиенту\n"
        "• Через 2 часа встреча с командой\n"
        "• В пятницу сдать отчёт"
    )


async def cmd_list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать все напоминания"""
    user_id = update.effective_user.id
    
    reminders = await db.get_all_reminders(user_id)
    
    if not reminders:
        await update.message.reply_text("⏰ У вас нет напоминаний.")
        return
    
    # Формируем список напоминаний
    lines = ["⏰ <b>Ваши напоминания:</b>\n"]
    keyboard = []
    
    for reminder in reminders:
        reminder_time = datetime.fromisoformat(reminder["reminder_time"])
        time_str = reminder_time.strftime("%d.%m.%Y %H:%M")
        status = "✅" if reminder["sent"] else "⏳"
        
        lines.append(f"{status} #{reminder['id']} <code>{time_str}</code> — {reminder['text']}")
        
        # Кнопка удаления для каждого напоминания
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 Удалить #{reminder['id']}",
                callback_data=f"delete_reminder_{reminder['id']}"
            )
        ])
    
    lines.append(f"\n<i>Всего: {len(reminders)} напоминаний</i>")
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=reply_markup
    )


async def callback_delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление напоминания"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID напоминания из callback_data
    reminder_id = int(query.data.split("_")[-1])
    user_id = query.from_user.id
    
    try:
        success = await db.delete_reminder(user_id, reminder_id)
        
        if success:
            await query.edit_message_text(f"🗑 Напоминание #{reminder_id} удалено.")
            logger.info(f"Пользователь {user_id} удалил напоминание #{reminder_id}")
        else:
            await query.edit_message_text("❌ Напоминание не найдено.")
    except Exception as e:
        logger.error(f"Ошибка при удалении напоминания: {e}")
        await query.edit_message_text("⚠️ Ошибка при удалении напоминания.")


async def handle_reminder_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка текста для добавления напоминания"""
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    
    # Проверяем, находится ли пользователь в режиме добавления напоминания
    if not context.user_data.get('adding_reminder'):
        return
    
    # Убираем флаг режима
    context.user_data.pop('adding_reminder', None)
    
    # Уведомляем о начале обработки
    processing_msg = await update.message.reply_text("🤖 Анализирую напоминание...")
    
    try:
        # Парсим текст напоминания через LLM
        parsed = await parse_reminder(update.message.text)
        
        if not parsed:
            await processing_msg.edit_text(
                "❌ Не удалось распознать дату и время.\n\n"
                "Попробуйте сформулировать точнее, например:\n"
                "• Завтра в 15:00 позвонить клиенту\n"
                "• Через 2 часа встреча"
            )
            return
        
        # Сохраняем напоминание в БД
        reminder_id = await db.add_reminder(
            user_id,
            parsed["datetime"],
            parsed["text"]
        )
        
        # Форматируем время для отображения
        reminder_time = datetime.fromisoformat(parsed["datetime"])
        time_str = reminder_time.strftime("%d.%m.%Y %H:%M")
        
        await processing_msg.edit_text(
            f"✅ Напоминание добавлено!\n\n"
            f"⏰ #{reminder_id} <code>{time_str}</code>\n"
            f"📝 {parsed['text']}",
            parse_mode="HTML"
        )
        
        logger.info(f"Пользователь {user_id} добавил напоминание #{reminder_id} на {parsed['datetime']}")
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении напоминания: {e}")
        await processing_msg.edit_text("⚠️ Ошибка при добавлении напоминания. Попробуйте позже.")


async def handle_reminder_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка голосового сообщения для добавления напоминания"""
    if not update.message or not update.message.voice:
        return
    
    user_id = update.effective_user.id
    
    # Проверяем, находится ли пользователь в режиме добавления напоминания
    if not context.user_data.get('adding_reminder'):
        return
    
    # Убираем флаг режима
    context.user_data.pop('adding_reminder', None)
    
    # Уведомляем о начале обработки
    processing_msg = await update.message.reply_text("🎤 Распознаю голос...")
    
    try:
        # Скачиваем аудиофайл
        file = await update.message.voice.get_file()
        from pathlib import Path
        file_path = Path(f"temp_reminder_voice_{update.message.voice.file_id}.ogg")
        await file.download_to_drive(file_path)
        
        # Распознаём речь через Groq Whisper
        transcribed_text = await groq_client.transcribe_audio(file_path)
        
        # Удаляем временный файл
        file_path.unlink(missing_ok=True)
        
        if not transcribed_text:
            await processing_msg.edit_text("❌ Не расслышал, продиктуй текстом.")
            return
        
        # Уведомляем о начале парсинга
        await processing_msg.edit_text("🤖 Анализирую напоминание...")
        
        # Парсим текст напоминания через LLM
        parsed = await parse_reminder(transcribed_text)
        
        if not parsed:
            await processing_msg.edit_text(
                f"❌ Не удалось распознать дату и время.\n\n"
                f"Распознанный текст: {transcribed_text}\n\n"
                f"Попробуйте сформулировать точнее."
            )
            return
        
        # Сохраняем напоминание в БД
        reminder_id = await db.add_reminder(
            user_id,
            parsed["datetime"],
            parsed["text"]
        )
        
        # Форматируем время для отображения
        reminder_time = datetime.fromisoformat(parsed["datetime"])
        time_str = reminder_time.strftime("%d.%m.%Y %H:%M")
        
        await processing_msg.edit_text(
            f"✅ Напоминание добавлено!\n\n"
            f"⏰ #{reminder_id} <code>{time_str}</code>\n"
            f"📝 {parsed['text']}",
            parse_mode="HTML"
        )
        
        logger.info(f"Пользователь {user_id} добавил голосовое напоминание #{reminder_id} на {parsed['datetime']}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке голосового напоминания: {e}")
        await processing_msg.edit_text("⚠️ Ошибка при добавлении напоминания. Попробуйте позже.")
