"""轻量 Token 估算（无外部依赖）。

用于 Context Budget 控制。注意：这是估算值，不是模型的精确分词结果；
预算计算时额外保留 CONTEXT_SAFETY_MARGIN 安全余量，抵消估算误差。

规则（保守启发式）：
- CJK 字符（中日韩统一表意文字 + 假名 + 谚文）按 1 字 ≈ 1 token
  （主流 BPE 分词器对常用汉字通常为 1~1.5 token）
- 其余字符按 4 字符 ≈ 1 token
- 每条消息额外 +4 token 结构开销（role 标记、分隔符等）
"""
import re

# CJK 区块：标点/假名/汉字扩展A/基本汉字/兼容汉字/谚文
_CJK_RE = re.compile(
    r"[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]"
)

# 每条消息的固定结构开销（role / 分隔符等）
MESSAGE_OVERHEAD_TOKENS = 4


def estimate_tokens(text: str | None) -> int:
    """估算一段文本的 token 数。空文本返回 0。"""
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    other = len(text) - cjk
    return cjk + max(1, other // 4) + 1


def estimate_message_tokens(msg: dict) -> int:
    """估算单条 OpenAI 风格消息（{"role","content"}）的 token 数。"""
    content = msg.get("content") or ""
    return estimate_tokens(str(content)) + MESSAGE_OVERHEAD_TOKENS


def estimate_messages_tokens(msgs: list[dict]) -> int:
    """估算消息数组的总 token 数。"""
    return sum(estimate_message_tokens(m) for m in msgs)
