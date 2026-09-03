"""
Обработчик генерации отчётов через LLM.
Команда /report с различными аргументами (сегодня, вчера, конкретная дата).
"""
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from aiogram import Router
from aiogram.types import Message

import database as db
from services.groq_client import GroqClient, load_report_prompt

logger = logging.getLogger(__name__)
router = Router()

# Глобальный клиент для генерации отчётов
groq_client = GroqClient()


def parse_report_date(args: str) -> Optional[date]:
    """
    Парсит аргумент команды /report и возвращает дату.
    
    Args:
        args: Аргумент команды ("yesterday", "2024-01-15" или пусто для сегодня)
        
    Returns:
        Дата или None при ошибке парсинга
    """
    if not args:
        return date.today()
    
    args = args.strip().lower()
    
    if args == "yesterday":
        return date.today() - timedelta(days=1)
    
    if args == "today":
        return date.today()
    
    # Пробуем парсить формат YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", args):
        try:
            return datetime.strptime(args, "%Y-%m-%d").date()
        except ValueError:
            return None
    
    return None


async def generate_report_for_date(user_id: int, target_date: date) -> Optional[str]:
    """
    Генерирует отчёт за указанную дату.
    
    Args:
        user_id: ID пользователя
        target_date: Дата для генерации отчёта
        
    Returns:
        Текст отчёта или None при ошибке/отсутствии заметок
    """
    # Получаем заметки за дату
    notes = await db.get_notes_by_date(user_id, target_date)
    
    if not notes:
        return None
    
    # Формируем текст заметок для промпта
    notes_lines = []
    for note in notes:
        timestamp = note["timestamp"][11:16]  # HH:MM
        notes_lines.append(f"[{timestamp}] {note['text']}")
    
    notes_text = "\n".join(notes_lines)
    
    # Загружаем промпт
    prompt_template = load_report_prompt()
    system_prompt = prompt_template.replace("{date}", target_date.strftime("%d.%m.%Y"))
    user_prompt = notes_text
    
    # Генерируем отчёт через LLM
    report_text = await groq_client.generate_report(system_prompt, user_prompt)
    
    if report_text:
        # Сохраняем отчёт в БД
        await db.save_report(user_id, target_date, report_text)
        logger.info(f"Сгенерирован отчёт для пользователя {user_id} за {target_date}")
    
    return report_text


@router.message(lambda m: m.text and m.text.startswith("/report"))
async def cmd_report(message: Message) -> None:
    """Генерация отчёта за указанную дату"""
    user_id = message.from_user.id
    
    # Парсим аргументы команды
    args = message.text[len("/report"):].strip() if len(message.text) > len("/report") else ""
    
    target_date = parse_report_date(args)
    if target_date is None:
        await message.answer(
            "❌ Неверный формат даты.\n\n"
            "Примеры:\n"
            "/report — отчёт за сегодня\n"
            "/report yesterday — отчёт за вчера\n"
            "/report 2024-01-15 — отчёт за конкретную дату"
        )
        return
    
    # Уведомляем о начале генерации
    processing_msg = await message.answer("🤖 Генерирую отчёт...")
    
    try:
        # Проверяем, есть ли уже сгенерированный отчёт
        existing_report = await db.get_report(user_id, target_date)
        if existing_report:
            await processing_msg.edit_text(
                f"ℹ️ Отчёт за {target_date.strftime('%d.%m.%Y')} уже был сгенерирован.\n\n"
                f"{existing_report}\n\n"
                f"💡 Повторная генерация создаст новую версию."
            )
        
        # Генерируем отчёт
        report_text = await generate_report_for_date(user_id, target_date)
        
        if not report_text:
            await processing_msg.edit_text(
                f"📭 За {target_date.strftime('%d.%m.%Y')} заметок нет. "
                f"Нечего включать в отчёт."
            )
            return
        
        # Отправляем отчёт
        await processing_msg.edit_text(
            f"📋 <b>Отчёт за {target_date.strftime('%d.%m.%Y')}</b>\n\n"
            f"{report_text}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при генерации отчёта: {e}")
        await processing_msg.edit_text(
            "⚠️ Не удалось сгенерировать отчёт. Попробуйте позже."
        )
