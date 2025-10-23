# handlers/weather_handler.py
from logger_config import get_logger
from modules.weather import get_formatted_current_weather, get_formatted_forecast, get_formatted_weather_by_coords

logger = get_logger()

# Вспомогательная функция для клавиатуры отмены/действий, нужно будет получить из bot.py
get_weather_inline_keyboard_func = None
def set_weather_inline_keyboard_func(func):
    global get_weather_inline_keyboard_func
    get_weather_inline_keyboard_func = func

def handle_weather_callback(data, chat_id, message_id, user_id, user_states, send_message_func, edit_message_text_func, get_weather_keyboard_func):
    """Обрабатывает callback_query, связанные с погодой."""
    # Устанавливаем функцию клавиатуры, если она передана
    if get_weather_keyboard_func:
        set_weather_inline_keyboard_func(get_weather_keyboard_func)

    if data == 'weather_menu':
        # Показываем текущую погоду и inline-клавиатуру
        import asyncio
        # Используем run_until_complete для вызова async функции
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            weather_text = loop.run_until_complete(get_formatted_current_weather(user_id))
        finally:
            loop.close()

        keyboard = get_weather_inline_keyboard_func() if get_weather_inline_keyboard_func else None
        send_message_func(chat_id, weather_text, keyboard)

    elif data == 'weather_forecast_3days':
        # Показываем прогноз на 3 дня
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            forecast_text = loop.run_until_complete(get_formatted_forecast(user_id))
        finally:
            loop.close()

        # Отправляем прогноз как новое сообщение
        send_message_func(chat_id, forecast_text, get_weather_inline_keyboard_func() if get_weather_inline_keyboard_func else None)

    elif data == 'weather_by_location':
        # Запрашиваем геолокацию у пользователя
        keyboard = {"keyboard": [[{"text": "📍 Отправить местоположение", "request_location": True}]], "resize_keyboard": True, "one_time_keyboard": True}
        send_message_func(chat_id, "📍 Пожалуйста, отправьте ваше местоположение:", keyboard)

    elif data == 'weather_back_to_main':
        # Возвращаемся в главное меню
        from bot import get_main_reply_keyboard # Импортируем из bot.py
        send_message_func(chat_id, "Глaвное меню:", get_main_reply_keyboard())


def handle_weather_message_input(text, chat_id, user_id, user_states, send_message_func, edit_message_text_func, get_weather_keyboard_func):
    """Обрабатывает текстовые сообщения и геолокацию для погоды."""
    # Проверяем, если это геолокация
    # В bot.py нужно будет передавать location отдельно или парсить из message
    # Пока что обрабатываем только текст. Геолокация будет обрабатываться в bot.py напрямую
    # и вызывать специальную функцию здесь.

    # Если пользователь отправил текст "📍 Отправить местоположение" или подобный,
    # это не геолокация, а просто текст. Настоящая геолокация - это объект message.location
    # который нужно обрабатывать отдельно в bot.py.

    # В данном обработчике текстовых сообщений для погоды особо делать нечего,
    # кроме как игнорировать или вернуть в главное меню, если пользователь "заблудился".
    # Например, если он нажал "Погода", получил inline-кнопки, но вместо них начал печатать текст.

    current_state = user_states.get((user_id, chat_id))
    if current_state and current_state.startswith("waiting_for_weather_"):
        # Если пользователь был в состоянии ожидания ввода, связанного с погодой (например, если бы была такая логика)
        # Сейчас такой логики нет, но на будущее оставим проверку.
        pass # Пока ничего не делаем

    # Если текст не распознан, можно просто проигнорировать или отправить сообщение
    # logger.warning(f"Нераспознанное текстовое сообщение в модуле погоды от user_id {user_id}: {text}")
    # send_message_func(chat_id, "Неизвестная команда в модуле погоды. Вернитесь в главное меню.", get_weather_inline_keyboard_func() if get_weather_inline_keyboard_func else None)
    # Или просто ничего не делать, как и задумано для inline-меню.


# Функция для обработки полученной геолокации (будет вызываться из bot.py)
def handle_weather_location(user_id, chat_id, latitude, longitude, send_message_func):
    """Обрабатывает полученные координаты геолокации."""
    try:
        logger.info(f"Получена геолокация от user_id {user_id}: {latitude}, {longitude}")

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            weather_text = loop.run_until_complete(get_formatted_weather_by_coords(user_id, latitude, longitude))
        finally:
            loop.close()

        # Отправляем погоду по координатам
        # После отправки погоды возвращаем inline-клавиатуру погоды
        keyboard = get_weather_inline_keyboard_func() if get_weather_inline_keyboard_func else None
        send_message_func(chat_id, weather_text, keyboard)

    except Exception as e:
        logger.error(f"Ошибка при обработке геолокации для user_id {user_id}: {e}")
        send_message_func(chat_id, "❌ Ошибка при получении погоды по местоположению.", get_weather_inline_keyboard_func() if get_weather_inline_keyboard_func else None)

# Функция для отправки ежедневного уведомления (будет вызываться из планировщика)
async def trigger_daily_notification(user_id, send_message_func):
    """Триггер для отправки ежедневного уведомления о погоде."""
    # Эта функция будет вызываться планировщиком
    # Она должна быть async, так как вызывает async функции из modules/weather.py
    from modules.weather import send_daily_weather_notification
    await send_daily_weather_notification(user_id, send_message_func)