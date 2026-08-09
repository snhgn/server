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
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import settings
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
from .providers.gemini import GeminiProvider
from .providers.glm import GLMProvider
from .providers.siliconflow import SiliconFlowProvider

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

app = FastAPI(title="AI Service Layer", version="3.0.0")

# Provider 注册：GLM 主调用，Gemini 备用（默认关闭）
PROVIDERS = [GLMProvider()]
if settings.GEMINI_ENABLED:
    PROVIDERS.append(GeminiProvider())

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


# ---- 请求/响应模型 ----


class ChatRequest(BaseModel):
    message: str
    use_memory: bool = False
    use_rag: bool = False
    session_id: str | None = None  # 不传则自动生成
    file_ids: list[str] | None = None  # 附件文件 id 列表


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
    memory_enabled: bool


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
        await _summarize_session_impl(user_id, session_id, user_msg, ai_resp)


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
                raw = await provider.chat(prompt, timeout=30)
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

    # 检查用户设置：memory_enabled
    settings_data = user_settings.get(user_id)
    memory_enabled = bool(settings_data["memory_enabled"])

    # 组合 prompt
    prompt_parts = []

    # 长期记忆：仅当 use_memory 且用户开启 memory_enabled
    if req.use_memory and memory_enabled:
        memory_ctx = memory_manager.get_context(user_id)
        if memory_ctx:
            prompt_parts.append(f"以下是关于用户的长期记忆信息：\n{memory_ctx}")
        # 赋予 AI 修改长期记忆的权限（仅用户开启记忆时）
        prompt_parts.append(_MEMORY_WRITE_NOTE)

    # RAG 检索：绑定 user_id
    sources: list[dict] = []
    if req.use_rag:
        try:
            rag = get_rag()
            results = rag.search(req.message, user_id)
            if results:
                rag_ctx = "\n\n---\n\n".join(r["content"] for r in results)
                prompt_parts.append(f"以下是与问题相关的知识库内容：\n{rag_ctx}")
                sources = results
        except Exception as exc:
            logger.warning(
                "RAG search failed: %s: %s", type(exc).__name__, str(exc)[:200]
            )

    # 文件附件：读取文本/代码进上下文，图片单独走视觉模型
    file_meta: list[dict] = []
    image_b64_list: list[str] = []
    if req.file_ids:
        file_records = file_manager.list_by_ids(user_id, req.file_ids)
        if file_records:
            file_text_ctx, image_b64_list, file_meta = _build_files_context(file_records)
            if file_text_ctx:
                prompt_parts.append(
                    f"以下是用户上传的文件内容，请结合这些内容回答用户问题：\n{file_text_ctx}"
                )

    prompt_parts.append(req.message)
    full_prompt = "\n\n".join(prompt_parts)

    # 调用 AI Provider（翻译请求优先路由到混元 MT，视觉走视觉链）
    answer = None
    used_provider_name: str | None = None
    is_translate = TRANSLATOR_PROVIDER is not None and not image_b64_list and _is_translation_request(full_prompt)
    providers_to_try = ([TRANSLATOR_PROVIDER] if is_translate else []) + PROVIDERS
    for provider in providers_to_try:
        try:
            if image_b64_list:
                answer = await provider.chat_with_images(
                    full_prompt, image_b64_list, timeout=settings.REQUEST_TIMEOUT
                )
            else:
                answer = await provider.chat(full_prompt, timeout=settings.REQUEST_TIMEOUT)
            used_provider_name = provider.name
            elapsed = round(time.monotonic() - start, 2)
            logger.info(
                "chat ok provider=%s cost=%.2fs user=%s images=%d",
                provider.name, elapsed, x_username, len(image_b64_list),
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
        logger.error(
            "chat failed all providers cost=%.2fs user=%s",
            round(time.monotonic() - start, 2),
            x_username,
        )
        return ChatResponse(success=False, error="All AI providers failed, please retry later.")

    # 提取 AI 主动写入的记忆指令（标签从展示文本中移除）
    if memory_enabled:
        answer, mem_ops = _extract_memory_ops(answer)
        if mem_ops:
            try:
                await _apply_memory_ops(user_id, mem_ops)
            except Exception as exc:
                logger.warning("apply memory ops failed: %s", str(exc)[:150])

    # 保存对话历史（仅当用户开启 memory_enabled，异步写库不阻塞主响应）
    if memory_enabled:
        try:
            await asyncio.to_thread(
                conversation_store.add, user_id, session_id, req.message, answer
            )
        except Exception as exc:
            logger.warning("save conversation failed: %s", str(exc)[:200])

    # 每次对话后异步生成 title / summary / keywords（不阻塞接口，结果保存到数据库）
    if memory_enabled:
        try:
            asyncio.create_task(
                summarize_session(
                    user_id=user_id,
                    session_id=session_id,
                    user_msg=req.message,
                    ai_resp=answer,
                )
            )
        except Exception as exc:
            logger.warning("schedule summarize failed: %s", str(exc)[:200])

    return ChatResponse(
        success=True,
        provider=used_provider_name,
        answer=answer,
        sources=sources or None,
        session_id=session_id,
        files=file_meta or None,
    )


# ---- SSE 流式对话 ----


def _sse(event: str, data: dict) -> str:
    """格式化一条 SSE 事件"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_chat_generator(
    req: ChatRequest, user_id: int, username: str
) -> AsyncGenerator[str, None]:
    """SSE 流式对话生成器：状态事件 + token 事件 + 完成事件"""
    start = time.monotonic()
    session_id = req.session_id or str(uuid.uuid4())[:8]
    settings_data = user_settings.get(user_id)
    memory_enabled = bool(settings_data["memory_enabled"])

    yield _sse("status", {"state": "analyzing", "session_id": session_id})

    # 1) 组合 prompt
    prompt_parts: list[str] = []

    # 1.1 长期记忆
    if req.use_memory and memory_enabled:
        yield _sse("status", {"state": "retrieving_memory"})
        try:
            memory_ctx = memory_manager.get_context(user_id)
            if memory_ctx:
                prompt_parts.append(f"以下是关于用户的长期记忆信息：\n{memory_ctx}")
            # 赋予 AI 修改长期记忆的权限（仅用户开启记忆时）
            prompt_parts.append(_MEMORY_WRITE_NOTE)
        except Exception as exc:
            logger.warning("stream memory failed: %s", exc)

    # 1.2 RAG
    sources: list[dict] = []
    if req.use_rag:
        yield _sse("status", {"state": "retrieving_knowledge"})
        try:
            rag = get_rag()
            results = rag.search(req.message, user_id)
            if results:
                rag_ctx = "\n\n---\n\n".join(r["content"] for r in results)
                prompt_parts.append(f"以下是与问题相关的知识库内容：\n{rag_ctx}")
                sources = results
        except Exception as exc:
            logger.warning("stream RAG failed: %s: %s", type(exc).__name__, exc)

    # 1.3 文件附件
    file_meta: list[dict] = []
    image_b64_list: list[str] = []
    if req.file_ids:
        yield _sse("status", {"state": "reading_files"})
        file_records = file_manager.list_by_ids(user_id, req.file_ids)
        if file_records:
            file_text_ctx, image_b64_list, file_meta = _build_files_context(file_records)
            if file_text_ctx:
                prompt_parts.append(
                    f"以下是用户上传的文件内容，请结合这些内容回答用户问题：\n{file_text_ctx}"
                )

    prompt_parts.append(req.message)
    full_prompt = "\n\n".join(prompt_parts)

    # 2) 调用 Provider 流式输出（翻译请求优先路由到混元 MT）
    yield _sse("status", {"state": "generating"})
    answer_parts: list[str] = []
    used_provider_name: str | None = None
    last_err: str | None = None
    # 流式过滤记忆指令标签：AI 写记忆的标签不显示给用户，完整提取后写回
    mem_filter = MemoryTagFilter()

    is_translate = TRANSLATOR_PROVIDER is not None and not image_b64_list and _is_translation_request(full_prompt)
    providers_to_try = ([TRANSLATOR_PROVIDER] if is_translate else []) + PROVIDERS
    for provider in providers_to_try:
        try:
            if image_b64_list:
                # 视觉模型不支持流式：先一次性取完整结果，再分块 yield
                full = await provider.chat_with_images(
                    full_prompt, image_b64_list, timeout=settings.REQUEST_TIMEOUT
                )
                used_provider_name = provider.name
                # 按字符切片模拟流式
                chunk_size = max(1, len(full) // 40)
                for i in range(0, len(full), chunk_size):
                    piece = full[i : i + chunk_size]
                    piece = mem_filter.feed(piece)
                    answer_parts.append(piece)
                    yield _sse("token", {"text": piece})
                break
            else:
                async for token in provider.chat_stream(full_prompt, timeout=120.0):
                    if token:
                        token = mem_filter.feed(token)
                        if token:
                            answer_parts.append(token)
                            yield _sse("token", {"text": token})
                used_provider_name = provider.name
                break
        except Exception as exc:
            last_err = f"{provider.name}: {type(exc).__name__}: {str(exc)[:120]}"
            logger.warning("stream chat failed provider=%s: %s", provider.name, last_err)

    answer = "".join(answer_parts)
    # 冲刷缓冲区（可能残留未完整输出的文本/标签；纯记忆指令时无可见文本也正常）
    tail = mem_filter.finish()
    if tail:
        answer += tail
        yield _sse("token", {"text": tail})

    if answer or mem_filter.ops:
        # 执行 AI 主动写入的记忆指令（即使没有可见文本也要执行）
        if memory_enabled and mem_filter.ops:
            try:
                await _apply_memory_ops(user_id, mem_filter.ops)
            except Exception as exc:
                logger.warning("stream apply memory ops failed: %s", str(exc)[:150])
        # 保存对话历史（异步写库，避免高并发写锁排队阻塞 SSE 完成事件）
        if memory_enabled and answer:
            try:
                await asyncio.to_thread(
                    conversation_store.add, user_id, session_id, req.message, answer
                )
            except Exception as exc:
                logger.warning("stream save conv failed: %s", exc)
        # 每次对话后异步生成并保存总结（不阻塞接口）
        if memory_enabled and answer:
            try:
                asyncio.create_task(
                    summarize_session(
                        user_id=user_id,
                        session_id=session_id,
                        user_msg=req.message,
                        ai_resp=answer,
                    )
                )
            except Exception as exc:
                logger.warning("stream schedule summarize failed: %s", exc)

        elapsed = round(time.monotonic() - start, 2)
        logger.info(
            "stream ok provider=%s cost=%.2fs user=%s images=%d",
            used_provider_name, elapsed, username, len(image_b64_list),
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
        yield _sse(
            "error",
            {"message": last_err or "All AI providers failed, please retry later."},
        )


@app.post("/api/chat/stream")
async def chat_stream(
    req: ChatRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
    x_username: str = Header(..., alias="X-Username"),
    x_role: str = Header(..., alias="X-Role"),
):
    """SSE 流式对话：返回 event: status / token / complete / error"""
    return StreamingResponse(
        _stream_chat_generator(req, x_user_id, x_username),
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
    """上传文件：保存到用户目录，返回文件元信息（status=temp）"""
    # 类型与大小校验
    allowed = IMAGE_EXTS | TEXT_EXTS | CODE_EXTS
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported file type: {suffix}")

    content = await file.read()
    max_bytes = settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            400, f"File too large, max {settings.UPLOAD_MAX_SIZE_MB}MB"
        )

    file_type = classify_file_type(file.filename or "")
    user_dir = file_manager._user_dir(x_user_id)
    # 用 uuid 前缀避免同名覆盖
    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    save_path = user_dir / safe_name
    save_path.write_bytes(content)

    file_id = file_manager.create(
        user_id=x_user_id,
        filename=file.filename or "unknown",
        file_type=file_type,
        file_size=len(content),
        storage_path=str(save_path),
    )
    rec = file_manager.get(x_user_id, file_id)

    logger.info(
        "file uploaded: user=%s id=%s name=%s type=%s size=%s",
        x_username, file_id, file.filename, file_type, _format_file_size(len(content)),
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
    files = file_manager.list_by_user(x_user_id, status)
    for f in files:
        f["size_label"] = _format_file_size(f["file_size"])
    return {"files": files, "count": len(files)}


@app.get("/api/files/{file_id}")
async def get_file(
    file_id: str,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """获取单个文件元信息"""
    rec = file_manager.get(x_user_id, file_id)
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
    rec = file_manager.get(x_user_id, file_id)
    if not rec:
        raise HTTPException(404, "File not found")
    if rec["file_type"] == "image":
        raise HTTPException(400, "Image files cannot be added to knowledge base")
    if rec["status"] == "knowledge":
        return {"success": True, "message": "already in knowledge", "chunks": 0}

    # 切片 + 向量化
    try:
        rag = get_rag()
        chunk_count = rag.add_file(rec["storage_path"], x_user_id, category)
    except Exception as exc:
        logger.error("add to knowledge failed: %s", exc)
        raise HTTPException(500, f"Failed to add to knowledge: {exc}")

    file_manager.update_status(x_user_id, file_id, "knowledge")
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
    ok = file_manager.delete(x_user_id, file_id)
    if not ok:
        raise HTTPException(404, "File not found")
    return {"success": True, "id": file_id}


# ---- 对话历史 ----


@app.get("/api/conversations")
async def list_sessions(
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """列出当前用户的所有会话"""
    sessions = conversation_store.list_sessions(x_user_id)
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/api/conversations/{session_id}")
async def get_conversation(
    session_id: str,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """获取某会话的对话历史（附带会话元信息）"""
    history = conversation_store.get_history(x_user_id, session_id)
    meta = conversation_store.get_meta(x_user_id, session_id)
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
    exchange = conversation_store.get_first_exchange(x_user_id, session_id)
    if not exchange:
        raise HTTPException(404, "Conversation not found")
    await summarize_session(
        user_id=x_user_id,
        session_id=session_id,
        user_msg=exchange["message"],
        ai_resp=exchange["response"],
    )
    meta = conversation_store.get_meta(x_user_id, session_id)
    return {"success": True, "meta": meta}


# ---- 知识库（多用户隔离）----


@app.post("/api/knowledge/add")
async def add_knowledge(
    file: UploadFile = File(...),
    category: str = Form("inbox"),
    x_user_id: int = Header(..., alias="X-User-Id"),
    x_username: str = Header(..., alias="X-Username"),
) -> dict:
    """上传知识文件到当前用户的私有知识库"""
    allowed = {".md", ".txt", ".pdf", ".docx"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported file type: {suffix}, allowed: {allowed}")

    # 保存到 knowledge 目录（按用户分目录）
    save_dir = Path(settings.KNOWLEDGE_BASE_DIR) / f"user_{x_user_id}" / category
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / file.filename
    content = await file.read()
    save_path.write_bytes(content)

    # 解析 → 切片 → 向量化（metadata 绑定 user_id）
    rag = get_rag()
    chunk_count = rag.add_file(str(save_path), x_user_id, category)

    logger.info(
        "knowledge added: user=%s file=%s chunks=%d category=%s",
        x_username, file.filename, chunk_count, category,
    )
    return {
        "success": True,
        "filename": file.filename,
        "chunks": chunk_count,
        "category": category,
    }


@app.get("/api/knowledge/search")
async def search_knowledge(
    query: str,
    top_k: int = 3,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """检索当前用户的知识库"""
    rag = get_rag()
    results = rag.search(query, x_user_id, top_k)
    return {"query": query, "results": results, "count": len(results)}


# ---- 长期记忆（多用户隔离）----


@app.get("/api/memory")
async def get_memory(
    category: str | None = None,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """查看当前用户的长期记忆"""
    if category:
        memories = memory_manager.get_by_category(x_user_id, category)
    else:
        memories = memory_manager.get_all(x_user_id)
    return {"memories": memories, "count": len(memories)}


@app.post("/api/memory")
async def add_memory(
    req: MemoryRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """添加/更新记忆（绑定当前用户）"""
    memory_manager.add(x_user_id, req.category, req.key, req.value)
    logger.info("memory added: user_id=%d [%s] %s", x_user_id, req.category, req.key)
    return {"success": True, "category": req.category, "key": req.key}


@app.delete("/api/memory")
async def delete_memory(
    category: str,
    key: str,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """删除当前用户的一条记忆"""
    deleted = memory_manager.delete(x_user_id, category, key)
    if not deleted:
        raise HTTPException(404, "Memory not found")
    return {"success": True, "category": category, "key": key}


# ---- 用户设置 ----


@app.get("/api/settings")
async def get_settings(
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """获取当前用户的设置"""
    return user_settings.get(x_user_id)


@app.put("/api/settings")
async def update_settings(
    req: SettingsRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> dict:
    """更新当前用户的设置"""
    user_settings.set_memory_enabled(x_user_id, req.memory_enabled)
    logger.info("settings updated: user_id=%d memory_enabled=%s", x_user_id, req.memory_enabled)
    return {"success": True, "memory_enabled": req.memory_enabled}


# ---- Admin 接口：跨用户管理 ----


@app.get("/api/admin/conversations")
async def admin_list_conversations(
    user_id: int,
    x_role: str = Header(..., alias="X-Role"),
) -> dict:
    """Admin 查看指定用户的会话列表"""
    if x_role != "admin":
        raise HTTPException(403, "Admin only")
    sessions = conversation_store.list_sessions(user_id)
    return {"user_id": user_id, "sessions": sessions, "count": len(sessions)}


@app.get("/api/admin/memory")
async def admin_get_memory(
    user_id: int,
    x_role: str = Header(..., alias="X-Role"),
) -> dict:
    """Admin 查看指定用户的记忆"""
    if x_role != "admin":
        raise HTTPException(403, "Admin only")
    memories = memory_manager.get_all(user_id)
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
