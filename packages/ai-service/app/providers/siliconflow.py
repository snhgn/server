import asyncio
import json
from typing import AsyncGenerator

import httpx

from ..config import settings
from .base import BaseProvider


class SiliconFlowProvider(BaseProvider):
    """硅基流动平台 Provider（OpenAI 兼容 HTTP）。
    用于专用任务：翻译（tencent/Hunyuan-MT-7B）、总结（Qwen/Qwen3-8B）。
    """

    def __init__(self, name: str, model: str) -> None:
        self.name = name
        self.model = model
        self.api_key = settings.SILICONFLOW_API_KEY
        self.base_url = settings.SILICONFLOW_BASE_URL.rstrip("/")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(self, message: str, timeout: float = settings.REQUEST_TIMEOUT) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": message}],
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self, message: str, timeout: float = 120.0
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": message}],
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get("content")
                    except Exception:
                        continue
                    if delta:
                        yield delta
