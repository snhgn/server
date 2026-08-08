import httpx

from ..config import settings
from .base import BaseProvider


class GeminiProvider(BaseProvider):
    """Google Gemini Provider：使用官方 HTTP 接口（generativelanguage.googleapis.com）"""

    name = "gemini"

    def __init__(self) -> None:
        self.model = settings.GEMINI_MODEL
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    async def chat(self, message: str, timeout: float = settings.REQUEST_TIMEOUT) -> str:
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": settings.GEMINI_API_KEY,
        }
        payload = {
            "contents": [{"parts": [{"text": message}]}],
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(self.url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
