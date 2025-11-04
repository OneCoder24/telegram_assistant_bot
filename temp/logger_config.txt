import logging
import os
from config import LOG_FILE_SIZE, LOG_DIR  # Импортируем настройки из config.py

# Пути к файлам логов
LOG_FILE_1 = os.path.join(LOG_DIR, 'bot_log_1.log')
LOG_FILE_2 = os.path.join(LOG_DIR, 'bot_log_2.log')

class RotatingFileHandlerTwoFiles(logging.Handler):
    """
    Пользовательский обработчик логов, который ротирует между двумя файлами.
    """
    def __init__(self, filename1, filename2, max_bytes):
        super().__init__()
        self.filename1 = filename1
        self.filename2 = filename2
        self.max_bytes = max_bytes
        # Убедимся, что папка logs существует
        os.makedirs(os.path.dirname(filename1), exist_ok=True)
        os.makedirs(os.path.dirname(filename2), exist_ok=True)

        # Инициализируем атрибут stream как None на случай ошибки в _get_current_file_to_write
        self.stream = None
        try:
            self.current_file = self._get_current_file_to_write()
            # Открываем файл для записи
            self.stream = open(self.current_file, 'a', encoding='utf-8')
        except Exception as e:
            print(f"Ошибка инициализации логгера: {e}")
            raise # Переподнимаем исключение, чтобы ошибка была явной


    def _get_current_file_to_write(self):
        """Определяет, в какой файл писать следующим."""
        # Получаем размер файла, если он существует, иначе 0
        size1 = os.path.getsize(self.filename1) if os.path.exists(self.filename1) else 0
        size2 = os.path.getsize(self.filename2) if os.path.exists(self.filename2) else 0

        # Если оба файла пустые или оба переполнены, начинаем с первого
        if size1 == 0 and size2 == 0:
            return self.filename1
        # Если первый файл переполнен, и второй пуст или не переполнен, пишем во второй
        elif size1 >= self.max_bytes and size2 < self.max_bytes:
            return self.filename2
        # Если второй файл переполнен, и первый пуст или не переполнен, пишем в первый
        elif size2 >= self.max_bytes and size1 < self.max_bytes:
            return self.filename1
        # Если оба переполнены, очищаем первый и пишем туда
        elif size1 >= self.max_bytes and size2 >= self.max_bytes:
            with open(self.filename1, 'w', encoding='utf-8') as f: # Очищаем первый файл
                pass
            return self.filename1
        # В остальных случаях, если ни один не переполнен, пишем в первый непереполненный
        else:
            return self.filename1 if size1 < self.max_bytes else self.filename2

    def _rotate_file(self):
        """Определяет, нужно ли сменить файл, и если да - меняет."""
        if self.stream and os.path.getsize(self.current_file) >= self.max_bytes:
            # Закрываем текущий поток
            self.stream.close()
            # Определяем новый файл
            if self.current_file == self.filename1:
                self.current_file = self.filename2
            else:
                self.current_file = self.filename1
            # Открываем новый поток
            self.stream = open(self.current_file, 'a', encoding='utf-8')

    def emit(self, record):
        """
        Вызывается при логировании сообщения.
        """
        try:
            # Проверяем, нужно ли сменить файл перед записью
            self._rotate_file()
            # Форматируем сообщение
            msg = self.format(record)
            # Записываем в открытый поток
            if self.stream: # Проверяем, что поток открыт
                self.stream.write(msg + '\n')
                self.stream.flush() # Принудительно сбрасываем буфер
        except Exception:
            # В случае ошибки вызываем стандартную обработку ошибки обработчика
            self.handleError(record)

    def close(self):
        """Закрывает открытый поток при завершении."""
        if hasattr(self, 'stream') and self.stream: # Проверяем наличие атрибута и его значение
            self.stream.close()
        super().close()

def setup_logger():
    """
    Настраивает и возвращает логгер с ротацией.
    """
    logger = logging.getLogger('TelegramBotLogger') # Имя логгера
    logger.setLevel(logging.DEBUG) # Уровень логирования

    # Создаем наш пользовательский обработчик
    handler = RotatingFileHandlerTwoFiles(LOG_FILE_1, LOG_FILE_2, LOG_FILE_SIZE)

    # Создаем форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)

    # Добавляем обработчик к логгеру
    logger.addHandler(handler)

    return logger

# Глобальный экземпляр логгера
bot_logger = setup_logger()

# Функция для импорта в другие модули
def get_logger():
    return bot_logger