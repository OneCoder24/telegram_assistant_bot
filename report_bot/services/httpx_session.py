"""
Кастомная HTTPX-сессия для aiogram.
Используется как альтернатива aiohttp, если возникают проблемы с подключением.
"""
from typing import Any, AsyncIterator, Optional, TYPE_CHECKING

import httpx
from aiogram.client.session.base import BaseSession
from aiogram.methods.base import TelegramMethod

if TYPE_CHECKING:
    from aiogram.client.bot import Bot


class HttpxSession(BaseSession):
    """HTTPX-сессия для aiogram"""
    
    def __init__(
        self,
        timeout: float = 60.0,
        proxy: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        super().__init__()
        self._timeout = timeout
        self._proxy = proxy
        self._client: Optional[httpx.AsyncClient] = None
    
    async def create_client(self) -> None:
        """Создаёт HTTPX-клиент"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                proxy=self._proxy,
                follow_redirects=True
            )
    
    async def close(self) -> None:
        """Закрывает HTTPX-клиент"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def make_request(
        self,
        bot: "Bot",
        method: TelegramMethod[Any],
        timeout: Optional[int] = None
    ) -> Any:
        """Выполняет запрос к Telegram API"""
        await self.create_client()
        
        # Конструируем URL для Telegram API
        url = f"https://api.telegram.org/bot{bot.token}/{method.__api_method__}"
        
        # Подготовка данных запроса
        request_data = method.model_dump(warnings=False, exclude_none=True)
        
        # Выполняем запрос
        response = await self._client.post(
            url,
            json=request_data,
            timeout=timeout or self._timeout
        )
        response.raise_for_status()
        
        # Парсим ответ
        response_data = response.json()
        
        # Проверяем успешность ответа
        if not response_data.get("ok"):
            raise Exception(f"Telegram API error: {response_data.get('description')}")
        
        # Десериализуем результат в правильную модель
        result_data = response_data.get("result")
        
        # Получаем тип возврата из метода
        return_type = method.__return_type__
        
        # Десериализуем в нужный тип
        if hasattr(return_type, "model_validate"):
            return return_type.model_validate(result_data)
        else:
            return result_data
    
    async def stream_content(
        self,
        url: str,
        headers: Optional[dict[str, Any]] = None,
        timeout: float = 30.0,
        chunk_size: Optional[int] = None,
        raise_for_status: bool = True
    ) -> AsyncIterator[bytes]:
        """Потоковая загрузка контента"""
        await self.create_client()
        
        async with self._client.stream(
            "GET",
            url,
            headers=headers,
            timeout=timeout
        ) as response:
            if raise_for_status:
                response.raise_for_status()
            
            async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                yield chunk
