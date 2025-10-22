# utils/reminders_datetime_parser.py
from datetime import datetime, timedelta
from config import REMINDER_DEFAULT_TIME # Импортируем время по умолчанию из config.py
import re

def parse_reminder_time(input_text, default_time_str=None):
    """
    Парсит строку ввода времени напоминания в 'YYYY-MM-DD HH:MM:SS'.
    Поддерживаемые форматы:
    - '5 мин' / '1 ч' (от текущего времени)
    - '18:15' (сегодня в 18:15)
    - 'завтра 10:00' (завтра в 10:00)
    - '15 октября' (15 октября текущего года в REMINDER_DEFAULT_TIME)
    """
    if default_time_str is None:
        default_time_str = REMINDER_DEFAULT_TIME # Используем время из config.py

    input_text = input_text.strip().lower()
    now = datetime.now()

    # Проверяем формат "HH:MM" (сегодня)
    time_match = re.search(r'\b(\d{1,2}):(\d{2})\b', input_text)
    if time_match:
        hour, minute = map(int, time_match.groups())
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            reminder_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # Если время уже прошло сегодня, переносим на завтра
            if reminder_time <= now:
                reminder_time = reminder_time + timedelta(days=1)
            return reminder_time.strftime('%Y-%m-%d %H:%M:%S')

    # Проверяем формат "завтра HH:MM"
    tomorrow_match = re.search(r'\bзавтра\s+(\d{1,2}):(\d{2})\b', input_text)
    if tomorrow_match:
        hour, minute = map(int, tomorrow_match.groups())
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            reminder_time = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            return reminder_time.strftime('%Y-%m-%d %H:%M:%S')

    # Проверяем формат "N мин" / "N ч"
    # Ищем число с единицей времени в любом месте строки
    time_delta_match = re.search(r'(\d+)\s*(мин|ч|час)', input_text)
    if time_delta_match:
        value, unit = time_delta_match.groups()
        value = int(value)
        if unit in ['мин']:
            delta = timedelta(minutes=value)
        elif unit in ['ч', 'час']:
            delta = timedelta(hours=value)
        else:
            return None # Неизвестная единица

        reminder_time = now + delta
        return reminder_time.strftime('%Y-%m-%d %H:%M:%S')

    # Проверяем формат "DD месяц" (в REMINDER_DEFAULT_TIME)
    # Словарь для месяцев (можно расширить для разных языков)
    months = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
        'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
    }
    # Регулярное выражение для DD месяца
    date_match = re.search(r'(\d{1,2})\s+(' + '|'.join(months.keys()) + ')', input_text)
    if date_match:
        day, month_str = date_match.groups()
        day = int(day)
        month = months[month_str]

        # Проверяем валидность числа и месяца
        if not (1 <= day <= 31):
            return None

        try:
            default_hour, default_minute = map(int, default_time_str.split(':'))
        except ValueError:
            default_hour, default_minute = 23, 55

        # Создаём объект datetime для введённой даты в текущем году с временем по умолчанию
        reminder_time = datetime(now.year, month, day, default_hour, default_minute, 0)

        # Если дата уже прошла в этом году, переносим на следующий год
        if reminder_time < now:
            reminder_time = reminder_time.replace(year=now.year + 1)

        return reminder_time.strftime('%Y-%m-%d %H:%M:%S')

    # Если ни один формат не подошёл
    return None

# Пример использования (для тестирования)
if __name__ == "__main__":
    print(f"Сейчас: {datetime.now()}")
    print(f"Парсинг '5 мин': {parse_reminder_time('5 мин')}")
    print(f"Парсинг '1 ч': {parse_reminder_time('1 ч')}")
    print(f"Парсинг '18:15': {parse_reminder_time('18:15')}")
    print(f"Парсинг 'завтра 10:00': {parse_reminder_time('завтра 10:00')}")
    print(f"Парсинг '24 октября': {parse_reminder_time('24 октября')}")
    print(f"Парсинг '01 января': {parse_reminder_time('01 января')}")
    print(f"Парсинг 'invalid': {parse_reminder_time('invalid')}") # Невалидно