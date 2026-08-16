# -*- coding: utf-8 -*-
"""Context Engine 单元测试（无外部重依赖，仅需 pydantic_settings）。

运行方式（在 packages/ai-service 目录下）：
    python -m unittest discover -s tests -v
"""
import os
import unittest

# 必须在导入 app 模块前设置环境变量（config.Settings 在导入时读取）
os.environ.setdefault("CONTEXT_SAFETY_MARGIN", "50")
os.environ.setdefault("CONTEXT_DEFAULT_WINDOW", "128000")
os.environ.setdefault("MODEL_CONTEXT_WINDOW_OVERRIDES", '{"test-model": 2000}')

from app.context.builder import ContextBuilder, history_to_messages  # noqa: E402
from app.context.tokens import estimate_message_tokens, estimate_messages_tokens, estimate_tokens  # noqa: E402


class TestTokenEstimator(unittest.TestCase):
    def test_cjk_and_ascii(self):
        # 中文按 1 字 ≈ 1 token
        self.assertGreaterEqual(estimate_tokens("你好世界"), 4)
        # 英文按 4 字符 ≈ 1 token
        self.assertLess(estimate_tokens("a" * 40), estimate_tokens("你" * 40))
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens(None), 0)

    def test_messages(self):
        msgs = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "hello world"},
        ]
        total = estimate_messages_tokens(msgs)
        self.assertEqual(total, estimate_message_tokens(msgs[0]) + estimate_message_tokens(msgs[1]))
        self.assertGreater(total, 0)


class TestContextBuilder(unittest.TestCase):
    """使用 MODEL_CONTEXT_WINDOW_OVERRIDES 里 2000 token 的小窗口测试压缩逻辑"""

    def _build(self, **kwargs):
        defaults = dict(
            provider_name="glm",
            model="test-model",
            base_system="你是助手。",
            memory_ctx="记忆：用户叫小明。",
            summary_ctx="摘要：之前讨论了项目A。",
            files_ctx="文件：README 内容……",
            schedule_ctx=None,
            rag_ctx="知识库：关于 STM32 的资料。",
            history=[
                {"message": f"问题{i}", "response": f"回答{i}"} for i in range(10)
            ],
            user_msg="当前问题",
            output_reserve=500,
            max_input_budget=0,
        )
        defaults.update(kwargs)
        return ContextBuilder(max_history_rounds=15).build(**defaults)

    def test_priority_order_and_required_parts(self):
        built = self._build()
        # 用户消息永不移除
        self.assertEqual(built.messages[-1], {"role": "user", "content": "当前问题"})
        # base system 永不移除
        self.assertIn("你是助手。", built.system)
        # 系统片段按优先级排列：base 在前，rag 在后
        self.assertLess(built.system.index("你是助手。"), built.system.index("知识库"))
        self.assertLess(built.system.index("记忆"), built.system.index("知识库"))
        # 预算充足时全部保留
        self.assertEqual(built.usage.history_rounds_used, 10)
        self.assertFalse(built.usage.compressed)
        self.assertGreater(built.usage.input_total, 0)

    def test_compress_drops_rag_first_then_history(self):
        # 大历史强制超预算：RAG 先被丢弃，历史从最旧开始截断
        history = [
            {"message": "问题" * 100, "response": "回答" * 100} for _ in range(15)
        ]
        built = self._build(history=history, user_msg="当前问题")
        self.assertTrue(built.usage.compressed)
        self.assertEqual(built.usage.rag, 0, "RAG 应最先被丢弃")
        self.assertIn("你是助手。", built.system)
        self.assertLess(built.usage.history_rounds_used, 15)
        # 丢弃的是最旧的历史：剩余历史应以“问题”开头（与原始一致，检查轮数变少即可）
        self.assertEqual(built.messages[-1], {"role": "user", "content": "当前问题"})

    def test_everything_compressed_keeps_base_and_user(self):
        # 极端：历史 + 所有片段都超预算 → 只保留 base + 用户消息
        history = [
            {"message": "问题" * 500, "response": "回答" * 500} for _ in range(15)
        ]
        built = self._build(history=history)
        self.assertTrue(built.usage.compressed)
        self.assertEqual(built.usage.memory, 0)
        self.assertEqual(built.usage.summary, 0)
        self.assertEqual(built.usage.rag, 0)
        self.assertIn("你是助手。", built.system)
        self.assertEqual(built.messages[-1]["role"], "user")

    def test_history_rounds_cap(self):
        history = [{"message": f"q{i}", "response": f"a{i}"} for i in range(100)]
        built = self._build(history=history, output_reserve=0, base_system=None)
        self.assertLessEqual(built.usage.history_rounds_used, 15)
        self.assertEqual(len(built.messages), built.usage.history_rounds_used * 2 + 1)

    def test_no_base_system_all_parts_droppable(self):
        # 未配置基础 System Prompt（默认情况）时，所有片段都可被压缩，
        # 只有用户消息永不移除
        history = [
            {"message": "问题" * 500, "response": "回答" * 500} for _ in range(10)
        ]
        built = self._build(history=history, base_system=None)
        self.assertTrue(built.usage.compressed)
        self.assertEqual(built.usage.memory, 0)
        self.assertEqual(built.usage.summary, 0)
        self.assertEqual(built.usage.rag, 0)
        self.assertIsNone(built.system)
        self.assertEqual(built.messages[-1], {"role": "user", "content": "当前问题"})

    def test_history_to_messages(self):
        msgs = history_to_messages([{"message": "m", "response": "r"}])
        self.assertEqual(
            msgs,
            [{"role": "user", "content": "m"}, {"role": "assistant", "content": "r"}],
        )


if __name__ == "__main__":
    unittest.main()
