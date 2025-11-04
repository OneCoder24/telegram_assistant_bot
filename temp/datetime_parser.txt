# utils/datetime_parser.py (должно быть ТОЧНО так)
from datetime import datetime, timedelta
from config import REMINDER_DEFAULT_TIME # Импортируем время по умолчанию из config.py
import re

def parse_deadline(input_text, default_time_str=None):
    """
    Парсит строку ввода дедлайна в формате 'DD.MM' в 'YYYY-MM-DD HH:MM:SS'.
    Если дата уже прошла в текущем году, возвращает дату следующего года.
    """
    if default_time_str is None:
        default_time_str = REMINDER_DEFAULT_TIME # Используем время из config.py

    # Регулярное выражение для DD.MM
    match = re.match(r'^(\d{1,2})\.(\d{1,2})$', input_text.strip())
    if not match:
        return None # Формат не распознан

    day, month = map(int, match.groups())

    # Проверяем валидность числа и месяца
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None

    # Разбираем время по умолчанию
    try:
        default_hour, default_minute = map(int, default_time_str.split(':'))
    except ValueError:
        # Если формат времени в config.py неправильный, используем 23:55
        default_hour, default_minute = 23, 55

    # Получаем текущую дату
    now = datetime.now()
    # Создаём объект datetime для введённой даты в текущем году с временем по умолчанию
    deadline_this_year = datetime(now.year, month, day, default_hour, default_minute, 0)

    # Если дата уже прошла в этом году, переносим на следующий год
    if deadline_this_year < now:
        deadline_this_year = deadline_this_year.replace(year=now.year + 1)

    return deadline_this_year.strftime('%Y-%m-%d %H:%M:%S')

# Пример использования (для тестирования)
if __name__ == "__main__":
    print(f"Сегодня: {datetime.now()}")
    print(f"Парсинг '24.10': {parse_deadline('24.10')}")
    print(f"Парсинг '01.01': {parse_deadline('01.01')}")
    print(f"Парсинг '32.13': {parse_deadline('32.13')}") # Невалидно
    print(f"Парсинг 'invalid': {parse_deadline('invalid')}") # Невалидно