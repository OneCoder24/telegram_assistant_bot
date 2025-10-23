# utils/weather_api.py
import requests
from datetime import datetime, timedelta

# Open-Meteo API endpoint
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

async def get_current_weather(city_name):
    """
    Получает текущую погоду для заданного города.
    Использует Open-Meteo Geocoding API для поиска координат.
    :param city_name: Название города (строка)
    :return: Словарь с данными о погоде или None в случае ошибки.
    """
    try:
        # 1. Получаем координаты города (простой поиск)
        geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
        geocode_params = {
            "name": city_name,
            "count": 1,
            "language": "ru", # Указываем язык для локализации
            "format": "json"
        }
        geo_response = requests.get(geocode_url, params=geocode_params)
        geo_data = geo_response.json()

        if not geo_data.get('results') or len(geo_data['results']) == 0:
            print(f"Город '{city_name}' не найден.")
            return None

        location = geo_data['results'][0]
        latitude = location['latitude']
        longitude = location['longitude']
        resolved_city_name = location['name'] # Может отличаться от введённого

        # 2. Получаем погоду по координатам
        weather_params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "timezone": "auto", # Используем часовой пояс по координатам
            "forecast_days": 1
        }

        weather_response = requests.get(OPEN_METEO_BASE_URL, params=weather_params)
        weather_data = weather_response.json()

        if 'current' not in weather_
            print(f"Ошибка получения погоды для {resolved_city_name} ({latitude}, {longitude})")
            return None

        current = weather_data['current']
        # hourly = weather_data.get('hourly', {}) # Для получения прогноза на ближайшие часы

        # Форматируем данные
        weather_info = {
            "city": resolved_city_name,
            "latitude": latitude,
            "longitude": longitude,
            "temperature": current['temperature_2m'],
            "apparent_temperature": current['apparent_temperature'],
            "is_day": current['is_day'], # 1 - день, 0 - ночь
            "precipitation": current['precipitation'], # Общее количество осадков (мм)
            "rain": current['rain'], # Дождь (мм)
            "showers": current['showers'], # Ливни (мм)
            "snowfall": current['snowfall'], # Снег (см)
            "weather_code": current['weather_code'], # Код погоды WMO
            "cloud_cover": current['cloud_cover'], # Облачность (%)
            "pressure_msl": current['pressure_msl'], # Давление на уровне моря (гПа)
            "surface_pressure": current['surface_pressure'], # Давление на поверхности (гПа)
            "wind_speed": current['wind_speed_10m'], # Скорость ветра (км/ч)
            "wind_direction": current['wind_direction_10m'], # Направление ветра (градусы)
            "wind_gusts": current['wind_gusts_10m'], # Порывы ветра (км/ч)
            "time": current['time'], # Время измерения (ISO)
            "units": weather_data.get('current_units', {}) # Единицы измерения
        }

        return weather_info

    except Exception as e:
        print(f"Ошибка при получении погоды для '{city_name}': {e}")
        return None

