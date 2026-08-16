"""AI Service - 多用户隔离版"""
import asyncio
import base64
import json
import logging
import logging.handlers
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import settings
from .context.builder import BuiltContext, ContextBuilder
from .context.tokens import estimate_tokens
from .course_tools import build_schedule_prompt
from .memory.manager import (
    CODE_EXTS,
    IMAGE_EXTS,
    TEXT_EXTS,
    FileManager,
    classify_file_type,
    ConversationStore,
    MemoryManager,
    UserSettingsManager,
)
from .providers.base import BaseProvider
from .providers.gemini import GeminiProvider, aclose_client as _gemini_aclose
from .providers.glm import GLMProvider
from .providers.siliconflow import SiliconFlowProvider, aclose_client as _sf_aclose

_LOG_DIR = Path(os.getenv("LOG_DIR", "/app/logs"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            _LOG_DIR / "ai-service.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger("ai-service")

# 让 uvicorn 访问日志也写入文件，统一格式
_uv_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
for uv_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uv_logger = logging.getLogger(uv_name)
    uv_logger.propagate = False
    for h in [
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            _LOG_DIR / "ai-service.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
        ),
    ]:
        h.setFormatter(_uv_fmt)
        uv_logger.addHandler(h)

@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    # 应用关闭时释放 Provider 共享 HTTP 连接池
    await _gemini_aclose()
    await _sf_aclose()


app = FastAPI(title="AI Service Layer", version="3.1.0", lifespan=_lifespan)

# Provider 注册：GLM 主调用，Gemini 备用（默认关闭）
PROVIDERS = [GLMProvider()]
if settings.GEMINI_ENABLED:
    PROVIDERS.append(GeminiProvider())

PROVIDER_BY_NAME = {p.name: p for p in PROVIDERS}


def _build_providers_to_try(pref: str | None) -> list:
    """构造 provider 尝试顺序：
    - pref 指定时（请求参数优先，其次用户设置），该 provider 排在首位；
    - 其余 provider 按注册顺序跟在后面；
    - 任一 provider 失败时调用方按此顺序自动切换到下一个。
    """
    if pref in PROVIDER_BY_NAME:
        return [PROVIDER_BY_NAME[pref]] + [
            p for p in PROVIDERS if p.name != pref
        ]
    return list(PROVIDERS)

# 硅基流动专用 Provider（配置了 key 才启用）
# - 翻译：腾讯混元 MT
# - 总结：通义千问
if settings.SILICONFLOW_API_KEY:
    TRANSLATOR_PROVIDER = SiliconFlowProvider(
        name="hunyuan-mt", model=settings.HUNYUAN_TRANSLATE_MODEL
    )
    SUMMARIZER_PROVIDER = SiliconFlowProvider(
        name="qwen", model=settings.QWEN_SUMMARY_MODEL
    )
else:
    TRANSLATOR_PROVIDER = None
    SUMMARIZER_PROVIDER = None

# 翻译请求检测：命中则优先路由到混元 MT 模型
_TRANSLATE_RE = re.compile(
    r"(把.{0,40}(翻译|译成)|翻译成|翻译一下|译一下|怎么翻译|如何翻译|"
    r"translate\b|translation\b|interpret\b)",
    re.IGNORECASE,
)


def _is_translation_request(text: str) -> bool:
    return bool(_TRANSLATE_RE.search(text))


# ---- 自动判断：是否需要携带 Memory / RAG（客户端 flag 仍优先生效）----
# 命中关键词时，即使客户端未开启 use_memory / use_rag 也自动注入，
# 避免闲聊（如“你好”）也做无意义的检索；可通过 settings 开关关闭。
_MEMORY_NEED_RE = re.compile(
    r"(记住|记得|上次|之前说过|我说过|我告诉过你|我叫|我喜欢|我不喜欢|我讨厌|"
    r"偏好|习惯|别忘|别忘了|我是谁|我的名字|我的生日|我的地址|我的电话|我的邮箱|用户名)"
)
_RAG_NEED_RE = re.compile(
    r"(知识库|知识点|资料库|我的文档|上传的文档|上传的文件|我的文件|项目文档|"
    r"查阅文档|查看文档|查下资料|查资料|搜资料|从库里|库里面|知识库里|"
    r"教材内容|课件内容|论文内容|说明书内容|手册内容|代码库内容|课程设计文档|报告内容)"
)


def _needs_memory(message: str) -> bool:
    return bool(_MEMORY_NEED_RE.search(message or ""))


def _needs_rag(message: str) -> bool:
    return bool(_RAG_NEED_RE.search(message or ""))


# ---- 上下文管理（连续对话）----
# 短期上下文窗口、滚动压缩参数统一走 settings（config.py 的 Context Engine 段）

# 滚动摘要 prompt：把「已有滚动摘要 + 最旧若干轮对话」压缩成新的摘要
_ROLLING_SUMMARY_PROMPT = """你是一个对话摘要助手。请把下面提供的「已有摘要」与「新增对话片段」合并，
生成一份**连续的对话摘要**，保留所有重要事实、用户偏好、约定、进行中的任务和结论。
要求：
- 使用简洁的要点式中文，按主题组织
- 不要重复描述已有摘要已涵盖的细节，但必须保留其核心信息
- 新信息完整并入，不遗漏关键决策与用户明确表达过的偏好
- 直接输出摘要正文，不要任何解释、代码块或标记

--- 已有摘要 ---
{existing}

--- 新增对话片段 ---
{new_chunk}
"""


def _build_rolling_summary_prompt(existing: str, chunk: str) -> str:
    return _ROLLING_SUMMARY_PROMPT.format(
        existing=existing or "（无）", new_chunk=chunk[:12000]
    )


async def _rolling_compress(
    user_id: int, session_id: str, old_rounds: list[dict]
) -> str | None:
    """把最旧的 old_rounds 轮对话压缩进滚动摘要（旧的直接丢弃）。
    返回新的滚动摘要文本；失败返回 None（不影响主对话）。"""
    meta = await asyncio.to_thread(conversation_store.get_meta, user_id, session_id)
    existing = (meta or {}).get("rolling_summary") or ""
    chunk_parts = []
    for r in old_rounds:
        chunk_parts.append(f"用户：{r['message']}\nAI：{r['response']}")
    prompt = _build_rolling_summary_prompt(existing, "\n\n".join(chunk_parts))

    try:
        providers_to_try = ([SUMMARIZER_PROVIDER] if SUMMARIZER_PROVIDER else []) + PROVIDERS
        for provider in providers_to_try:
            try:
                raw = await provider.chat(
                    [{"role": "user", "content": prompt}], timeout=60
                )
                new_summary = (raw or "").strip()
                if new_summary:
                    await asyncio.to_thread(
                        conversation_store.upsert_meta,
                        user_id,
                        session_id,
                        rolling_summary=new_summary,
                    )
                    logger.info(
                        "rolling summary updated user=%s session=%s len=%d",
                        user_id, session_id, len(new_summary),
                    )
                    return new_summary
            except Exception as exc:
                logger.warning(
                    "rolling compress provider=%s failed: %s",
                    provider.name, str(exc)[:120],
                )
    except Exception as exc:
        logger.warning("rolling compress failed: %s", str(exc)[:150])
    return None


async def _build_context(
    *,
    user_id: int,
    session_id: str,
    user_msg: str,
    memory_ctx: str | None,
    rag_ctx: str | None,
    files_ctx: str | None,
    schedule_ctx: str | None,
    provider: BaseProvider,
) -> BuiltContext:
    """Context Engine：组装发给 LLM 的完整上下文（Token 预算内按优先级压缩）。

    system：基础System + Memory + 滚动摘要 + 文件 + 课表 + RAG（优先级从高到低）
    messages：最近 N 轮历史 + 当前用户消息（永不移除）
    超窗（轮数或 Token 阈值）时异步触发滚动压缩，不阻塞本轮响应。
    """
    history = await asyncio.to_thread(
        conversation_store.get_history,
        user_id,
        session_id,
        settings.CONTEXT_MAX_HISTORY_ROUNDS,
    )
    meta = await asyncio.to_thread(conversation_store.get_meta, user_id, session_id)
    rolling = (meta or {}).get("rolling_summary") or ""
    summary_ctx = (
        f"以下是本会话更早的对话摘要（来自滚动压缩）：\n{rolling}" if rolling else None
    )

    reserve = (
        settings.CONTEXT_OUTPUT_RESERVE_TOKENS
        or provider.max_output_tokens
        or settings.CONTEXT_DEFAULT_WINDOW // 4
    )
    builder = ContextBuilder(max_history_rounds=settings.CONTEXT_MAX_HISTORY_ROUNDS)
    built = builder.build(
        provider_name=provider.name,
        model=provider.primary_text_model,
        base_system=settings.AI_SYSTEM_PROMPT or None,
        memory_ctx=memory_ctx,
        summary_ctx=summary_ctx,
        files_ctx=files_ctx,
        schedule_ctx=schedule_ctx,
        rag_ctx=rag_ctx,
        history=history,
        user_msg=user_msg,
        output_reserve=reserve,
        max_input_budget=settings.CONTEXT_MAX_TOKENS,
    )

    # 超窗：把最旧 N 轮折叠进滚动摘要（异步，不阻塞主对话）
    total_rounds = len(history) + 1  # +1 为当前轮
    if (
        len(history) >= settings.CONTEXT_ROLLING_COMPRESS_ROUNDS
        and (
            total_rounds > settings.CONTEXT_MAX_HISTORY_ROUNDS
            or built.usage.history > settings.CONTEXT_SUMMARY_TRIGGER_TOKENS
        )
    ):
        old_rounds = history[: settings.CONTEXT_ROLLING_COMPRESS_ROUNDS]
        try:
            asyncio.create_task(_rolling_compress(user_id, session_id, old_rounds))
        except Exception as exc:
            logger.warning("schedule rolling compress failed: %s", exc)

    return built


def _log_chat_usage(
    event: str,
    provider: str | None,
    username: str,
    session_id: str,
    elapsed: float,
    images: int,
    built: BuiltContext | None,
    answer: str | None,
) -> None:
    """上下文用量日志（§十三）：记录 token 分项与耗时。
    绝不记录消息内容、API Key、密码等敏感信息。"""
    usage = built.usage if built else None
    parts = [
        event, f"provider={provider}", f"user={username}", f"session={session_id}",
        f"cost={elapsed:.2f}s", f"images={images}",
    ]
    if usage:
        parts.append(
            "input_tokens=%d system=%d memory=%d summary=%d rag=%d files=%d schedule=%d "
            "history=%d user_msg=%d rounds=%d/%d compressed=%s" % (
                usage.input_total, usage.system_total, usage.memory, usage.summary,
                usage.rag, usage.files, usage.schedule, usage.history, usage.user_msg,
                usage.history_rounds_used, usage.history_rounds_total, usage.compressed,
            )
        )
    if answer is not None:
        parts.append(f"output_est={estimate_tokens(answer)}")
    logger.info(" ".join(parts))


# ---- AI 主动写记忆（长期记忆写回）----
# AI 在回答中嵌入隐藏标签即可修改当前用户的长期记忆：
#   写入：<memory category="偏好" key="编程语言">Python</memory>
#   删除：<memory_delete category="偏好" key="编程语言"/>
# 标签会被 ai-service 解析并从用户可见文本中移除，不展示给用户。

_MEMORY_WRITE_NOTE = (
    "你可以根据对话主动长期记忆用户信息（仅当内容值得长期记住时，如偏好、名字、重要事实、"
    "需要持续遵守的规则），不要记忆一次性话题内容。"
    "在回答中直接嵌入以下隐藏标签（不会显示给用户，也不会出现在你的可见回答中）：\n"
    "写入记忆：<memory category=\"分类\" key=\"键\">值</memory>\n"
    "删除记忆：<memory_delete category=\"分类\" key=\"键\"/>\n"
    "分类建议用：偏好 / 个人信息 / 项目 / 知识 / 规则。"
)

# 匹配 <memory ...> / <memory_delete ...> 开标签（属性任意顺序，兼容 /> 或显式闭合）
_MEMORY_OPEN_RE = re.compile(r'<(?P<tag>memory_delete|memory)\b(?P<attrs>[^>]*)>')
_ATTR_RE = re.compile(r'([\w-]+)\s*=\s*"([^"]*)"')
_CLOSE_MEM_RE = re.compile(r'</memory\s*>')
_CLOSE_MEMDEL_RE = re.compile(r'</memory_delete\s*>')


def _extract_memory_ops(text: str) -> tuple[str, list[tuple[str, str, str, str]]]:
    """从完整文本中提取记忆操作，返回 (去除标签后的干净文本, ops)。
    ops 元素：(action, category, key, value)，action 为 'add' 或 'delete'。
    未闭合的标签不解析（保持原样，由调用方保留尾部）。"""
    ops: list[tuple[str, str, str, str]] = []
    clean_parts: list[str] = []
    pos = 0
    i = 0
    n = len(text)
    while i < n:
        m = _MEMORY_OPEN_RE.search(text, i)
        if not m:
            break
        tag = m.group("tag")
        attrs_raw = m.group("attrs").strip()
        self_close = attrs_raw.endswith("/")
        if self_close:
            attrs_raw = attrs_raw[:-1].rstrip()
        attrs = {k: v for k, v in _ATTR_RE.findall(attrs_raw)}
        cat = attrs.get("category", "")
        key = attrs.get("key", "")
        if not (cat and key):
            # 属性不完整，视为普通文本
            i = m.end()
            continue
        if tag == "memory_delete":
            if self_close:
                clean_parts.append(text[pos:m.start()])
                ops.append(("delete", cat, key, ""))
                pos = m.end()
                i = m.end()
            else:
                close = _CLOSE_MEMDEL_RE.search(text, m.end())
                if not close:
                    break  # 未闭合，保留尾部
                clean_parts.append(text[pos:m.start()])
                ops.append(("delete", cat, key, ""))
                pos = close.end()
                i = close.end()
        else:  # memory 写入
            if self_close:
                # 自闭合无内容，忽略该标签
                clean_parts.append(text[pos:m.start()])
                pos = m.end()
                i = m.end()
                continue
            close = _CLOSE_MEM_RE.search(text, m.end())
            if not close:
                break  # 未闭合，保留尾部
            val = text[m.end():close.start()].strip()
            clean_parts.append(text[pos:m.start()])
            ops.append(("add", cat, key, val))
            pos = close.end()
            i = close.end()
    clean_parts.append(text[pos:])
    return "".join(clean_parts), ops


class MemoryTagFilter:
    """流式过滤记忆标签：逐 chunk 喂入，返回用户可见文本；完整标签跨 chunk 也能正确提取。"""

    def __init__(self) -> None:
        self._buf = ""
        self.ops: list[tuple[str, str, str, str]] = []

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        clean, ops = _extract_memory_ops(self._buf)
        self.ops.extend(ops)
        keep = 0
        # 1) 存在未闭合的完整开标签（如 "<memory category=\"偏好\" key=\"名字\">"），保留尾部
        m = _MEMORY_OPEN_RE.search(clean)
        if m:
            keep = len(clean) - m.start()
        else:
            # 2) 末尾存在未结束的标签前缀（如 "<memory categ" 或 "</mem"），保守保留
            pm = re.search(r'</?[A-Za-z][^>]*$', clean)
            if pm:
                keep = len(clean) - pm.start()
        if keep:
            out, self._buf = clean[:-keep], clean[-keep:]
        else:
            out, self._buf = clean, ""
        return out

    def finish(self) -> str:
        """清空缓冲区（最后一次），返回残余可见文本；丢弃未闭合的标签，避免泄漏原始标签"""
        clean, ops = _extract_memory_ops(self._buf)
        self.ops.extend(ops)
        self._buf = ""
        m = _MEMORY_OPEN_RE.search(clean)
        if m:
            clean = clean[: m.start()]
        else:
            pm = re.search(r'</?[A-Za-z][^>]*$', clean)
            if pm:
                clean = clean[: pm.start()]
        return clean


async def _apply_memory_ops(user_id: int, ops: list[tuple[str, str, str, str]]) -> None:
    """执行记忆写回（add/delete），绑定当前用户；任何失败都不影响主响应。"""
    for action, category, key, value in ops:
        try:
            if action == "add":
                await asyncio.to_thread(memory_manager.add, user_id, category, key, value)
                logger.info("AI memory add: user=%d [%s] %s", user_id, category, key)
            elif action == "delete":
                await asyncio.to_thread(memory_manager.delete, user_id, category, key)
                logger.info("AI memory delete: user=%d [%s] %s", user_id, category, key)
        except Exception as exc:
            logger.warning("AI memory op failed: %s", str(exc)[:150])


# ---- 后台总结任务并发控制 ----
# 限制同时运行的总结任务数（asyncio.Semaphore 公平排队）：
# 防止高并发对话下 create_task 无限堆积，拖慢事件循环；
# 超出的总结任务排队等待，不占用主对话资源。
SUMMARIZE_MAX_CONCURRENCY = 4
_summarize_sem: asyncio.Semaphore | None = None


def _get_summarize_sem() -> asyncio.Semaphore:
    """惰性创建信号量：绑定到运行中的事件循环，避免模块导入期无 loop 问题"""
    global _summarize_sem
    if _summarize_sem is None:
        _summarize_sem = asyncio.Semaphore(SUMMARIZE_MAX_CONCURRENCY)
    return _summarize_sem

# 存储管理器（SQLite，启动时初始化）
memory_manager = MemoryManager()
conversation_store = ConversationStore()
user_settings = UserSettingsManager()
file_manager = FileManager(settings.UPLOAD_STORAGE_DIR)

# RAG 检索器（lazy init：首次使用时加载 Chroma + ONNX 模型，不影响 health 检查）
_rag_retriever = None


def get_rag():
    global _rag_retriever
    if _rag_retriever is None:
        from .rag.retriever import RAGRetriever

        _rag_retriever = RAGRetriever()
    return _rag_retriever


_rag_init_lock: asyncio.Lock | None = None


async def get_rag_async():
    """异步获取 RAG：首次初始化（加载 Chroma + ONNX 嵌入模型，秒级）
    在线程池完成，不阻塞事件循环；双重检查 + 锁防止并发重复初始化"""
    global _rag_retriever, _rag_init_lock
    if _rag_init_lock is None:
        _rag_init_lock = asyncio.Lock()
    if _rag_retriever is None:
        async with _rag_init_lock:
            if _rag_retriever is None:
                from .rag.retriever import RAGRetriever

                _rag_retriever = await asyncio.to_thread(RAGRetriever)
    return _rag_retriever


# ---- 请求/响应模型 ----


class ChatRequest(BaseModel):
    message: str
    use_memory: bool = False
    use_rag: bool = False
    session_id: str | None = None  # 不传则自动生成
    file_ids: list[str] | None = None  # 附件文件 id 列表
    provider: str | None = None  # 首选 provider（'glm'/'gemini'），失败自动切换，默认全部按序尝试


class ChatResponse(BaseModel):
    success: bool
    provider: str | None = None
    answer: str | None = None
    sources: list[dict] | None = None
    session_id: str | None = None
    error: str | None = None
    files: list[dict] | None = None  # 本次对话引用的文件元信息


class MemoryRequest(BaseModel):
    category: str
    key: str
    value: str


class SettingsRequest(BaseModel):
    memory_enabled: bool = True
    ai_provider: str | None = None  # 'glm'/'gemini'/'auto'（None 表示自动）


class RenameRequest(BaseModel):
    title: str


# ---- 会话元信息摘要（异步后台任务）----

_SUMMARIZE_PROMPT = """你是一个对话摘要助手。请根据用户和AI的第一轮对话，生成以下三个字段，并**严格只输出合法 JSON**，不要任何解释、代码块或额外文字。

要求：
- title：8-20 字的中文标题，简洁概括主题，不要加引号
- summary：20-50 字的一句话中文摘要，完整表述对话的核心内容
- keywords：3-6 个关键词的字符串数组，优先用中文名词

--- 以下是对话内容 ---
用户问题：
{user_msg}

AI 回答（节选前 500 字）：
{ai_resp_short}
--- 对话结束 ---

输出格式示例：
{{"title":"STM32项目分析","summary":"讨论电机控制系统优化方案。","keywords":["STM32","电机控制"]}}
"""


def _extract_json(text: str) -> dict | None:
    """从 AI 返回内容中提取 JSON 对象，兼容包裹在 ```json 或其他文字中的情况。"""
    if not text:
        return None
    # 1) 直接解析
    try:
        return json.loads(text)
    except Exception:
        pass
    # 2) 找 ```json ... ```
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 3) 找 ``` ... ```
    m = re.search(r"```\s*(\{[\s\S]*?\})\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 4) 找第一个 { ... }
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None


async def summarize_session(
    *,
    user_id: int,
    session_id: str,
    user_msg: str,
    ai_resp: str,
) -> None:
    """后台调用 AI，生成会话 title/summary/keywords 并写入 conversation_meta。
    该函数本身不应抛出任何异常。"""
    # 并发上限：同时最多 SUMMARIZE_MAX_CONCURRENCY 个总结任务，
    # 其余排队等待，避免高并发时阻塞事件循环 / 打爆第三方 API
    async with _get_summarize_sem():
        await _summarize_session_impl(
            user_id=user_id,
            session_id=session_id,
            user_msg=user_msg,
            ai_resp=ai_resp,
        )


async def _summarize_session_impl(
    *,
    user_id: int,
    session_id: str,
    user_msg: str,
    ai_resp: str,
) -> None:
    """summarize_session 的实现体（信号量保护内执行）"""
    t0 = time.monotonic()
    try:
        ai_resp_short = (ai_resp or "")[:500]
        user_msg_short = (user_msg or "")[:300]
        prompt = _SUMMARIZE_PROMPT.format(
            user_msg=user_msg_short, ai_resp_short=ai_resp_short
        )

        parsed: dict | None = None
        last_err: str | None = None
        # 优先用千问（硅基流动），失败回退主 Provider
        providers_to_try = ([SUMMARIZER_PROVIDER] if SUMMARIZER_PROVIDER else []) + PROVIDERS
        for provider in providers_to_try:
            try:
                raw = await provider.chat(
                    [{"role": "user", "content": prompt}], timeout=30
                )
                parsed = _extract_json(raw) if raw else None
                if parsed and isinstance(parsed, dict) and parsed.get("title"):
                    break
            except Exception as exc:
                last_err = f"{provider.name}: {type(exc).__name__}: {str(exc)[:100]}"
                logger.warning("summarize provider=%s failed: %s", provider.name, last_err)

        if not parsed or not isinstance(parsed, dict):
            logger.warning(
                "summarize parse failed user=%s session=%s err=%s",
                user_id, session_id, last_err or "no-json",
            )
            # 兜底：用用户消息前 15 字作为标题（异步写库，不阻塞事件循环）
            title = (user_msg_short[:15] + "…") if len(user_msg_short) > 15 else user_msg_short or "新对话"
            await asyncio.to_thread(
                conversation_store.upsert_meta, user_id, session_id, title=title
            )
            return

        title = str(parsed.get("title") or "").strip()[:50]
        summary = str(parsed.get("summary") or "").strip()[:200]
        keywords_raw = parsed.get("keywords") or []
        if not isinstance(keywords_raw, list):
            keywords_raw = []
        keywords = [str(k).strip() for k in keywords_raw if str(k).strip()][:8]

        if not title:
            title = (user_msg_short[:15] + "…") if len(user_msg_short) > 15 else user_msg_short or "新对话"

        await asyncio.to_thread(
            conversation_store.upsert_meta,
            user_id,
            session_id,
            title=title,
            summary=summary,
            keywords=keywords,
        )
        logger.info(
            "summarize ok user=%s session=%s cost=%.2fs title=%s kw=%s",
            user_id, session_id, round(time.monotonic() - t0, 2), title, keywords,
        )
    except Exception as exc:
        logger.error(
            "summarize fatal user=%s session=%s err=%s: %s",
            user_id, session_id, type(exc).__name__, str(exc)[:300],
        )


# ---- 健康检查 ----


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "providers": [p.name for p in PROVIDERS]}


