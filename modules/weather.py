# modules/weather.py
from logger_config import get_logger
from database import get_db
from utils.weather_api import get_current_weather, get_weather_forecast, get_current_weather_by_coords

logger = get_logger()
db = get_db()

# --- Функции для получения и форматирования погоды ---

async def get_formatted_current_weather(user_id):
    """
    Получает и форматирует текущую погоду для пользователя.
    Использует город по умолчанию из настроек.
    """
    try:
        settings = db.get_settings(user_id)
        default_city = settings.get("main_city", "Moscow") # Используем main_city как default_city

        weather_data = await get_current_weather(default_city)
        if not weather_
            return f"❌ Не удалось получить погоду для города '{default_city}'. Проверьте название города в настройках."

        # Форматируем строку ответа
        city_name = weather_data['city']
        temp = weather_data['temperature']
        apparent_temp = weather_data['apparent_temperature']
        wind_speed = weather_data['wind_speed']
        # precipitation = weather_data['precipitation'] # Общее количество осадков
        # rain = weather_data['rain'] # Дождь
        # showers = weather_data['showers'] # Ливни
        # snowfall = weather_data['snowfall'] # Снег

        # Определяем тип осадков (упрощённо)
        precip_type = "Без осадков"
        if weather_data['rain'] and weather_data['rain'] > 0:
            precip_type = f"Дождь {weather_data['rain']} мм"
        elif weather_data['showers'] and weather_data['showers'] > 0:
            precip_type = f"Ливни {weather_data['showers']} мм"
        elif weather_data['snowfall'] and weather_data['snowfall'] > 0:
            precip_type = f"Снег {weather_data['snowfall']} см"
        elif weather_data['precipitation'] and weather_data['precipitation'] > 0:
             precip_type = f"Осадки {weather_data['precipitation']} мм"


        response_text = (
            f"🌤️ Погода в {city_name}:\n"
            f"🌡️ Температура: {temp}°C (ощущается как {apparent_temp}°C)\n"
            f"💨 Ветер: {wind_speed} км/ч\n"
            f"🌧️ Осадки: {precip_type}\n"
            # Можно добавить больше информации
        )
        return response_text

    except Exception as e:
        logger.error(f"Ошибка при получении/форматировании текущей погоды для user_id {user_id}: {e}")
        return "❌ Произошла ошибка при получении погоды."

async def get_formatted_forecast(user_id):
    """
    Получает и форматирует прогноз погоды на 3 дня для пользователя.
    Использует город по умолчанию из настроек.
    """
    try:
        settings = db.get_settings(user_id)
        default_city = settings.get("main_city", "Moscow")

        forecast_data = await get_weather_forecast(default_city, days=3)
        if not forecast_
            return f"❌ Не удалось получить прогноз погоды для города '{default_city}'."

        city_name = forecast_data['city']
        forecast_list = forecast_data['forecast']

        response_lines = [f"📅 Прогноз погоды в {city_name} на 3 дня:"]
        for day_data in forecast_list:
            date_str = day_data['date']
            # Преобразуем дату из строки в объект datetime для форматирования
            try:
                date_obj = datetime.fromisoformat(date_str)
                formatted_date = date_obj.strftime("%d.%m.%Y")
            except ValueError:
                formatted_date = date_str # Если не удалось преобразовать, оставляем как есть

            temp_max = day_data['temperature_max']
            temp_min = day_data['temperature_min']
            precip_sum = day_data['precipitation_sum']
            wind_max = day_data['wind_speed_max']

            # Определяем тип осадков для дня (упрощённо)
            precip_desc = "Без осадков"
            if precip_sum and precip_sum > 0:
                precip_desc = f"{precip_sum} мм"

            response_lines.append(
                f"🗓 {formatted_date}:\n"
                f"  🌡️ {temp_min}°C .. {temp_max}°C\n"
                f"  💧 Осадки: {precip_desc}\n"
                f"  💨 Ветер макс.: {wind_max} км/ч"
            )

        return "\n\n".join(response_lines)

    except Exception as e:
        logger.error(f"Ошибка при получении/форматировании прогноза для user_id {user_id}: {e}")
        return "❌ Произошла ошибка при получении прогноза погоды."