async def get_weather_forecast(city_name, days=3):
    """
    Получает прогноз погоды на несколько дней для заданного города.
    :param city_name: Название города (строка)
    :param days: Количество дней прогноза (по умолчанию 3)
    :return: Словарь с данными о прогнозе или None в случае ошибки.
    """
    try:
        # 1. Получаем координаты города
        geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
        geocode_params = {
            "name": city_name,
            "count": 1,
            "language": "ru",
            "format": "json"
        }
        geo_response = requests.get(geocode_url, params=geocode_params)
        geo_data = geo_response.json()

        if not geo_data.get('results') or len(geo_data['results']) == 0:
            print(f"Город '{city_name}' не найден для прогноза.")
            return None

        location = geo_data['results'][0]
        latitude = location['latitude']
        longitude = location['longitude']
        resolved_city_name = location['name']

        # 2. Получаем прогноз по координатам
        forecast_params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum,rain_sum,showers_sum,snowfall_sum,precipitation_hours,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,sunrise,sunset,uv_index_max",
            "timezone": "auto",
            "forecast_days": days
        }

        forecast_response = requests.get(OPEN_METEO_BASE_URL, params=forecast_params)
        forecast_data = forecast_response.json()

        if 'daily' not in forecast_
            print(f"Ошибка получения прогноза для {resolved_city_name} ({latitude}, {longitude})")
            return None

        daily = forecast_data['daily']
        # Форматируем данные
        forecast_list = []
        for i in range(len(daily['time'])):
            day_forecast = {
                "date": daily['time'][i],
                "weather_code": daily['weather_code'][i],
                "temperature_max": daily['temperature_2m_max'][i],
                "temperature_min": daily['temperature_2m_min'][i],
                "apparent_temperature_max": daily['apparent_temperature_max'][i],
                "apparent_temperature_min": daily['apparent_temperature_min'][i],
                "precipitation_sum": daily['precipitation_sum'][i],
                "rain_sum": daily['rain_sum'][i],
                "showers_sum": daily['showers_sum'][i],
                "snowfall_sum": daily['snowfall_sum'][i],
                "precipitation_hours": daily['precipitation_hours'][i],
                "precipitation_probability_max": daily['precipitation_probability_max'][i],
                "wind_speed_max": daily['wind_speed_10m_max'][i],
                "wind_gusts_max": daily['wind_gusts_10m_max'][i],
                "wind_direction_dominant": daily['wind_direction_10m_dominant'][i],
                "sunrise": daily['sunrise'][i],
                "sunset": daily['sunset'][i],
                "uv_index_max": daily['uv_index_max'][i],
                "units": forecast_data.get('daily_units', {})
            }
            forecast_list.append(day_forecast)

        return {
            "city": resolved_city_name,
            "latitude": latitude,
            "longitude": longitude,
            "forecast": forecast_list
        }

    except Exception as e:
        print(f"Ошибка при получении прогноза для '{city_name}': {e}")
        return None

async def get_current_weather_by_coords(latitude, longitude):
    """
    Получает текущую погоду по координатам.
    :param latitude: Широта (float)
    :param longitude: Долгота (float)
    :return: Словарь с данными о погоде или None в случае ошибки.
    """
    try:
        # Получаем погоду по координатам
        weather_params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "timezone": "auto",
            "forecast_days": 1
        }

        weather_response = requests.get(OPEN_METEO_BASE_URL, params=weather_params)
        weather_data = weather_response.json()

        if 'current' not in weather_data:
            print(f"Ошибка получения погоды для координат ({latitude}, {longitude})")
            return None

        current = weather_data['current']

        # Форматируем данные (без названия города)
        weather_info = {
            "city": "Ваше местоположение", # Заглушка
            "latitude": latitude,
            "longitude": longitude,
            "temperature": current['temperature_2m'],
            "apparent_temperature": current['apparent_temperature'],
            "is_day": current['is_day'],
            "precipitation": current['precipitation'],
            "rain": current['rain'],
            "showers": current['showers'],
            "snowfall": current['snowfall'],
            "weather_code": current['weather_code'],
            "cloud_cover": current['cloud_cover'],
            "pressure_msl": current['pressure_msl'],
            "surface_pressure": current['surface_pressure'],
            "wind_speed": current['wind_speed_10m'],
            "wind_direction": current['wind_direction_10m'],
            "wind_gusts": current['wind_gusts_10m'],
            "time": current['time'],
            "units": weather_data.get('current_units', {})
        }

        return weather_info

    except Exception as e:
        print(f"Ошибка при получении погоды по координатам ({latitude}, {longitude}): {e}")
        return None

# Пример использования (для тестирования)
if __name__ == "__main__":
    import asyncio

    async def main():
        print("Тестирование модуля weather_api...")
        city = "Москва"
        print(f"--- Текущая погода в {city} ---")
        current_weather = await get_current_weather(city)
        if current_weather:
            print(current_weather)
        else:
            print("Не удалось получить текущую погоду.")

        print("\n--- Прогноз погоды на 3 дня в Москве ---")
        forecast = await get_weather_forecast(city, days=3)
        if forecast:
            print(forecast)
        else:
            print("Не удалось получить прогноз.")

        print("\n--- Погода по координатам (Москва, примерно) ---")
        lat, lon = 55.7558, 37.6176
        weather_by_coords = await get_current_weather_by_coords(lat, lon)
        if weather_by_coords:
            print(weather_by_coords)
        else:
            print("Не удалось получить погоду по координатам.")

    asyncio.run(main())