# ---- AI 对话（多用户隔离 + 可选记忆/RAG）----


def _load_text_file(storage_path: str, filename: str) -> str:
    """读取文本/代码文件内容，作为 prompt 上下文"""
    p = Path(storage_path)
    if not p.exists():
        return ""
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        try:
            from .rag.loader import load_file
            return load_file(str(p))
        except Exception as exc:
            logger.warning("pdf load failed: %s", exc)
            return ""
    # 其余文本/代码文件直接读取
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        logger.warning("read file failed %s: %s", filename, exc)
        return ""


def _load_image_b64(storage_path: str) -> str | None:
    """读取图片文件并返回 base64"""
    try:
        with open(storage_path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception as exc:
        logger.warning("read image failed: %s", exc)
        return None


def _build_files_context(file_records: list[dict]) -> tuple[str, list[str], list[dict]]:
    """构建文件上下文，返回 (text_ctx, image_b64_list, file_meta_for_response)"""
    text_parts: list[str] = []
    image_b64_list: list[str] = []
    file_meta: list[dict] = []

    for rec in file_records:
        meta = {
            "id": rec["id"],
            "filename": rec["filename"],
            "file_type": rec["file_type"],
            "file_size": rec["file_size"],
            "status": rec["status"],
        }
        file_meta.append(meta)

        if rec["file_type"] == "image":
            b64 = _load_image_b64(rec["storage_path"])
            if b64:
                image_b64_list.append(b64)
        else:  # text / code
            content = _load_text_file(rec["storage_path"], rec["filename"])
            if content:
                # 截断超长内容，避免 token 爆炸
                if len(content) > 12000:
                    content = content[:12000] + "\n...(内容过长已截断)"
                text_parts.append(
                    f"--- 文件：{rec['filename']} ---\n{content}\n--- 文件结束 ---"
                )

    text_ctx = "\n\n".join(text_parts)
    return text_ctx, image_b64_list, file_meta


def _collect_files_ctx(user_id: int, file_ids: list[str]) -> tuple[str, list[str], list[dict]]:
    """同步收集文件上下文（DB 查询 + 磁盘/PDF 解析 + base64），供 to_thread 调用，避免阻塞事件循环"""
    records = file_manager.list_by_ids(user_id, file_ids)
    if not records:
        return "", [], []
    return _build_files_context(records)


# ---- 统一 Chat Pipeline（chat / stream 共用）----


@dataclass
class GatheredCtx:
    """上下文收集结果（Memory/RAG/文件/课表），chat 与 stream 共用"""

    memory_ctx: str | None = None
    rag_ctx: str | None = None
    sources: list = field(default_factory=list)
    files_ctx: str | None = None
    file_meta: list = field(default_factory=list)
    image_b64_list: list = field(default_factory=list)
    schedule_ctx: str | None = None
    full_prompt: str = ""


async def _gather_contexts(
    req: ChatRequest, user_id: int, memory_enabled: bool
) -> AsyncGenerator[tuple[str, object], None]:
    """统一上下文收集管道（chat 与 stream 共用，消除双端重复组装）。

    异步生成器：先产出 ("status", state) 进度事件（stream 转发为 SSE，
    非流式调用方忽略），最后产出 ("ctx", GatheredCtx)。
    所有同步 IO/重计算均走线程池，不阻塞事件循环。
    """
    # 是否携带记忆/检索知识库：客户端 flag 优先，其次后端按消息自动判断（可配置关闭）
    use_memory = req.use_memory or (
        settings.CONTEXT_AUTO_MEMORY and memory_enabled and _needs_memory(req.message)
    )
    use_rag = req.use_rag or (settings.CONTEXT_AUTO_RAG and _needs_rag(req.message))

    g = GatheredCtx()
    prompt_parts: list[str] = []  # 仅用于翻译检测的完整文本

    # 长期记忆：仅当 use_memory 且用户开启 memory_enabled
    if use_memory and memory_enabled:
        yield "status", "retrieving_memory"
        try:
            memory_text = await asyncio.to_thread(memory_manager.get_context, user_id)
            # 赋予 AI 修改长期记忆的权限（仅用户开启记忆时）
            g.memory_ctx = (
                f"以下是关于用户的长期记忆信息：\n{memory_text}\n\n{_MEMORY_WRITE_NOTE}"
                if memory_text
                else _MEMORY_WRITE_NOTE
            )
            if memory_text:
                prompt_parts.append(f"以下是关于用户的长期记忆信息：\n{memory_text}")
            prompt_parts.append(_MEMORY_WRITE_NOTE)
        except Exception as exc:
            logger.warning("memory gather failed: %s", exc)

    # RAG 检索：绑定 user_id（ONNX 嵌入走线程池，按相似度阈值过滤无关片段）
    if use_rag:
        yield "status", "retrieving_knowledge"
        try:
            rag = await get_rag_async()
            results = await asyncio.to_thread(rag.search, req.message, user_id)
            if results:
                g.rag_ctx = (
                    "以下是检索到的参考知识库内容（仅在内容与用户问题高度相关时作为参考；"
                    "若与用户问题无关或无法回答问题，请忽略该内容，直接根据自身知识准确回答，切勿生搬硬套或强行关联）：\n"
                    + "\n\n---\n\n".join(r["content"] for r in results)
                )
                prompt_parts.append(g.rag_ctx)
                g.sources = results
        except Exception as exc:
            logger.warning(
                "RAG search failed: %s: %s", type(exc).__name__, str(exc)[:200]
            )

    # 文件附件：读取文本/代码进上下文，图片单独走视觉模型
    if req.file_ids:
        yield "status", "reading_files"
        file_text_ctx, g.image_b64_list, g.file_meta = await asyncio.to_thread(
            _collect_files_ctx, user_id, req.file_ids
        )
        if file_text_ctx:
            g.files_ctx = (
                f"以下是用户上传的文件内容，请结合这些内容回答用户问题：\n{file_text_ctx}"
            )
            prompt_parts.append(g.files_ctx)

    # 课程数据（AI 数据目录，内部函数读取；仅课表相关问题注入）
    try:
        sctx = await asyncio.to_thread(build_schedule_prompt, user_id, req.message)
        if sctx:
            g.schedule_ctx = (
                "以下是用户的课表信息，请基于此回答（提及今天/本周的课请结合周次与星期）：\n"
                f"{sctx}"
            )
            prompt_parts.append(g.schedule_ctx)
    except Exception as exc:
        logger.warning("schedule prompt failed: %s", str(exc)[:150])

    prompt_parts.append(req.message)
    g.full_prompt = "\n\n".join(prompt_parts)
    yield "ctx", g


def _providers_for_request(req: ChatRequest, settings_data: dict, g: GatheredCtx) -> list:
    """构造 provider 尝试顺序（翻译请求优先路由到混元 MT；首选由请求参数/用户设置决定）"""
    is_translate = (
        TRANSLATOR_PROVIDER is not None
        and not g.image_b64_list
        and _is_translation_request(g.full_prompt)
    )
    pref = req.provider or (settings_data.get("ai_provider") or None)
    return ([TRANSLATOR_PROVIDER] if is_translate else []) + _build_providers_to_try(pref)


async def _post_completion(
    *,
    user_id: int,
    session_id: str,
    req_message: str,
    answer: str,
    memory_enabled: bool,
    mem_ops: list | None = None,
) -> None:
    """完成后处理（chat 与 stream 共用）：写回记忆 → 保存历史 → 首轮触发标题摘要。
    所有失败仅记日志，不影响主响应。"""
    if not memory_enabled:
        return
    if mem_ops:
        try:
            await _apply_memory_ops(user_id, mem_ops)
        except Exception as exc:
            logger.warning("apply memory ops failed: %s", str(exc)[:150])
    if not answer:
        return
    try:
        await asyncio.to_thread(
            conversation_store.add, user_id, session_id, req_message, answer
        )
    except Exception as exc:
        logger.warning("save conversation failed: %s", str(exc)[:200])
    # 新会话首次生成 title / summary / keywords（已有标题则跳过，避免每轮冗余调用）
    try:
        meta = await asyncio.to_thread(conversation_store.get_meta, user_id, session_id)
        if not (meta and meta.get("title")):
            asyncio.create_task(
                summarize_session(
                    user_id=user_id,
                    session_id=session_id,
                    user_msg=req_message,
                    ai_resp=answer,
                )
            )
    except Exception as exc:
        logger.warning("schedule summarize failed: %s", str(exc)[:200])


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
    x_username: str = Header(..., alias="X-Username"),
    x_role: str = Header(..., alias="X-Role"),
) -> ChatResponse:
    """AI 对话：所有记忆/RAG 查询绑定 user_id"""
    start = time.monotonic()
    user_id = x_user_id
    session_id = req.session_id or str(uuid.uuid4())[:8]

    # 检查用户设置：memory_enabled（SQLite 同步 IO 走线程池，不阻塞事件循环）
    settings_data = await asyncio.to_thread(user_settings.get, user_id)
    memory_enabled = bool(settings_data["memory_enabled"])

    # 统一上下文收集（Memory/RAG/文件/课表，与流式端点共用同一条管道；忽略进度事件）
    g: GatheredCtx | None = None
    async for kind, payload in _gather_contexts(req, user_id, memory_enabled):
        if kind == "ctx":
            g = payload
    assert g is not None

    # 调用 AI Provider（翻译请求优先路由到混元 MT，视觉走视觉链）
    answer = None
    used_provider_name: str | None = None
    built: BuiltContext | None = None
    for provider in _providers_for_request(req, settings_data, g):
        try:
            if g.image_b64_list:
                answer = await provider.chat_with_images(
                    g.full_prompt, g.image_b64_list, timeout=settings.REQUEST_TIMEOUT
                )
            else:
                # 连续对话：Context Engine 组装（Token 预算内压缩），只构建一次
                if built is None:
                    built = await _build_context(
                        user_id=user_id,
                        session_id=session_id,
                        user_msg=req.message,
                        memory_ctx=g.memory_ctx,
                        rag_ctx=g.rag_ctx,
                        files_ctx=g.files_ctx,
                        schedule_ctx=g.schedule_ctx,
                        provider=provider,
                    )
                answer = await provider.chat(
                    built.messages, timeout=settings.REQUEST_TIMEOUT, system=built.system
                )
            used_provider_name = provider.name
            elapsed = round(time.monotonic() - start, 2)
            _log_chat_usage(
                "chat ok", provider.name, x_username, session_id, elapsed,
                len(g.image_b64_list), built, answer,
            )
            break
        except Exception as exc:
            logger.warning(
                "chat failed provider=%s error_type=%s msg=%s",
                provider.name,
                type(exc).__name__,
                str(exc)[:200],
            )

    if answer is None:
        _log_chat_usage(
            "chat failed", used_provider_name or "none", x_username, session_id,
            round(time.monotonic() - start, 2), len(g.image_b64_list), built, None,
        )
        return ChatResponse(success=False, error="All AI providers failed, please retry later.")

    # 提取 AI 主动写入的记忆指令（标签从展示文本中移除），
    # 完成后处理（保存/摘要）与流式端点共用
    mem_ops: list = []
    if memory_enabled:
        answer, mem_ops = _extract_memory_ops(answer)
    await _post_completion(
        user_id=user_id,
        session_id=session_id,
        req_message=req.message,
        answer=answer,
        memory_enabled=memory_enabled,
        mem_ops=mem_ops,
    )

    return ChatResponse(
        success=True,
        provider=used_provider_name,
        answer=answer,
        sources=g.sources or None,
        session_id=session_id,
        files=g.file_meta or None,
    )


