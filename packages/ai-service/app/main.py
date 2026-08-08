"""AI Service - 多用户隔离版"""
import logging
import logging.handlers
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel

from .config import settings
from .memory.manager import ConversationStore, MemoryManager, UserSettingsManager
from .providers.gemini import GeminiProvider
from .providers.glm import GLMProvider

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

# 存储管理器（SQLite，启动时初始化）
memory_manager = MemoryManager()
conversation_store = ConversationStore()
user_settings = UserSettingsManager()

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


class ChatResponse(BaseModel):
    success: bool
    provider: str | None = None
    answer: str | None = None
    sources: list[dict] | None = None
    session_id: str | None = None
    error: str | None = None


class MemoryRequest(BaseModel):
    category: str
    key: str
    value: str


class SettingsRequest(BaseModel):
    memory_enabled: bool


# ---- 健康检查 ----


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "providers": [p.name for p in PROVIDERS]}


# ---- AI 对话（多用户隔离 + 可选记忆/RAG）----


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

    prompt_parts.append(req.message)
    full_prompt = "\n\n".join(prompt_parts)

    # 调用 AI Provider（不变）
    answer = None
    for provider in PROVIDERS:
        try:
            answer = await provider.chat(full_prompt, timeout=settings.REQUEST_TIMEOUT)
            elapsed = round(time.monotonic() - start, 2)
            logger.info(
                "chat ok provider=%s cost=%.2fs user=%s", provider.name, elapsed, x_username
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

    # 保存对话历史（仅当用户开启 memory_enabled）
    if memory_enabled:
        try:
            conversation_store.add(user_id, session_id, req.message, answer)
        except Exception as exc:
            logger.warning("save conversation failed: %s", str(exc)[:200])

    return ChatResponse(
        success=True,
        provider=provider.name,
        answer=answer,
        sources=sources or None,
        session_id=session_id,
    )


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
    """获取某会话的对话历史"""
    history = conversation_store.get_history(x_user_id, session_id)
    return {"session_id": session_id, "messages": history, "count": len(history)}


# ---- 知识库（多用户隔离）----


@app.post("/api/knowledge/add")
async def add_knowledge(
    file: UploadFile = File(...),
    category: str = Form("inbox"),
    x_user_id: int = Header(..., alias="X-User-Id"),
    x_username: str = Header(..., alias="X-Username"),
) -> dict:
    """上传知识文件到当前用户的私有知识库"""
    allowed = {".md", ".txt", ".pdf"}
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
