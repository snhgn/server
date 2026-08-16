import json
from typing import AsyncGenerator

import httpx

from ..config import settings
from .base import BaseProvider

# 允许调用的模型白名单（禁止调用白名单之外的其他模型）
ALLOWED_MODELS = {
    "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite", "gemini-3-flash-preview",
    "gemini-2.5-pro", "gemini-2.5-flash",
}


def _require_allowed(model: str) -> str:
    if model not in ALLOWED_MODELS:
        raise ValueError(
            f"Model '{model}' is not in the allowlist for gemini. "
            f"Allowed: {sorted(ALLOWED_MODELS)}"
        )
    return model


# ---- 共享 AsyncClient：进程内连接复用（keep-alive），避免每次调用重新 TCP+TLS ----
# 代理统一在这一层生效：httpx 默认 trust_env=True，读取容器注入的
# HTTP_PROXY/HTTPS_PROXY/NO_PROXY 环境变量（Gemini 经本机 clash 代理出网）。
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
    """按请求覆盖读超时（连接/池超时保持客户端默认）"""
    return httpx.Timeout(connect=10.0, read=t, write=30.0, pool=10.0)


async def aclose_client() -> None:
    """应用关闭时释放连接池（FastAPI lifespan 调用）"""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


class GeminiProvider(BaseProvider):
    """Google Gemini Provider：使用官方 HTTP 接口"""

    name = "gemini"

    def __init__(self) -> None:
        self.model = _require_allowed(settings.GEMINI_MODEL)
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        self.stream_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?alt=sse"

    @property
    def primary_text_model(self) -> str | None:
        return self.model

    @property
    def max_output_tokens(self) -> int | None:
        return settings.GEMINI_MAX_OUTPUT_TOKENS

    @staticmethod
    def _to_contents(
        messages: list[dict], system: str | None = None
    ) -> tuple[list[dict], str | None]:
        """OpenAI 风格 messages → Gemini contents。
        role 映射：system→(合并进 user 或作为 system_instruction)；user/assistant 原样保留。
        返回 (contents, system_instruction)。"""
        contents: list[dict] = []
        sys_parts: list[str] = []
        if system:
            sys_parts.append(system)
        for m in messages:
            role = m.get("role")
            content = m.get("content") or ""
            if role == "system":
                sys_parts.append(content)
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
        system_instruction = "\n".join(sys_parts) if sys_parts else None
        return contents, system_instruction

    async def chat(
        self,
        messages: list[dict],
        timeout: float = settings.REQUEST_TIMEOUT,
        system: str | None = None,
    ) -> str:
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": settings.GEMINI_API_KEY,
        }
        contents, system_instruction = self._to_contents(messages, system)
        payload: dict = {"contents": contents}
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}
        client = _get_client()
        resp = await client.post(
            self.url, headers=headers, json=payload, timeout=_req_timeout(timeout)
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    async def chat_stream(
        self,
        messages: list[dict],
        timeout: float = 120.0,
        system: str | None = None,
    ) -> AsyncGenerator[str, None]:
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": settings.GEMINI_API_KEY,
        }
        contents, system_instruction = self._to_contents(messages, system)
        payload: dict = {"contents": contents}
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}
        client = _get_client()
        async with client.stream(
            "POST", self.stream_url, headers=headers, json=payload,
            timeout=_req_timeout(timeout),
        ) as resp:
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
        client = _get_client()
        resp = await client.post(
            self.url, headers=headers, json=payload, timeout=_req_timeout(timeout)
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
