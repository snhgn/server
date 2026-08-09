import json
from typing import AsyncGenerator

import httpx

from ..config import settings
from .base import BaseProvider


class GeminiProvider(BaseProvider):
    """Google Gemini Provider：使用官方 HTTP 接口"""

    name = "gemini"

    def __init__(self) -> None:
        self.model = settings.GEMINI_MODEL
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        self.stream_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?alt=sse"

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

    async def chat_stream(
        self, message: str, timeout: float = 120.0
    ) -> AsyncGenerator[str, None]:
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": settings.GEMINI_API_KEY,
        }
        payload = {
            "contents": [{"parts": [{"text": message}]}],
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", self.stream_url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "text" in part:
                                    yield part["text"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

    async def chat_with_images(
        self, message: str, images: list[str], timeout: float = 60.0
    ) -> str:
        """多模态：文本 + 图片 base64 列表"""
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": settings.GEMINI_API_KEY,
        }
        parts: list[dict] = [{"text": message}]
        for img_b64 in images:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_b64}})
        payload = {"contents": [{"parts": parts}]}
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(self.url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
