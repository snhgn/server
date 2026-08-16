from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseProvider(ABC):
    """AI Provider 抽象基类：所有 Provider 实现统一的 chat / chat_stream 接口"""

    name: str = "base"

    @property
    def primary_text_model(self) -> str | None:
        """主要文本模型名（用于查询上下文窗口）；None 时使用默认窗口。"""
        return None

    @property
    def max_output_tokens(self) -> int | None:
        """主要文本模型的最大输出 token（用于预算预留）；None 时使用配置默认值。"""
        return None

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        timeout: float,
        system: str | None = None,
    ) -> str:
        """发送完整 messages 数组（OpenAI 风格 role/content），返回 AI 回答文本。
        system 单独传入，由 Provider 内部按各自格式附加（Gemini 用 system_instruction）。
        """
        raise NotImplementedError

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        timeout: float,
        system: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式发送 messages 数组，逐个 yield token"""
        raise NotImplementedError
        yield  # make it a generator  # noqa: E701

    async def chat_with_images(
        self, message: str, images: list[str], timeout: float
    ) -> str:
        """多模态：文本 + 图片（base64），返回完整回答。
        默认实现回退到纯文本（不支持视觉的 provider）。
        """
        return await self.chat([{"role": "user", "content": message}], timeout)
