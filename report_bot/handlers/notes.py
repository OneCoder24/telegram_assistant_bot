"""
Обработчики для сохранения заметок: текст, голосовые сообщения, фото с подписью.
"""
import logging
import tempfile
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart

import database as db
from services.groq_client import GroqClient

logger = logging.getLogger(__name__)
router = Router()

# Глобальный клиент для распознавания голоса
groq_client = GroqClient()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Обработчик /start — не сохраняет как заметку"""
    # Этот хендлер здесь только для того, чтобы /start не сохранялся как заметка
    # Основная логика /start в handlers/commands.py
    pass


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_note(message: Message) -> None:
    """Сохраняет текстовое сообщение как заметку"""
    if not message.text:
        return
    
    user_id = message.from_user.id
    
    try:
        note_id = await db.add_note(user_id, message.text, "text")
        await message.answer(f"✓ Заметка сохранена (#{note_id})")
        logger.info(f"Пользователь {user_id} добавил текстовую заметку #{note_id}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении заметки: {e}")
        await message.answer("⚠️ Не удалось сохранить заметку. Попробуйте позже.")


@router.message(F.voice)
async def handle_voice_note(message: Message) -> None:
    """Скачивает голосовое сообщение, распознаёт через Whisper и сохраняет"""
    if not message.voice:
        return
    
    user_id = message.from_user.id
    voice = message.voice
    
    # Уведомляем пользователя о начале обработки
    processing_msg = await message.answer("🎤 Распознаю голос...")
    
    # Скачиваем аудиофайл
    try:
        file = await message.bot.get_file(voice.file_id)
        
        # Создаём временный файл для аудио
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
            temp_path = Path(temp_file.name)
            await message.bot.download_file(file.file_path, temp_path)
        
        # Распознаём речь через Groq Whisper
        transcribed_text = await groq_client.transcribe_audio(temp_path)
        
        # Удаляем временный файл
        temp_path.unlink(missing_ok=True)
        
        if not transcribed_text:
            await processing_msg.edit_text("❌ Не расслышал, продиктуй текстом.")
            logger.warning(f"Не удалось распознать голос от пользователя {user_id}")
            return
        
        # Сохраняем распознанный текст как заметку
        note_id = await db.add_note(user_id, transcribed_text, "voice")
        
        # Подтверждаем пользователю
        await processing_msg.edit_text(
            f"✓ Записал: {transcribed_text}\n\n(заметка #{note_id})"
        )
        logger.info(f"Пользователь {user_id} добавил голосовую заметку #{note_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке голосового сообщения: {e}")
        await processing_msg.edit_text("⚠️ Ошибка при распознавании голоса. Попробуйте позже.")


@router.message(F.photo)
async def handle_photo_note(message: Message) -> None:
    """Сохраняет подпись к фото как заметку"""
    if not message.caption:
        await message.answer("📷 Фото без подписи — не сохраняю. Добавьте текст к фото.")
        return
    
    user_id = message.from_user.id
    
    try:
        note_id = await db.add_note(user_id, message.caption, "photo")
        await message.answer(f"✓ Подпись к фото сохранена (#{note_id})")
        logger.info(f"Пользователь {user_id} добавил заметку с фото #{note_id}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении заметки с фото: {e}")
        await message.answer("⚠️ Не удалось сохранить заметку. Попробуйте позже.")
