"""ContextBuilder：按优先级组装 LLM 上下文，Token 预算内自动压缩。

组装顺序（优先级从高到低，超预算时从低到高丢弃/截断）：
  1. System Prompt（基础系统提示，永不移除）
  2. 用户长期 Memory
  3. Conversation Summary（滚动摘要，DB 已缓存）
  4. 文件 / 课表等当前消息相关上下文
  5. 最近消息（从最旧轮开始丢弃）
  6. RAG Context（最易被压缩）
  7. 当前用户消息（永不移除）

预算公式：budget = min(模型窗口, CONTEXT_MAX_TOKENS 硬上限) - 预留输出 - 安全余量。
"""
from dataclasses import dataclass

from ..config import settings
from .models import get_context_window
from .tokens import estimate_message_tokens, estimate_messages_tokens, estimate_tokens

# 预算计算异常时的兜底下限（避免配置错误导致预算为 0 或负数）
MIN_CONTEXT_BUDGET = 4096


@dataclass
class ContextUsage:
    """构建后的上下文 Token 统计（估算值，用于日志与调优）"""

    base_system: int = 0
    memory: int = 0
    summary: int = 0
    files: int = 0
    schedule: int = 0
    rag: int = 0
    system_total: int = 0
    history: int = 0
    user_msg: int = 0
    input_total: int = 0
    history_rounds_used: int = 0
    history_rounds_total: int = 0
    compressed: bool = False

    def as_log_dict(self) -> dict:
        """转为日志友好的 key=value 字典（不含任何消息内容）。"""
        return {
            "system": self.system_total,
            "memory": self.memory,
            "summary": self.summary,
            "files": self.files,
            "schedule": self.schedule,
            "rag": self.rag,
            "history": self.history,
            "user_msg": self.user_msg,
            "input_total": self.input_total,
            "rounds": f"{self.history_rounds_used}/{self.history_rounds_total}",
            "compressed": self.compressed,
        }


@dataclass
class BuiltContext:
    """ContextBuilder.build 的产出"""

    messages: list[dict]  # OpenAI 风格 messages（历史 + 当前用户消息）
    system: str | None    # 合并后的 system 指令
    usage: ContextUsage


def history_to_messages(history: list[dict]) -> list[dict]:
    """把保存的对话轮次展开为 OpenAI 风格 messages"""
    msgs: list[dict] = []
    for r in history:
        msgs.append({"role": "user", "content": r["message"]})
        msgs.append({"role": "assistant", "content": r["response"]})
    return msgs


# system 片段 key → usage 字段名
_PART_FIELD = {
    "base": "base_system",
    "memory": "memory",
    "summary": "summary",
    "files": "files",
    "schedule": "schedule",
    "rag": "rag",
}


class ContextBuilder:
    """纯函数式上下文组装器（不访问数据层，user_id 隔离由调用方保证）。"""

    def __init__(self, max_history_rounds: int = 15) -> None:
        self.max_history_rounds = max_history_rounds

    def build(
        self,
        *,
        provider_name: str,
        model: str | None,
        base_system: str | None,
        memory_ctx: str | None,
        summary_ctx: str | None,
        files_ctx: str | None,
        schedule_ctx: str | None,
        rag_ctx: str | None,
        history: list[dict],
        user_msg: str,
        output_reserve: int,
        max_input_budget: int = 0,
    ) -> BuiltContext:
        """组装上下文。

        provider_name/model：用于查询模型上下文窗口。
        output_reserve：预留输出 token（该 provider 主模型的 max_tokens 或配置值）。
        max_input_budget：CONTEXT_MAX_TOKENS 硬上限（0 = 不额外限制）。
        """
        window = get_context_window(provider_name, model)
        budget = window - output_reserve - settings.CONTEXT_SAFETY_MARGIN
        if max_input_budget and max_input_budget > 0:
            budget = min(budget, max_input_budget)
        budget = max(budget, MIN_CONTEXT_BUDGET)

        # ---- 1. system 片段：按优先级从高到低排列（尾部 = 最易丢弃）----
        parts: list[tuple[str, str]] = []
        if base_system:
            parts.append(("base", base_system))
        if memory_ctx:
            parts.append(("memory", memory_ctx))
        if summary_ctx:
            parts.append(("summary", summary_ctx))
        if files_ctx:
            parts.append(("files", files_ctx))
        if schedule_ctx:
            parts.append(("schedule", schedule_ctx))
        if rag_ctx:
            parts.append(("rag", rag_ctx))

        # ---- 2. messages：短期历史（限轮数）+ 当前用户消息（永不移除）----
        kept_history = history[: self.max_history_rounds]
        messages = history_to_messages(kept_history)
        messages.append({"role": "user", "content": user_msg})

        # ---- 3. Token 统计 ----
        part_tokens: dict[str, int] = {}
        for key, text in parts:
            part_tokens[key] = estimate_tokens(text)
        history_tokens = estimate_messages_tokens(messages[:-1])
        user_msg_tokens = estimate_message_tokens(messages[-1])

        total = sum(part_tokens.values()) + history_tokens + user_msg_tokens
        compressed = False
        # base 片段永不移除；其余片段（含仅有的 rag/memory 等）都可被压缩
        has_base = any(key == "base" for key, _text in parts)
        min_parts = 1 if has_base else 0

        # ---- 4. 超预算：按优先级从低到高压缩 ----
        # 4.1 丢弃 system 片段（base 永不移除）
        while total > budget and len(parts) > min_parts:
            key, _text = parts.pop()  # 尾部优先级最低
            total -= part_tokens.pop(key)
            compressed = True
        # 4.2 截断历史（从最旧轮开始丢；用户消息永不移除）
        while total > budget and kept_history:
            dropped = kept_history.pop(0)  # 最旧一轮（2 条消息）
            total -= (
                estimate_tokens(dropped.get("message") or "")
                + estimate_tokens(dropped.get("response") or "")
                + 2 * 4  # 结构开销
            )
            compressed = True
        # 4.3 仍超预算（罕见：单条消息/记忆本身过大）→ 丢弃除 base 外的 system 片段
        while total > budget and len(parts) > min_parts:
            key, _text = parts.pop()
            total -= part_tokens.pop(key)
            compressed = True

        # ---- 5. 重组输出（统计按最终保留的内容重算）----
        messages = history_to_messages(kept_history)
        messages.append({"role": "user", "content": user_msg})
        system = "\n\n".join(text for _key, text in parts) or None

        final_system_tokens = sum(part_tokens.values())
        final_history_tokens = estimate_messages_tokens(messages[:-1])
        usage = ContextUsage(
            base_system=part_tokens.get("base", 0),
            memory=part_tokens.get("memory", 0),
            summary=part_tokens.get("summary", 0),
            files=part_tokens.get("files", 0),
            schedule=part_tokens.get("schedule", 0),
            rag=part_tokens.get("rag", 0),
            system_total=final_system_tokens,
            history=final_history_tokens,
            user_msg=user_msg_tokens,
            input_total=final_system_tokens + final_history_tokens + user_msg_tokens,
            history_rounds_used=len(kept_history),
            history_rounds_total=len(history),
            compressed=compressed,
        )
        return BuiltContext(messages=messages, system=system, usage=usage)
