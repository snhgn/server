from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """AI Provider 抽象基类：所有 Provider 实现统一的 chat 接口"""

    name: str = "base"

    @abstractmethod
    async def chat(self, message: str, timeout: float) -> str:
        """发送单条用户消息，返回 AI 回答文本

        Args:
            message: 用户消息
            timeout: 请求超时时间（秒）

        Returns:
            AI 回答文本

        Raises:
            Exception: 调用失败（网络错误 / API 错误 / 超时 / 服务异常）
        """
        raise NotImplementedError
