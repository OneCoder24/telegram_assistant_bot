"""
Парсер напоминаний — извлекает дату, время и текст из естественного языка.
Использует Groq LLM для понимания естественного языка.
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config import Config

logger = logging.getLogger(__name__)


async def parse_reminder(text: str) -> Optional[dict]:
    """
    Парсит текст напоминания и извлекает дату, время и содержимое.
    
    Args:
        text: Текст напоминания на естественном языке
        
    Returns:
        Словарь с ключами: datetime (ISO формат), text (содержимое)
        или None при ошибке
    """
    url = f"{Config.GROQ_BASE_URL}/chat/completions"
    
    # Системный промпт для парсинга
    system_prompt = """Ты — парсер напоминаний. Извлеки из текста дату, время и содержимое напоминания.

Правила:
- Определи дату и время напоминания из контекста
- Если указано "завтра", "послезавтра" — вычисли дату относительно сегодня
- Если указано "через N часов/минут" — вычисли время относительно сейчас
- Если время не указано, используй 09:00 по умолчанию
- Извлеки основное содержимое напоминания (что нужно сделать)
- Верни JSON в формате: {"datetime": "YYYY-MM-DDTHH:MM:SS", "text": "содержимое"}
- НЕ добавляй никаких пояснений, только JSON

Примеры:
- "Напомни завтра в 15:00 позвонить клиенту" -> {"datetime": "2026-09-04T15:00:00", "text": "Позвонить клиенту"}
- "Через 2 часа встреча с командой" -> {"datetime": "2026-09-03T14:00:00", "text": "Встреча с командой"}
- "В пятницу сдать отчёт" -> {"datetime": "2026-09-05T09:00:00", "text": "Сдать отчёт"}

Сейчас: {current_datetime}"""
    
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_prompt = system_prompt.replace("{current_datetime}", current_datetime)
    
    payload = {
        "model": Config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "temperature": 0.1,
        "max_tokens": 200
    }
    
    headers = {
        "Authorization": f"Bearer {Config.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=Config.API_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            result_text = data["choices"][0]["message"]["content"].strip()
            
            # Парсим JSON из ответа
            # Убираем возможные markdown-обёртки
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
                result_text = result_text.strip()
            
            parsed = json.loads(result_text)
            
            # Проверяем наличие необходимых полей
            if "datetime" not in parsed or "text" not in parsed:
                logger.error(f"Неверный формат ответа от LLM: {parsed}")
                return None
            
            # Проверяем валидность datetime
            try:
                datetime.fromisoformat(parsed["datetime"])
            except ValueError:
                logger.error(f"Неверный формат datetime: {parsed['datetime']}")
                return None
            
            return parsed
            
    except httpx.TimeoutException:
        logger.error("Таймаут при парсинге напоминания")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP ошибка при парсинге напоминания: {e.response.status_code}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Неизвестная ошибка при парсинге напоминания: {e}")
        return None
