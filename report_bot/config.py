"""
Конфигурация бота — загрузка переменных окружения из .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env из корня проекта
load_dotenv(Path(__file__).parent.parent / ".env")


class Config:
    """Конфигурация приложения"""
    
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # Прокси для Telegram (опционально)
    # Формат: socks5://user:pass@host:port или http://user:pass@host:port
    PROXY_URL: str = os.getenv("PROXY_URL", "")
    
    # Groq API
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "qwen/qwen3.8-27b"  # Изменено на доступную модель
    GROQ_WHISPER_MODEL: str = "whisper-large-v3-turbo"
    
    # База данных
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot.db")
    
    # Время отчёта по умолчанию
    DEFAULT_REPORT_TIME: str = "18:00"
    
    # Таймауты для API запросов (секунды)
    API_TIMEOUT: int = 10
    
    # Путь к промпту
    PROMPT_PATH: Path = Path(__file__).parent / "prompts" / "report.txt"


def validate_config() -> None:
    """Проверяет наличие обязательных переменных окружения"""
    if not Config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен в .env")
    if not Config.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY не установлен в .env")
