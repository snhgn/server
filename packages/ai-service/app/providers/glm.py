import asyncio
import queue
import threading
from typing import AsyncGenerator

from zai import ZhipuAiClient

from ..config import settings
from .base import BaseProvider

# 允许调用的模型白名单（禁止调用白名单之外的其他模型）
ALLOWED_MODELS = {
    "glm-4.7-flash", "glm-4-flash-250414",
    "glm-4.6v-flash", "glm-4.1v-thinking-flash", "glm-4v-flash",
    "cogview-3-flash",
}

# 各白名单模型的 max_tokens 上限（智谱官方限制），调用时取 min(配置值, 模型上限)
MAX_TOKENS_BY_MODEL = {
    "glm-4.7-flash": 65536,
    "glm-4-flash-250414": 16384,
    "glm-4.6v-flash": 32768,
    "glm-4.1v-thinking-flash": 32768,
    "glm-4v-flash": 2048,
    "cogview-3-flash": None,  # 图片生成不适用
}


def _max_tokens_for(model: str, configured: int) -> int:
    cap = MAX_TOKENS_BY_MODEL.get(model)
    if cap is None:
        return configured
    return min(configured, cap)


def _require_allowed(model: str, purpose: str) -> str:
    if model not in ALLOWED_MODELS:
        raise ValueError(
            f"Model '{model}' is not in the allowlist for {purpose}. "
            f"Allowed: {sorted(ALLOWED_MODELS)}"
        )
    return model


class GLMProvider(BaseProvider):
    """智谱 GLM Provider：使用智谱官方 SDK（zai-sdk），内置模型 fallback 链"""

    name = "glm"

    def __init__(self) -> None:
        # max_retries=1：429 限速时快速失败（重试 1 次约 0.9s），
        # 尽快回退到备用模型，避免 SDK 指数退避重试导致长时间无响应
        self.client = ZhipuAiClient(api_key=settings.GLM_API_KEY, max_retries=1)
        # 文本链：最新优先，失败自动回退
        self.text_models = [
            _require_allowed(settings.GLM_TEXT_MODEL, "text"),
            _require_allowed(settings.GLM_TEXT_FALLBACK_MODEL, "text fallback"),
        ]
        # 视觉链：最新优先
        self.vision_models = [
            _require_allowed(settings.GLM_VISION_MODEL, "vision"),
            _require_allowed(settings.GLM_VISION_THINK_MODEL, "vision think"),
            _require_allowed(settings.GLM_VISION_FALLBACK_MODEL, "vision fallback"),
        ]
        self.image_model = _require_allowed(settings.GLM_IMAGE_MODEL, "image")

    # ---- 文本对话 ----

    async def chat(self, message: str, timeout: float = settings.REQUEST_TIMEOUT) -> str:
        last_err: Exception | None = None
        for model in self.text_models:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._chat_sync, model, message), timeout=timeout
                )
            except Exception as exc:
                last_err = exc
        assert last_err is not None
        raise last_err

    def _chat_sync(self, model: str, message: str) -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": message}],
            max_tokens=_max_tokens_for(model, settings.GLM_MAX_TOKENS),
            temperature=settings.GLM_TEMPERATURE,
        )
        return response.choices[0].message.content

    async def chat_stream(
        self, message: str, timeout: float = 120.0
    ) -> AsyncGenerator[str, None]:
        """流式调用 GLM：线程消费同步迭代器，queue 桥接 async。
        模型失败自动回退到下一个白名单模型（重新开始流式）。
        """
        last_err: Exception | None = None
        for model in self.text_models:
            q: queue.Queue = queue.Queue()
            sentinel = object()

            def _produce(_model: str = model) -> None:
                try:
                    response = self.client.chat.completions.create(
                        model=_model,
                        messages=[{"role": "user", "content": message}],
                        max_tokens=_max_tokens_for(_model, settings.GLM_MAX_TOKENS),
                        temperature=settings.GLM_TEMPERATURE,
                        stream=True,
                    )
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            q.put(chunk.choices[0].delta.content)
                except Exception as exc:
                    q.put(exc)
                finally:
                    q.put(sentinel)

            thread = threading.Thread(target=_produce, daemon=True)
            thread.start()

            loop = asyncio.get_event_loop()
            try:
                async def _iter():
                    while True:
                        item = await loop.run_in_executor(None, q.get)
                        if item is sentinel:
                            break
                        if isinstance(item, Exception):
                            raise item
                        yield item
                # 消费生成器；中途失败则换下一个模型重试
                produced_any = False
                async for token in _iter():
                    produced_any = True
                    yield token
                return  # 正常完成
            except Exception as exc:
                last_err = exc
                if produced_any:
                    # 已产出部分内容，回退会重复输出，直接抛出
                    raise exc
                # 尚未产出内容（请求阶段失败），回退下一个模型
                continue

        if last_err is not None:
            raise last_err

    # ---- 多模态（图片理解）----

    async def chat_with_images(
        self, message: str, images: list[str], timeout: float = 60.0
    ) -> str:
        """多模态：文本 + 图片 base64 列表，视觉模型失败自动回退"""
        last_err: Exception | None = None
        for model in self.vision_models:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._vision_sync, model, message, images),
                    timeout=timeout,
                )
            except Exception as exc:
                last_err = exc
        assert last_err is not None
        raise last_err

    def _vision_sync(self, model: str, message: str, images: list[str]) -> str:
        content: list[dict] = [{"type": "text", "text": message}]
        for img_b64 in images:
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            )
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=_max_tokens_for(model, settings.GLM_VISION_MAX_TOKENS),
            temperature=settings.GLM_TEMPERATURE,
        )
        return response.choices[0].message.content

    # ---- 图片生成（CogView）----

    async def generate_image(
        self, prompt: str, size: str | None = None, timeout: float = 120.0
    ) -> dict:
        """根据文本提示生成图片（cogview-3-flash）。
        返回 { url: str|None, b64_json: str|None, revised_prompt: str|None }
        """
        def _call() -> dict:
            resp = self.client.images.generations(
                model=self.image_model,
                prompt=prompt,
                size=size or settings.GLM_IMAGE_SIZE,
            )
            # ImagesResponded: data[0].{url, b64_json, revised_prompt}
            if not resp or not getattr(resp, "data", None):
                raise RuntimeError("cogview returned no image data")
            img = resp.data[0]
            return {
                "url": getattr(img, "url", None),
                "b64_json": getattr(img, "b64_json", None),
                "revised_prompt": getattr(img, "revised_prompt", None),
            }

        return await asyncio.wait_for(asyncio.to_thread(_call), timeout=timeout)
