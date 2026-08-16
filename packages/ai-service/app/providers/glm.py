import asyncio
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


def _post(loop, q, item) -> None:
    """生产者线程向事件循环投递元素；进程退出（loop 已关）时静默丢弃"""
    try:
        loop.call_soon_threadsafe(q.put_nowait, item)
    except RuntimeError:
        pass


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

    @property
    def primary_text_model(self) -> str | None:
        """主要文本模型（文本链的第一个）"""
        return self.text_models[0]

    @property
    def max_output_tokens(self) -> int | None:
        """主要文本模型的最大输出 token（受白名单模型上限约束）"""
        return _max_tokens_for(self.text_models[0], settings.GLM_MAX_TOKENS)

    # ---- 文本对话 ----

    async def chat(
        self,
        messages: list[dict],
        timeout: float = settings.REQUEST_TIMEOUT,
        system: str | None = None,
    ) -> str:
        last_err: Exception | None = None
        for model in self.text_models:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._chat_sync, model, messages, system),
                    timeout=timeout,
                )
            except Exception as exc:
                last_err = exc
        assert last_err is not None
        raise last_err

    def _chat_sync(
        self, model: str, messages: list[dict], system: str | None
    ) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        response = self.client.chat.completions.create(
            model=model,
            messages=msgs,
            max_tokens=_max_tokens_for(model, settings.GLM_MAX_TOKENS),
            temperature=settings.GLM_TEMPERATURE,
        )
        return response.choices[0].message.content

    async def chat_stream(
        self,
        messages: list[dict],
        timeout: float = 120.0,
        system: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式调用 GLM：生产者线程消费同步 SDK 迭代器，经 asyncio.Queue 桥接。

        - 每个流只占用 1 个生产者线程（token 经 call_soon_threadsafe 直投事件循环，
          不再占用 executor 线程逐个 q.get，避免高并发时线程池饥饿）
        - timeout 语义为「相邻 token 之间的空闲超时」：首包慢或中途断流都会触发，
          触发后按普通失败走模型/Provider 回退
        - 模型失败自动回退到下一个白名单模型（重新开始流式）
        """
        last_err: Exception | None = None
        for model in self.text_models:
            q: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_running_loop()
            sentinel = object()

            def _produce(_model: str = model) -> None:
                try:
                    msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
                    response = self.client.chat.completions.create(
                        model=_model,
                        messages=msgs,
                        max_tokens=_max_tokens_for(_model, settings.GLM_MAX_TOKENS),
                        temperature=settings.GLM_TEMPERATURE,
                        stream=True,
                    )
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            _post(loop, q, chunk.choices[0].delta.content)
                except Exception as exc:
                    _post(loop, q, exc)
                finally:
                    _post(loop, q, sentinel)

            threading.Thread(target=_produce, daemon=True).start()

            produced_any = False
            try:
                while True:
                    try:
                        item = await asyncio.wait_for(q.get(), timeout=timeout)
                    except asyncio.TimeoutError:
                        raise TimeoutError(
                            f"glm stream idle > {timeout:.0f}s (model={model})"
                        )
                    if item is sentinel:
                        break
                    if isinstance(item, Exception):
                        raise item
                    produced_any = True
                    yield item
                return  # 正常完成
            except Exception as exc:
                last_err = exc
                if produced_any:
                    # 已产出部分内容，回退会重复输出，直接抛出
                    raise exc
                # 尚未产出内容（请求阶段失败/首包超时），回退下一个模型
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
