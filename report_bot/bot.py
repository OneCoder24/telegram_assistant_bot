"""
Точка входа Telegram-бота для генерации рабочих отчётов.
Регистрирует хендлеры, настраивает логирование и запускает бота.
"""
import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Config, validate_config
import database as db
from handlers import notes, commands, report
from services.scheduler import (
    start_scheduler,
    shutdown_scheduler,
    schedule_daily_reports
)


def setup_logging() -> None:
    """Настраивает логирование в файл и консоль"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )


async def on_startup(bot: Bot) -> None:
    """Действия при запуске бота"""
    logger = logging.getLogger(__name__)
    
    # Инициализируем базу данных
    await db.init_db()
    logger.info("База данных инициализирована")
    
    # Запускаем планировщик
    start_scheduler()
    
    # Настраиваем расписание отчётов для всех пользователей
    await schedule_daily_reports(bot)
    logger.info("Расписание отчётов настроено")


async def on_shutdown(bot: Bot) -> None:
    """Действия при остановке бота"""
    logger = logging.getLogger(__name__)
    
    # Останавливаем планировщик
    shutdown_scheduler()
    
    # Закрываем подключение к БД
    await db.close_db()
    logger.info("Бот остановлен, ресурсы освобождены")


async def main() -> None:
    """Главная функция запуска бота"""
    # Настраиваем логирование
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Проверяем конфигурацию
    try:
        validate_config()
        logger.info("Конфигурация загружена")
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        logger.error("Создайте .env файл на основе .env.example и заполните все необходимые значения")
        sys.exit(1)
    
    # Создаём стандартную сессию с увеличенными таймаутами
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiohttp import ClientTimeout
    
    timeout = ClientTimeout(
        total=120,
        connect=30,
        sock_read=120,
        sock_connect=30
    )
    
    session = AiohttpSession(timeout=timeout)
    
    # Создаём экземпляры бота и диспетчера
    bot = Bot(
        token=Config.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    
    # Регистрируем хендлеры (порядок важен!)
    dp.include_router(commands.router)  # Команды (кроме /report)
    dp.include_router(report.router)    # /report должен быть после обычных команд
    dp.include_router(notes.router)     # Заметки (текст, голос, фото) — последними
    
    # Регистрируем хуки запуска/остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    logger.info("Бот запущен")
    
    # Запускаем polling с коротким таймаутом для обхода проблем с VPN
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            timeout=5,  # Короткий таймаут для быстрого переподключения
            poll_timeout=10  # Короткий polling timeout
        )
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        # Используем WindowsSelectorEventLoopPolicy для решения проблем с semaphore timeout
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Бот остановлен пользователем")