async def get_formatted_weather_by_coords(user_id, latitude, longitude):
    """
    Получает и форматирует текущую погоду по координатам.
    """
    try:
        weather_data = await get_current_weather_by_coords(latitude, longitude)
        if not weather_
            return "❌ Не удалось получить погоду по вашему местоположению."

        city_name = weather_data['city'] # "Ваше местоположение"
        temp = weather_data['temperature']
        apparent_temp = weather_data['apparent_temperature']
        wind_speed = weather_data['wind_speed']
        # precipitation = weather_data['precipitation']
        # rain = weather_data['rain']
        # showers = weather_data['showers']
        # snowfall = weather_data['snowfall']

        # Определяем тип осадков (упрощённо)
        precip_type = "Без осадков"
        if weather_data['rain'] and weather_data['rain'] > 0:
            precip_type = f"Дождь {weather_data['rain']} мм"
        elif weather_data['showers'] and weather_data['showers'] > 0:
            precip_type = f"Ливни {weather_data['showers']} мм"
        elif weather_data['snowfall'] and weather_data['snowfall'] > 0:
            precip_type = f"Снег {weather_data['snowfall']} см"
        elif weather_data['precipitation'] and weather_data['precipitation'] > 0:
             precip_type = f"Осадки {weather_data['precipitation']} мм"

        response_text = (
            f"📍 Погода в {city_name} (по координатам):\n"
            f"🌡️ Температура: {temp}°C (ощущается как {apparent_temp}°C)\n"
            f"💨 Ветер: {wind_speed} км/ч\n"
            f"🌧️ Осадки: {precip_type}\n"
            # Можно добавить больше информации
        )
        return response_text

    except Exception as e:
        logger.error(f"Ошибка при получении/форматировании погоды по координатам для user_id {user_id}: {e}")
        return "❌ Произошла ошибка при получении погоды по местоположению."

# --- Функция для ежедневных уведомлений (заглушка) ---
async def send_daily_weather_notification(user_id, send_message_func):
    """
    Отправляет ежедневное уведомление о погоде.
    Это заглушка, которая будет вызываться планировщиком.
    """
    try:
        # Проверяем, включены ли уведомления
        settings = db.get_settings(user_id)
        if not settings.get("daily_weather_enabled", False):
            logger.debug(f"Ежедневные уведомления о погоде отключены для user_id {user_id}.")
            return

        # Получаем форматированную погоду
        weather_message = await get_formatted_current_weather(user_id)
        # Отправляем сообщение пользователю
        # send_message_func(chat_id=user_id, text=weather_message, reply_markup=None, parse_mode=None)
        # NOTE: send_message_func должна быть передана из bot.py и иметь правильную сигнатуру
        logger.info(f"Ежедневное уведомление о погоде отправлено user_id {user_id}.")
        # В реальности, send_message_func нужно будет вызвать правильно.
        # Пока просто логируем.
        print(f"[DAILY_WEATHER] Отправка user_id {user_id}: {weather_message}")

    except Exception as e:
        logger.error(f"Ошибка при отправке ежедневного уведомления о погоде для user_id {user_id}: {e}")


# Пример использования (для тестирования)
if __name__ == "__main__":
    import asyncio
    from datetime import datetime # Импортируем datetime для теста

    async def test_module():
        print("Тестирование модуля weather...")
        # Тестовые user_id
        test_user_id = 123456789 # Замените на реальный user_id для теста

        print("\n--- Текущая погода (по умолчанию) ---")
        current_msg = asyncio.run(get_formatted_current_weather(test_user_id))
        print(current_msg)

        print("\n--- Прогноз на 3 дня (по умолчанию) ---")
        forecast_msg = asyncio.run(get_formatted_forecast(test_user_id))
        print(forecast_msg)

        print("\n--- Погода по координатам ---")
        lat, lon = 55.7558, 37.6176 # Москва
        coords_msg = asyncio.run(get_formatted_weather_by_coords(test_user_id, lat, lon))
        print(coords_msg)

        print("\n--- Ежедневное уведомление (заглушка) ---")
        # send_daily_weather_notification не может быть протестирована без send_message_func
        # asyncio.run(send_daily_weather_notification(test_user_id, lambda **kwargs: print(f"Отправлено: {kwargs}")))

    # asyncio.run(test_module()) # Закомментировано, так как основной бот не использует asyncio.run напрямую