"""
Клиент для работы с Groq API.
Поддерживает генерацию текста (LLM) и распознавание речи (Whisper).
"""
import logging
from pathlib import Path
from typing import Optional

import httpx

from config import Config

logger = logging.getLogger(__name__)


class GroqClient:
    """Асинхронный клиент для Groq API"""
    
    def __init__(self) -> None:
        self.api_key = Config.GROQ_API_KEY
        self.base_url = Config.GROQ_BASE_URL
        self.timeout = Config.API_TIMEOUT
    
    async def generate_report(self, system_prompt: str, notes_text: str) -> Optional[str]:
        """
        Генерирует отчёт через LLM.
        
        Args:
            system_prompt: Системный промпт с инструкциями
            notes_text: Текст заметок за день
            
        Returns:
            Сгенерированный текст отчёта или None при ошибке
        """
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": Config.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": notes_text}
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                return data["choices"][0]["message"]["content"]
                
        except httpx.TimeoutException:
            logger.error("Таймаут при запросе к Groq LLM")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка от Groq: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при запросе к Groq LLM: {e}")
            return None
    
    async def transcribe_audio(self, audio_file_path: Path) -> Optional[str]:
        """
        Распознаёт голосовое сообщение через Whisper API.
        
        Args:
            audio_file_path: Путь к аудиофайлу (.ogg)
            
        Returns:
            Распознанный текст или None при ошибке
        """
        url = f"{self.base_url}/audio/transcriptions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                with open(audio_file_path, "rb") as audio_file:
                    files = {"file": ("voice.ogg", audio_file, "audio/ogg")}
                    data = {"model": Config.GROQ_WHISPER_MODEL}
                    
                    response = await client.post(
                        url,
                        files=files,
                        data=data,
                        headers=headers
                    )
                    response.raise_for_status()
                    
                    result = response.json()
                    return result.get("text")
                    
        except httpx.TimeoutException:
            logger.error("Таймаут при запросе к Groq Whisper")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка от Groq Whisper: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при запросе к Groq Whisper: {e}")
            return None


def load_report_prompt() -> str:
    """Загружает шаблон промпта из файла"""
    prompt_path = Config.PROMPT_PATH
    
    if not prompt_path.exists():
        logger.warning(f"Файл промпта не найден: {prompt_path}, используется встроенный")
        return _default_prompt()
    
    return prompt_path.read_text(encoding="utf-8")


def _default_prompt() -> str:
    """Встроенный промпт на случай отсутствия файла"""
    return """Ты — помощник разработчика робототехники. На основе сырых заметок за день составь структурированный отчёт.

Формат:
## 📋 Отчёт за {date}

### ✅ Выполнено
- [пункты]

### 🐛 Проблемы и блокеры
- [если есть]

### 💡 Идеи и наблюдения
- [если есть]

### 📌 План на завтра
- [если можно вывести из контекста]

Правила:
- Не выдумывай факты, которых нет в заметках.
- Сохраняй технические термины как есть.
- Если заметок мало — не раздувай отчёт, будь лаконичен.
- Язык отчёта — русский.

Заметки за день:
{notes}"""
