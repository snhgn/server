from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseProvider(ABC):
    """AI Provider 抽象基类：所有 Provider 实现统一的 chat / chat_stream 接口"""

    name: str = "base"

    @abstractmethod
    async def chat(self, message: str, timeout: float) -> str:
        """发送单条用户消息，返回 AI 回答文本"""
        raise NotImplementedError

    @abstractmethod
    async def chat_stream(self, message: str, timeout: float) -> AsyncGenerator[str, None]:
        """流式发送消息，逐个 yield token"""
        raise NotImplementedError
        yield  # make it a generator  # noqa: E701

    async def chat_with_images(
        self, message: str, images: list[str], timeout: float
    ) -> str:
        """多模态：文本 + 图片（base64），返回完整回答。
        默认实现回退到纯文本（不支持视觉的 provider）。
        """
        return await self.chat(message, timeout)
