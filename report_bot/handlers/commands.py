"""
Обработчики команд бота: /start, /help, /clear, /settime, /list
"""
import logging
import re
from datetime import date

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from config import Config

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Приветствие и краткая инструкция"""
    welcome_text = """
👋 Привет! Я бот для ведения рабочих заметок и генерации отчётов.

📝 <b>Как пользоваться:</b>
• Просто пиши текст — я сохраню как заметку
• Отправь голосовое — я распознаю и сохраню
• Фото с подписью — подпись сохранится

📋 <b>Команды:</b>
/report — отчёт за сегодня
/report yesterday — отчёт за вчера
/report 2024-01-15 — отчёт за дату
/list — заметки за сегодня
/clear — удалить заметки за сегодня
/settime 18:00 — время автоотправки отчёта
/help — список команд

Начни записывать заметки, а я помогу составить отчёт! 🚀
"""
    await message.answer(welcome_text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Список команд с описаниями"""
    help_text = """
📋 <b>Доступные команды:</b>

/start — Приветствие и инструкция
/help — Этот список команд

/report — Отчёт за сегодня
/report yesterday — Отчёт за вчера
/report YYYY-MM-DD — Отчёт за конкретную дату

/list — Заметки за сегодня (без LLM)
/clear — Удалить заметки за сегодня

/settime HH:MM — Установить время автоотправки
Текущее время: {current_time}

💡 <b>Совет:</b> просто пиши текст или отправляй голосовые — всё сохранится!
"""
    # Получаем текущее настроенное время
    user_id = message.from_user.id
    current_time = await db.get_report_time(user_id)
    
    await message.answer(help_text.format(current_time=current_time), parse_mode="HTML")


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    """Удаление заметок за сегодня с подтверждением"""
    user_id = message.from_user.id
    today = date.today()
    
    # Проверяем, есть ли заметки
    notes = await db.get_notes_by_date(user_id, today)
    if not notes:
        await message.answer("За сегодня заметок нет — нечего удалять.")
        return
    
    # Создаём inline-кнопку подтверждения
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data="clear_confirm")
    builder.button(text="❌ Отмена", callback_data="clear_cancel")
    builder.adjust(2)
    
    await message.answer(
        f"Удалить {len(notes)} заметок за сегодня?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "clear_confirm")
async def callback_clear_confirm(callback: CallbackQuery) -> None:
    """Подтверждение удаления заметок"""
    user_id = callback.from_user.id
    today = date.today()
    
    deleted_count = await db.delete_notes_by_date(user_id, today)
    await callback.message.edit_text(f"🗑 Удалено заметок: {deleted_count}")
    logger.info(f"Пользователь {user_id} удалил {deleted_count} заметок")


@router.callback_query(F.data == "clear_cancel")
async def callback_clear_cancel(callback: CallbackQuery) -> None:
    """Отмена удаления заметок"""
    await callback.message.edit_text("❌ Удаление отменено.")


@router.message(Command("settime"))
async def cmd_settime(message: Message) -> None:
    """Установка времени автоотправки отчёта"""
    user_id = message.from_user.id
    
    # Парсим аргументы команды
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        current_time = await db.get_report_time(user_id)
        await message.answer(
            f"⏰ Укажи время в формате HH:MM\n"
            f"Текущее время автоотправки: {current_time}\n\n"
            f"Пример: /settime 18:00"
        )
        return
    
    time_str = args[1].strip()
    
    # Проверяем формат времени
    if not re.match(r"^\d{2}:\d{2}$", time_str):
        await message.answer("❌ Неверный формат. Используй HH:MM (например, 18:00)")
        return
    
    hours, minutes = map(int, time_str.split(":"))
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        await message.answer("❌ Неверное время. Часы: 00-23, минуты: 00-59")
        return
    
    # Сохраняем в БД
    await db.set_report_time(user_id, time_str)
    await message.answer(f"✅ Время автоотправки отчёта установлено: {time_str}")
    logger.info(f"Пользователь {user_id} установил время отчёта: {time_str}")


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    """Показать все заметки за сегодня без генерации отчёта"""
    user_id = message.from_user.id
    today = date.today()
    
    notes = await db.get_notes_by_date(user_id, today)
    
    if not notes:
        await message.answer("📭 За сегодня заметок нет.")
        return
    
    # Формируем список заметок
    lines = [f"📝 <b>Заметки за {today.strftime('%d.%m.%Y')}:</b>\n"]
    
    for note in notes:
        timestamp = note["timestamp"][11:16]  # Извлекаем HH:MM из ISO формата
        note_type = {"text": "📝", "voice": "🎤", "photo": "📷"}.get(note["type"], "📝")
        lines.append(f"{note_type} <code>{timestamp}</code> — {note['text']}")
    
    lines.append(f"\n<i>Всего: {len(notes)} заметок</i>")
    
    await message.answer("\n".join(lines), parse_mode="HTML")