# ---- SSE 流式对话 ----


def _sse(event: str, data: dict) -> str:
    """格式化一条 SSE 事件"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_chat_generator(
    req: ChatRequest, user_id: int, username: str
) -> AsyncGenerator[str, None]:
    """SSE 流式对话生成器：状态事件 + token 事件 + 完成/错误事件"""
    start = time.monotonic()
    session_id = req.session_id or str(uuid.uuid4())[:8]
    settings_data = await asyncio.to_thread(user_settings.get, user_id)
    memory_enabled = bool(settings_data["memory_enabled"])

    yield _sse("status", {"state": "analyzing", "session_id": session_id})

    # 1) 统一上下文收集（与非流式端点共用同一条管道；进度事件实时转发给客户端）
    g: GatheredCtx | None = None
    async for kind, payload in _gather_contexts(req, user_id, memory_enabled):
        if kind == "status":
            yield _sse("status", {"state": payload})
        else:
            g = payload
    assert g is not None
    sources = g.sources
    image_b64_list = g.image_b64_list
    file_meta = g.file_meta

    # 2) 调用 Provider 流式输出（翻译请求优先路由到混元 MT）
    yield _sse("status", {"state": "generating"})
    used_provider_name: str | None = None
    last_err: str | None = None
    built: BuiltContext | None = None
    # 流式过滤记忆指令标签：AI 写记忆的标签不显示给用户，完整提取后写回
    mem_filter = MemoryTagFilter()
    # 本轮是否完整成功结束：决定是否保存历史 / 应用记忆 / 生成标题
    completed = False
    interrupted = False

    for provider in _providers_for_request(req, settings_data, g):
        # 单次尝试的产出缓冲：失败时整段丢弃，避免与后续输出拼接混乱
        attempt_parts: list[str] = []
        produced = False
        try:
            if image_b64_list:
                # 视觉模型不支持流式：先一次性取完整结果，再分块 yield
                full = await provider.chat_with_images(
                    g.full_prompt, image_b64_list, timeout=settings.REQUEST_TIMEOUT
                )
                used_provider_name = provider.name
                # 按字符切片模拟流式
                chunk_size = max(1, len(full) // 40)
                for i in range(0, len(full), chunk_size):
                    piece = mem_filter.feed(full[i : i + chunk_size])
                    attempt_parts.append(piece)
                    yield _sse("token", {"text": piece})
                completed = True
                break
            # 连续对话：Context Engine 组装（Token 预算内压缩），只构建一次
            if built is None:
                built = await _build_context(
                    user_id=user_id,
                    session_id=session_id,
                    user_msg=req.message,
                    memory_ctx=g.memory_ctx,
                    rag_ctx=g.rag_ctx,
                    files_ctx=g.files_ctx,
                    schedule_ctx=g.schedule_ctx,
                    provider=provider,
                )
            async for token in provider.chat_stream(
                built.messages, timeout=120.0, system=built.system
            ):
                if token:
                    token = mem_filter.feed(token)
                    if token:
                        produced = True
                        attempt_parts.append(token)
                        yield _sse("token", {"text": token})
            used_provider_name = provider.name
            completed = True
            break
        except Exception as exc:
            last_err = f"{provider.name}: {type(exc).__name__}: {str(exc)[:120]}"
            logger.warning("stream chat failed provider=%s: %s", provider.name, last_err)
            if produced:
                # 已产出部分内容：不再回退下一个 provider（避免输出拼接混乱），
                # 本轮视为中断失败，不保存不完整回答（§十）
                interrupted = True
                break

    answer = "".join(attempt_parts)
    if completed:
        # 冲刷缓冲区（可能残留未完整输出的文本/标签；纯记忆指令时无可见文本也正常）
        tail = mem_filter.finish()
        if tail:
            answer += tail
            yield _sse("token", {"text": tail})

        # 完成后处理（写回记忆/保存历史/首轮标题摘要，与非流式端点共用）
        await _post_completion(
            user_id=user_id,
            session_id=session_id,
            req_message=req.message,
            answer=answer,
            memory_enabled=memory_enabled,
            mem_ops=mem_filter.ops if memory_enabled else None,
        )

        elapsed = round(time.monotonic() - start, 2)
        _log_chat_usage(
            "stream ok", used_provider_name, username, session_id, elapsed,
            len(image_b64_list), built, answer,
        )
        yield _sse(
            "complete",
            {
                "finish": True,
                "provider": used_provider_name,
                "session_id": session_id,
                "sources": sources or None,
                "files": file_meta or None,
            },
        )
    else:
        # 失败/中断：不保存不完整回答，记录 error 状态（§十）
        elapsed = round(time.monotonic() - start, 2)
        _log_chat_usage(
            "stream failed", used_provider_name, username, session_id, elapsed,
            len(image_b64_list), built, None,
        )
        if interrupted:
            yield _sse("error", {"message": f"Stream interrupted: {last_err}"})
        else:
            yield _sse(
                "error",
                {"message": last_err or "All AI providers failed, please retry later."},
            )


async def _sse_heartbeat(
    inner: AsyncGenerator[str, None], interval: float = 15.0
) -> AsyncGenerator[str, None]:
    """SSE 心跳：interval 秒无事件时发送 `: ping` 注释行。

    实现：pump 任务把 inner 的产出推入队列，主循环带超时消费。
    不会取消 inner 正在进行的单项产出（避免 token 丢失）；
    `: ping` 是 SSE 注释，前端解析器会忽略。
    作用：长思考/检索阶段保持链路活跃，防止 Cloudflare/Caddy 空闲断连。
    """
    q: asyncio.Queue = asyncio.Queue()
    _done = object()

    async def _pump() -> None:
        try:
            async for item in inner:
                await q.put(item)
        except Exception as exc:
            q.put_nowait(exc)
        finally:
            q.put_nowait(_done)

    pump_task = asyncio.create_task(_pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=interval)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue
            if item is _done:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        pump_task.cancel()


@app.post("/api/chat/stream")
async def chat_stream(
    req: ChatRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
    x_username: str = Header(..., alias="X-Username"),
    x_role: str = Header(..., alias="X-Role"),
):
    """SSE 流式对话：返回 event: status / token / complete / error"""
    return StreamingResponse(
        _sse_heartbeat(_stream_chat_generator(req, x_user_id, x_username)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---- 文件上传与管理 ----


def _format_file_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{round(n / 1024, 1)}KB"
    return f"{round(n / 1024 / 1024, 2)}MB"


@app.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    x_user_id: int = Header(..., alias="X-User-Id"),
    x_username: str = Header(..., alias="X-Username"),
) -> dict:
    """上传文件：保存到用户目录，返回文件元信息（status=temp）。

    流式落盘：不一次性读入内存，逐 1MB 块写入，内存占用与文件大小无关；
    先用 multipart 声明的大小预检，实际写入中再二次校验（防伪造头）。"""
    raw_name = file.filename or "unknown"
    allowed = IMAGE_EXTS | TEXT_EXTS | CODE_EXTS
    suffix = Path(raw_name).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported file type: {suffix}")

    max_bytes = settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024
    if file.size is not None and file.size > max_bytes:
        raise HTTPException(400, f"File too large, max {settings.UPLOAD_MAX_SIZE_MB}MB")

    file_type = classify_file_type(raw_name)
    user_dir = file_manager._user_dir(x_user_id)
    # 文件名 sanitize：去路径分隔符防穿越，uuid 前缀避免同名覆盖
    safe_base = Path(raw_name.replace("\\", "/")).name or "unknown"
    safe_name = f"{uuid.uuid4().hex[:8]}_{safe_base}"
    save_path = user_dir / safe_name

    written = 0
    try:
        with open(save_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        400, f"File too large, max {settings.UPLOAD_MAX_SIZE_MB}MB"
                    )
                out.write(chunk)
    except Exception:
        save_path.unlink(missing_ok=True)
        raise

    file_id = await asyncio.to_thread(
        file_manager.create,
        user_id=x_user_id,
        filename=raw_name,
        file_type=file_type,
        file_size=written,
        storage_path=str(save_path),
    )
    rec = await asyncio.to_thread(file_manager.get, x_user_id, file_id)

    logger.info(
        "file uploaded: user=%s id=%s name=%s type=%s size=%s",
        x_username, file_id, raw_name, file_type, _format_file_size(written),
    )
    return {
        "success": True,
        "file": {
            "id": file_id,
            "filename": rec["filename"],
            "file_type": rec["file_type"],
            "file_size": rec["file_size"],
            "size_label": _format_file_size(rec["file_size"]),
            "status": rec["status"],
            "created_at": rec["created_at"],
        },
    }


@app.get("/api/files")
async def list_files(
    status: str | None = None,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """列出当前用户的文件（默认全部，可按 status=temp|knowledge 过滤）"""
    files = await asyncio.to_thread(file_manager.list_by_user, x_user_id, status)
    for f in files:
        f["size_label"] = _format_file_size(f["file_size"])
    return {"files": files, "count": len(files)}


@app.get("/api/files/{file_id}")
async def get_file(
    file_id: str,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """获取单个文件元信息"""
    rec = await asyncio.to_thread(file_manager.get, x_user_id, file_id)
    if not rec:
        raise HTTPException(404, "File not found")
    rec["size_label"] = _format_file_size(rec["file_size"])
    return {"file": rec}


@app.post("/api/files/{file_id}/add-to-knowledge")
async def add_file_to_knowledge(
    file_id: str,
    category: str = "inbox",
    x_user_id: int = Header(..., alias="X-User-Id"),
    x_username: str = Header(..., alias="X-Username"),
) -> dict:
    """将临时文件加入知识库：生成 Embedding → 状态改为 knowledge"""
    rec = await asyncio.to_thread(file_manager.get, x_user_id, file_id)
    if not rec:
        raise HTTPException(404, "File not found")
    if rec["file_type"] == "image":
        raise HTTPException(400, "Image files cannot be added to knowledge base")
    if rec["status"] == "knowledge":
        return {"success": True, "message": "already in knowledge", "chunks": 0}

    # 切片 + 向量化（重 CPU 计算走线程池，不阻塞事件循环；入库期间其他请求正常服务）
    try:
        rag = await get_rag_async()
        chunk_count = await asyncio.to_thread(
            rag.add_file, rec["storage_path"], x_user_id, category
        )
    except Exception as exc:
        logger.error("add to knowledge failed: %s", exc)
        raise HTTPException(500, f"Failed to add to knowledge: {exc}")

    await asyncio.to_thread(file_manager.update_status, x_user_id, file_id, "knowledge")
    logger.info(
        "file -> knowledge: user=%s id=%s name=%s chunks=%d",
        x_username, file_id, rec["filename"], chunk_count,
    )
    return {
        "success": True,
        "filename": rec["filename"],
        "chunks": chunk_count,
        "category": category,
    }


@app.delete("/api/files/{file_id}")
async def delete_file(
    file_id: str,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """删除文件（仅删除物理文件 + 记录，已入库的向量需另行清理）"""
    ok = await asyncio.to_thread(file_manager.delete, x_user_id, file_id)
    if not ok:
        raise HTTPException(404, "File not found")
    return {"success": True, "id": file_id}


# ---- 对话历史 ----


@app.get("/api/conversations")
async def list_sessions(
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """列出当前用户的所有会话"""
    sessions = await asyncio.to_thread(conversation_store.list_sessions, x_user_id)
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/api/conversations/{session_id}")
async def get_conversation(
    session_id: str,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """获取某会话的对话历史（附带会话元信息）"""
    history, meta = await asyncio.to_thread(
        conversation_store.get_history_and_meta, x_user_id, session_id
    )
    return {
        "session_id": session_id,
        "messages": history,
        "count": len(history),
        "meta": meta,
    }


@app.patch("/api/conversations/{session_id}/summarize")
async def summarize_conversation(
    session_id: str,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """手动触发/重试 生成会话标题/摘要/关键词"""
    exchange = await asyncio.to_thread(
        conversation_store.get_first_exchange, x_user_id, session_id
    )
    if not exchange:
        raise HTTPException(404, "Conversation not found")
    await summarize_session(
        user_id=x_user_id,
        session_id=session_id,
        user_msg=exchange["message"],
        ai_resp=exchange["response"],
    )
    meta = await asyncio.to_thread(conversation_store.get_meta, x_user_id, session_id)
    return {"success": True, "meta": meta}


@app.patch("/api/conversations/{session_id}")
async def rename_conversation(
    session_id: str,
    req: RenameRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """重命名当前用户的会话标题"""
    title = (req.title or "").strip()[:50]
    ok = await asyncio.to_thread(conversation_store.rename_session, x_user_id, session_id, title)
    if not ok:
        raise HTTPException(404, "Conversation not found")
    logger.info("conversation renamed: user_id=%d session=%s", x_user_id, session_id)
    return {"success": True, "session_id": session_id, "title": title}


@app.delete("/api/conversations/{session_id}")
async def delete_conversation(
    session_id: str,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """删除当前用户的会话（对话记录 + 元信息）"""
    ok = await asyncio.to_thread(conversation_store.delete_session, x_user_id, session_id)
    if not ok:
        raise HTTPException(404, "Conversation not found")
    logger.info("conversation deleted: user_id=%d session=%s", x_user_id, session_id)
    return {"success": True, "session_id": session_id}


# ---- 知识库（多用户隔离）----


@app.post("/api/knowledge/add")
async def add_knowledge(
    file: UploadFile = File(...),
    category: str = Form("inbox"),
    x_user_id: int = Header(..., alias="X-User-Id"),
    x_username: str = Header(..., alias="X-Username"),
) -> dict:
    """上传知识文件到当前用户的私有知识库（流式落盘 + 文件名 sanitize 防路径穿越）"""
    allowed = {".md", ".txt", ".pdf", ".docx"}
    raw_name = (file.filename or "").strip()
    # sanitize：去路径分隔符（含 Windows 反斜杠），拒绝纯目录名
    safe_name = Path(raw_name.replace("\\", "/")).name
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(400, "Invalid filename")
    suffix = Path(safe_name).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported file type: {suffix}, allowed: {allowed}")

    # 保存到 knowledge 目录（按用户分目录），逐块流式写入并限制大小
    max_bytes = settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024
    if file.size is not None and file.size > max_bytes:
        raise HTTPException(400, f"File too large, max {settings.UPLOAD_MAX_SIZE_MB}MB")
    save_dir = Path(settings.KNOWLEDGE_BASE_DIR) / f"user_{x_user_id}" / category
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / safe_name
    written = 0
    try:
        with open(save_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        400, f"File too large, max {settings.UPLOAD_MAX_SIZE_MB}MB"
                    )
                out.write(chunk)
    except Exception:
        save_path.unlink(missing_ok=True)
        raise

    # 解析 → 切片 → 向量化（重计算走线程池，不阻塞事件循环；metadata 绑定 user_id）
    rag = await get_rag_async()
    chunk_count = await asyncio.to_thread(rag.add_file, str(save_path), x_user_id, category)

    logger.info(
        "knowledge added: user=%s file=%s chunks=%d category=%s",
        x_username, safe_name, chunk_count, category,
    )
    return {
        "success": True,
        "filename": safe_name,
        "chunks": chunk_count,
        "category": category,
    }


@app.get("/api/knowledge/search")
async def search_knowledge(
    query: str,
    top_k: int = 3,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """检索当前用户的知识库（ONNX 嵌入走线程池，不阻塞事件循环）"""
    rag = await get_rag_async()
    results = await asyncio.to_thread(rag.search, query, x_user_id, top_k)
    return {"query": query, "results": results, "count": len(results)}


# ---- 长期记忆（多用户隔离）----


@app.get("/api/memory")
async def get_memory(
    category: str | None = None,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """查看当前用户的长期记忆"""
    if category:
        memories = await asyncio.to_thread(
            memory_manager.get_by_category, x_user_id, category
        )
    else:
        memories = await asyncio.to_thread(memory_manager.get_all, x_user_id)
    return {"memories": memories, "count": len(memories)}


@app.post("/api/memory")
async def add_memory(
    req: MemoryRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """添加/更新记忆（绑定当前用户）"""
    await asyncio.to_thread(memory_manager.add, x_user_id, req.category, req.key, req.value)
    logger.info("memory added: user_id=%d [%s] %s", x_user_id, req.category, req.key)
    return {"success": True, "category": req.category, "key": req.key}


@app.delete("/api/memory")
async def delete_memory(
    category: str,
    key: str,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """删除当前用户的一条记忆"""
    deleted = await asyncio.to_thread(
        memory_manager.delete, x_user_id, category, key
    )
    if not deleted:
        raise HTTPException(404, "Memory not found")
    return {"success": True, "category": category, "key": key}


# ---- 用户设置 ----


@app.get("/api/settings")
async def get_settings(
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """获取当前用户的设置（含可用 provider 列表，供前端选择）"""
    data = await asyncio.to_thread(user_settings.get, x_user_id)
    data["available_providers"] = [p.name for p in PROVIDERS]
    return data


@app.put("/api/settings")
async def update_settings(
    req: SettingsRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """更新当前用户的设置"""
    # 只更新非空字段（memory_enabled 为开关无法区分未传，始终写入）
    await asyncio.to_thread(
        user_settings.set_memory_enabled, x_user_id, req.memory_enabled
    )
    if req.ai_provider is not None:
        pref = None if req.ai_provider in ("", "auto") else req.ai_provider
        if pref is not None and pref not in PROVIDER_BY_NAME:
            raise HTTPException(422, f"Unknown provider: {pref}")
        await asyncio.to_thread(user_settings.set_ai_provider, x_user_id, pref)
    logger.info(
        "settings updated: user_id=%d memory_enabled=%s ai_provider=%s",
        x_user_id, req.memory_enabled, req.ai_provider,
    )
    return {"success": True, "memory_enabled": req.memory_enabled, "ai_provider": req.ai_provider}


# ---- Admin 接口：跨用户管理 ----


@app.get("/api/admin/conversations")
async def admin_list_conversations(
    user_id: int,
    x_role: str = Header(..., alias="X-Role"),
) -> dict:
    """Admin 查看指定用户的会话列表"""
    if x_role != "admin":
        raise HTTPException(403, "Admin only")
    sessions = await asyncio.to_thread(conversation_store.list_sessions, user_id)
    return {"user_id": user_id, "sessions": sessions, "count": len(sessions)}


@app.get("/api/admin/memory")
async def admin_get_memory(
    user_id: int,
    x_role: str = Header(..., alias="X-Role"),
) -> dict:
    """Admin 查看指定用户的记忆"""
    if x_role != "admin":
        raise HTTPException(403, "Admin only")
    memories = await asyncio.to_thread(memory_manager.get_all, user_id)
    return {"user_id": user_id, "memories": memories, "count": len(memories)}


# ---- 图片生成（CogView）----


class ImageRequest(BaseModel):
    prompt: str
    size: str | None = None  # 例如 1024x1024


@app.post("/api/image/generate")
async def generate_image(
    req: ImageRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
    x_username: str = Header(..., alias="X-Username"),
) -> dict:
    """根据文本提示生成图片（cogview-3-flash）。返回图片 URL / base64。"""
    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(400, "Prompt is required")
    if len(prompt) > 1000:
        raise HTTPException(400, "Prompt too long (max 1000 chars)")

    if req.size:
        allowed_sizes = {"1024x1024", "768x1344", "864x1152", "1344x768", "1152x864"}
        if req.size not in allowed_sizes:
            raise HTTPException(
                400, f"Unsupported size: {req.size}, allowed: {sorted(allowed_sizes)}"
            )

    for provider in PROVIDERS:
        try:
            t_start = time.monotonic()
            result = await provider.generate_image(prompt, req.size)
            elapsed = round(time.monotonic() - t_start, 2)
            logger.info(
                "image generated provider=%s cost=%.2fs user=%s prompt_len=%d has_url=%s",
                provider.name, elapsed, x_username, len(prompt), bool(result.get("url")),
            )
            return {"success": True, "provider": provider.name, **result}
        except Exception as exc:
            logger.warning(
                "image generate failed provider=%s error_type=%s msg=%s",
                provider.name, type(exc).__name__, str(exc)[:200],
            )
    raise HTTPException(500, "Image generation failed, please retry later.")
