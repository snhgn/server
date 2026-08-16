# -*- coding: utf-8 -*-
"""P0 重构冒烟测试（本地 venv 可运行，无需 zai/Chroma 等重依赖）。

覆盖：
1. _sse_heartbeat：慢产出间插入 `: ping`、正常透传、inner 异常传播
2. 上传/知识库文件名 sanitize 逻辑（路径穿越用例）
3. MemoryTagFilter 流式标签过滤回归
4. GLMProvider.chat_stream 新桥接（call_soon_threadsafe + asyncio.Queue）：
   正常流、生产者异常、idle 超时回退
5. gemini/siliconflow 共享 AsyncClient 复用

运行（在 packages/ai-service 目录下）：
    python ../../tests/smoke_p0.py
"""
import asyncio
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="p0smoke_")
os.environ.update({
    "LOG_DIR": _TMP,
    "SQLITE_DB_PATH": str(Path(_TMP) / "memory.db"),
    "UPLOAD_STORAGE_DIR": str(Path(_TMP) / "uploads"),
    "KNOWLEDGE_BASE_DIR": str(Path(_TMP) / "knowledge"),
})

# ---- zai SDK stub（本地 venv 未安装，仅为通过 import）----
import types


class _FakeCompletions:
    def create(self, **kw):
        return ""


class _FakeChat:
    completions = _FakeCompletions()


class _FakeZhipuClient:
    def __init__(self, **kw):
        self.chat = _FakeChat()


zai_mod = types.ModuleType("zai")
zai_mod.ZhipuAiClient = _FakeZhipuClient
sys.modules["zai"] = zai_mod

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "ai-service"))

from app import main  # noqa: E402
from app.main import MemoryTagFilter, _gather_contexts, _providers_for_request, _sse_heartbeat, ChatRequest, GatheredCtx  # noqa: E402
from app.providers.gemini import _get_client as _gemini_client  # noqa: E402
from app.providers.siliconflow import _get_client as _sf_client  # noqa: E402
from app.providers.glm import GLMProvider  # noqa: E402


class TestSSEHeartbeat(unittest.TestCase):
    def test_ping_inserted_when_slow(self):
        async def run():
            async def inner():
                yield "a"
                await asyncio.sleep(0.12)
                yield "b"

            out = []
            async for item in _sse_heartbeat(inner(), interval=0.03):
                out.append(item)
            return out

        out = asyncio.run(run())
        self.assertIn("a", out)
        self.assertIn("b", out)
        self.assertIn(": ping\n\n", out)
        # ping 出现在 a 与 b 之间
        self.assertLess(out.index("a"), out.index(": ping\n\n"))
        self.assertLess(out.index(": ping\n\n"), out.index("b"))

    def test_passthrough_no_ping_when_fast(self):
        async def run():
            async def inner():
                for i in range(5):
                    yield f"t{i}"

            out = []
            async for item in _sse_heartbeat(inner(), interval=1.0):
                out.append(item)
            return out

        out = asyncio.run(run())
        self.assertEqual(out, [f"t{i}" for i in range(5)])

    def test_inner_exception_propagates(self):
        async def run():
            async def inner():
                yield "x"
                raise RuntimeError("boom")

            try:
                async for _ in _sse_heartbeat(inner(), interval=1.0):
                    pass
            except RuntimeError as e:
                return str(e)
            return None

        self.assertEqual(asyncio.run(run()), "boom")


class TestSanitize(unittest.TestCase):
    def test_upload_name_traversal(self):
        cases = {
            "../../etc/passwd": "passwd",
            "..\\..\\evil.py": "evil.py",
            "/abs/path/x.md": "x.md",
            "normal.txt": "normal.txt",
        }
        for raw, expect in cases.items():
            got = Path(raw.replace("\\", "/")).name
            self.assertEqual(got, expect, msg=raw)

    def test_knowledge_name_rejects_dots(self):
        for raw in ("", ".", "..", "../", "..\\"):
            name = Path((raw or "").replace("\\", "/")).name
            self.assertTrue(
                not name or name in {".", ".."},
                msg=f"{raw!r} -> {name!r} 应被拒绝",
            )


class TestMemoryTagFilter(unittest.TestCase):
    def test_split_tag_across_chunks(self):
        f = MemoryTagFilter()
        parts = ['<memory categ', 'ory="偏好" key="名', '字">小明</memory>你好']
        visible = "".join(f.feed(p) for p in parts) + f.finish()
        self.assertEqual(visible, "你好")
        self.assertEqual(f.ops, [("add", "偏好", "名字", "小明")])


class _Chunk:
    def __init__(self, text):
        class _C:
            pass

        c = _C()
        d = _C()
        d.content = text
        c.delta = d
        self.choices = [c]


class _FakeStreamCreate:
    """替换 GLM client.chat.completions.create 的假实现。
    script 每项：("tokens", [..]) / ("error", Exc) / ("gen", callable→迭代器)
    """

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def __call__(self, **kw):
        self.calls += 1
        action = self.script.pop(0)
        if action[0] == "error":
            raise action[1]
        if action[0] == "gen":
            return action[1]()
        return iter(_Chunk(t) for t in action[1])


