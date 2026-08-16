import json
from typing import AsyncGenerator

import httpx

from ..config import settings
from .base import BaseProvider

# ---- 共享 AsyncClient：进程内连接复用（keep-alive），所有实例（翻译/总结）共用一个连接池 ----
# trust_env=True 默认读取容器代理环境变量；NO_PROXY 已在 compose 中排除国内域名，
# siliconflow.cn 直连、不走代理。
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


def _req_timeout(t: float) -> httpx.Timeout:
    return httpx.Timeout(connect=10.0, read=t, write=30.0, pool=10.0)


async def aclose_client() -> None:
    """应用关闭时释放连接池（FastAPI lifespan 调用）"""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


class SiliconFlowProvider(BaseProvider):
    """硅基流动平台 Provider（OpenAI 兼容 HTTP）。
    用于专用任务：翻译（tencent/Hunyuan-MT-7B）、总结（Qwen/Qwen3-8B）。
    """

    def __init__(self, name: str, model: str) -> None:
        self.name = name
        self.model = model
        self.api_key = settings.SILICONFLOW_API_KEY
        self.base_url = settings.SILICONFLOW_BASE_URL.rstrip("/")

    @property
    def primary_text_model(self) -> str | None:
        return self.model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: list[dict],
        timeout: float = settings.REQUEST_TIMEOUT,
        system: str | None = None,
    ) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        payload = {
            "model": self.model,
            "messages": msgs,
        }
        client = _get_client()
        resp = await client.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=_req_timeout(timeout),
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        messages: list[dict],
        timeout: float = 120.0,
        system: str | None = None,
    ) -> AsyncGenerator[str, None]:
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        payload = {
            "model": self.model,
            "messages": msgs,
            "stream": True,
        }
        client = _get_client()
        async with client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=_req_timeout(timeout),
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
