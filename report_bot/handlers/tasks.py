"""
Обработчики для модуля задач.
Добавление, просмотр, редактирование, удаление и отметка выполнения задач.
"""
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db

logger = logging.getLogger(__name__)


async def cmd_add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавление задачи — ожидает текст следующим сообщением"""
    context.user_data['adding_task'] = True
    await update.message.reply_text(
        "✅ Режим добавления задачи\n\n"
        "Отправьте текст задачи.\n"
        "Примеры:\n"
        "• Закончить отчёт по проекту\n"
        "• Купить продукты\n"
        "• Позвонить врачу"
    )


async def cmd_list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать все задачи с кнопками управления"""
    user_id = update.effective_user.id
    
    tasks = await db.get_all_tasks(user_id)
    
    if not tasks:
        await update.message.reply_text("✅ У вас нет задач.")
        return
    
    # Формируем список задач
    lines = ["✅ <b>Ваши задачи:</b>\n"]
    keyboard = []
    
    for task in tasks:
        status = "✅" if task["completed"] else "⏳"
        created = datetime.fromisoformat(task["created_at"]).strftime("%d.%m %H:%M")
        
        lines.append(f"{status} #{task['id']} <code>{created}</code> — {task['text']}")
        
        # Кнопки управления для каждой задачи
        buttons = []
        
        if not task["completed"]:
            buttons.append(InlineKeyboardButton(
                "✅ Выполнено",
                callback_data=f"task_complete_{task['id']}"
            ))
        
        buttons.append(InlineKeyboardButton(
            "✏️ Исправить",
            callback_data=f"task_edit_{task['id']}"
        ))
        buttons.append(InlineKeyboardButton(
            "🗑 Удалить",
            callback_data=f"task_delete_{task['id']}"
        ))
        
        keyboard.append(buttons)
    
    lines.append(f"\n<i>Всего: {len(tasks)} задач</i>")
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=reply_markup
    )


async def callback_task_complete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отметить задачу как выполненную"""
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.split("_")[-1])
    user_id = query.from_user.id
    
    try:
        success = await db.mark_task_completed(user_id, task_id)
        
        if success:
            await query.edit_message_text(f"✅ Задача #{task_id} отмечена как выполненная!")
            logger.info(f"Пользователь {user_id} отметил задачу #{task_id} как выполненную")
        else:
            await query.edit_message_text("❌ Задача не найдена.")
    except Exception as e:
        logger.error(f"Ошибка при отметке задачи: {e}")
        await query.edit_message_text("⚠️ Ошибка при обновлении задачи.")


async def callback_task_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начало редактирования задачи"""
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.split("_")[-1])
    user_id = query.from_user.id
    
    # Сохраняем ID задачи в context.user_data
    context.user_data['editing_task_id'] = task_id
    
    await query.edit_message_text(
        f"✏️ Редактирование задачи #{task_id}\n\n"
        f"Отправьте новый текст задачи следующим сообщением."
    )
    logger.info(f"Пользователь {user_id} начал редактирование задачи #{task_id}")


async def callback_task_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление задачи"""
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.split("_")[-1])
    user_id = query.from_user.id
    
    try:
        success = await db.delete_task(user_id, task_id)
        
        if success:
            await query.edit_message_text(f"🗑 Задача #{task_id} удалена.")
            logger.info(f"Пользователь {user_id} удалил задачу #{task_id}")
        else:
            await query.edit_message_text("❌ Задача не найдена.")
    except Exception as e:
        logger.error(f"Ошибка при удалении задачи: {e}")
        await query.edit_message_text("⚠️ Ошибка при удалении задачи.")


async def handle_task_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка текста для добавления задачи"""
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    
    # Проверяем, находится ли пользователь в режиме добавления задачи
    if not context.user_data.get('adding_task'):
        return
    
    # Убираем флаг режима
    context.user_data.pop('adding_task', None)
    
    try:
        # Сохраняем задачу в БД
        task_id = await db.add_task(user_id, update.message.text)
        
        await update.message.reply_text(
            f"✅ Задача добавлена!\n\n"
            f"#{task_id} — {update.message.text}"
        )
        
        logger.info(f"Пользователь {user_id} добавил задачу #{task_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении задачи: {e}")
        await update.message.reply_text("⚠️ Ошибка при добавлении задачи. Попробуйте позже.")


async def handle_task_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка текста для редактирования задачи"""
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    
    # Проверяем, находится ли пользователь в режиме редактирования задачи
    editing_task_id = context.user_data.get('editing_task_id')
    
    if not editing_task_id:
        return
    
    # Убираем флаг режима
    context.user_data.pop('editing_task_id', None)
    
    try:
        success = await db.update_task_text(user_id, editing_task_id, update.message.text)
        
        if success:
            await update.message.reply_text(f"✅ Задача #{editing_task_id} обновлена.")
            logger.info(f"Пользователь {user_id} обновил задачу #{editing_task_id}")
        else:
            await update.message.reply_text("❌ Задача не найдена.")
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении задачи: {e}")
        await update.message.reply_text("⚠️ Ошибка при обновлении задачи.")
        context.user_data.pop('editing_task_id', None)


async def handle_task_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка голосового сообщения для добавления задачи"""
    if not update.message or not update.message.voice:
        return
    
    user_id = update.effective_user.id
    
    # Убираем флаг режима
    context.user_data.pop('adding_task', None)
    
    # Уведомляем пользователя о начале обработки
    processing_msg = await update.message.reply_text("🎤 Распознаю голос...")
    
    try:
        # Скачиваем аудиофайл
        file = await update.message.voice.get_file()
        from pathlib import Path
        file_path = Path(f"temp_task_voice_{update.message.voice.file_id}.ogg")
        await file.download_to_drive(file_path)
        
        # Распознаём речь через Groq Whisper
        from services.groq_client import GroqClient
        groq_client = GroqClient()
        transcribed_text = await groq_client.transcribe_audio(file_path)
        
        # Удаляем временный файл
        file_path.unlink(missing_ok=True)
        
        if not transcribed_text:
            await processing_msg.edit_text("❌ Не расслышал, продиктуй текстом.")
            return
        
        # Сохраняем задачу в БД
        task_id = await db.add_task(user_id, transcribed_text)
        
        await processing_msg.edit_text(
            f"✅ Задача добавлена!\n\n"
            f"#{task_id} — {transcribed_text}"
        )
        
        logger.info(f"Пользователь {user_id} добавил голосовую задачу #{task_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении голосовой задачи: {e}")
        await processing_msg.edit_text("⚠️ Ошибка при добавлении задачи. Попробуйте позже.")