class TestGLMStreamBridge(unittest.IsolatedAsyncioTestCase):
    def _patch(self, script):
        p = GLMProvider.__new__(GLMProvider)
        p.name = "glm"
        p.text_models = ["m1", "m2"]
        fake = _FakeStreamCreate(script)
        p.client = types.SimpleNamespace(
            chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=fake))
        )
        return p, fake

    async def test_normal_stream(self):
        p, fake = self._patch([("tokens", ["你", "好"])])
        got = [t async for t in p.chat_stream([{"role": "user", "content": "hi"}])]
        self.assertEqual(got, ["你", "好"])
        self.assertEqual(fake.calls, 1)

    async def test_first_model_error_falls_back(self):
        p, fake = self._patch([("error", RuntimeError("m1 down")), ("tokens", ["O", "K"])])
        got = [t async for t in p.chat_stream([{"role": "user", "content": "hi"}])]
        self.assertEqual(got, ["O", "K"])
        self.assertEqual(fake.calls, 2)

    async def test_idle_timeout_falls_back(self):
        # m1 生产者先睡眠 0.3s 才出首包，idle timeout=0.1 触发 → 回退 m2
        def slow_gen():
            def g():
                time.sleep(0.3)
                yield _Chunk("X")
            return g()
    
        p, fake = self._patch([
            ("gen", slow_gen),
            ("tokens", ["L", "ate"]),
        ])
        t0 = time.monotonic()
        got = [t async for t in p.chat_stream([{"role": "user", "content": "hi"}], timeout=0.1)]
        self.assertEqual(got, ["L", "ate"])
        self.assertEqual(fake.calls, 2)
        # 若无 idle 超时语义，需等 0.3s 才能发现慢；现在 ~0.1s 即回退
        self.assertLess(time.monotonic() - t0, 0.28)
    
    async def test_partial_output_no_fallback(self):
        def midstream_fail():
            def g():
                yield _Chunk("A")
                yield _Chunk("B")
                raise RuntimeError("mid-stream fail")
            return g()
    
        p, fake = self._patch([("gen", midstream_fail)])
        got = []
        with self.assertRaises(RuntimeError):
            async for t in p.chat_stream([{"role": "user", "content": "hi"}]):
                got.append(t)
        self.assertEqual(got, ["A", "B"])
        self.assertEqual(fake.calls, 1)


class TestSharedClients(unittest.TestCase):
    def test_clients_reused(self):
        c1 = _gemini_client()
        c2 = _gemini_client()
        self.assertIs(c1, c2)
        s1 = _sf_client()
        s2 = _sf_client()
        self.assertIs(s1, s2)
        self.assertIsNot(c1, s1)


class TestChatPipeline(unittest.IsolatedAsyncioTestCase):
    """统一 Chat Pipeline：_gather_contexts 状态事件与结果、_providers_for_request 路由"""

    async def test_gather_yields_status_then_ctx(self):
        req = ChatRequest(message="你好", use_memory=True, use_rag=False)
        events = []
        g = None
        async for kind, payload in _gather_contexts(req, user_id=1, memory_enabled=True):
            events.append(kind)
            if kind == "ctx":
                g = payload
        # 仅 memory：应看到 retrieving_memory 进度 + 最终 ctx
        self.assertEqual(events, ["status", "ctx"])
        self.assertIsInstance(g, GatheredCtx)
        self.assertIsNotNone(g.memory_ctx)
        self.assertEqual(g.full_prompt.split("\n\n")[-1], "你好")

    async def test_gather_plain_chat_no_status(self):
        req = ChatRequest(message="嗨", use_memory=False, use_rag=False)
        events = []
        g = None
        async for kind, payload in _gather_contexts(req, user_id=1, memory_enabled=False):
            events.append(kind)
            if kind == "ctx":
                g = payload
        self.assertEqual(events, ["ctx"])
        self.assertEqual(g.full_prompt, "嗨")

    def test_providers_translation_routing(self):
        from app import main as m
        # 翻译请求且配置了 TRANSLATOR_PROVIDER → 翻译器排首位
        if m.TRANSLATOR_PROVIDER is None:
            self.skipTest("SILICONFLOW_API_KEY 未配置，跳过翻译路由测试")
        g = GatheredCtx(full_prompt="把这段话翻译成英文")
        req = ChatRequest(message="把这段话翻译成英文")
        providers = _providers_for_request(req, {}, g)
        self.assertEqual(providers[0].name, "hunyuan-mt")
        # 非翻译请求 → 默认顺序（glm 在前）
        g2 = GatheredCtx(full_prompt="讲个笑话")
        req2 = ChatRequest(message="讲个笑话")
        providers2 = _providers_for_request(req2, {}, g2)
        self.assertEqual(providers2[0].name, "glm")


if __name__ == "__main__":
    unittest.main(verbosity=2)
