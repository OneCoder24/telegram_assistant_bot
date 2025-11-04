import os

from dotenv import load_dotenv

load_dotenv()

# --- Определяем корневую директорию проекта ---
# __file__ - это путь к текущему файлу (config.py).
# os.path.dirname(...) получает папку, в которой лежит config.py.
# Предполагается, что config.py находится в корне проекта.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- Настройки бота ---
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- Путь к базе данных (теперь абсолютный) ---
# os.path.join соединяет путь к проекту и имя файла базы данных
DATABASE_PATH = os.path.join(PROJECT_ROOT, 'bot_database.db')

# --- Настройки логирования (теперь абсолютные) ---
# LOG_DIR теперь будет внутри PROJECT_ROOT
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs') # Абсолютный путь к папке логов
LOG_FILE_SIZE = 2 * 1024 * 1024  # 2 МБ в байтах

# --- Настройки погоды ---
DEFAULT_CITY = "Moscow"
WEATHER_TIME = "08:00"
MASTER_MESSAGE_TIME = "09:00"

# --- Настройки напоминаний ---
REMINDER_DEFAULT_TIME = "23:55"
