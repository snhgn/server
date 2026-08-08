import asyncio

from zai import ZhipuAiClient

from ..config import settings
from .base import BaseProvider


class GLMProvider(BaseProvider):
    """智谱 GLM Provider：使用智谱官方 SDK（zai-sdk）"""

    name = "glm"

    def __init__(self) -> None:
        self.client = ZhipuAiClient(api_key=settings.GLM_API_KEY)
        self.model = settings.GLM_MODEL

    async def chat(self, message: str, timeout: float = settings.REQUEST_TIMEOUT) -> str:
        def _call() -> str:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": message}],
                max_tokens=settings.GLM_MAX_TOKENS,
                temperature=settings.GLM_TEMPERATURE,
            )
            return response.choices[0].message.content

        # zai-sdk 为同步 SDK，放入线程池执行，避免阻塞事件循环；并用 wait_for 实现超时
        return await asyncio.wait_for(asyncio.to_thread(_call), timeout=timeout)
