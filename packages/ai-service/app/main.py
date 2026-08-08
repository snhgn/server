import logging
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .config import settings
from .memory.manager import MemoryManager
from .providers.gemini import GeminiProvider
from .providers.glm import GLMProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ai-service")

app = FastAPI(title="AI Service Layer", version="2.0.0")

# Provider 注册：GLM 主调用，Gemini 备用（默认关闭）
PROVIDERS = [GLMProvider()]
if settings.GEMINI_ENABLED:
    PROVIDERS.append(GeminiProvider())

# 长期记忆（SQLite，轻量，启动时初始化）
memory_manager = MemoryManager()

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


class ChatResponse(BaseModel):
    success: bool
    provider: str | None = None
    answer: str | None = None
    sources: list[dict] | None = None
    error: str | None = None


class MemoryRequest(BaseModel):
    category: str
    key: str
    value: str


# ---- 健康检查 ----


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "providers": [p.name for p in PROVIDERS]}


# ---- AI 对话（增强版：可选长期记忆 + RAG 检索）----


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    start = time.monotonic()

    # 组合 prompt
    prompt_parts = []

    if req.use_memory:
        memory_ctx = memory_manager.get_context()
        if memory_ctx:
            prompt_parts.append(f"以下是关于用户的长期记忆信息：\n{memory_ctx}")

    sources: list[dict] = []
    if req.use_rag:
        try:
            rag = get_rag()
            results = rag.search(req.message)
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

    for provider in PROVIDERS:
        try:
            answer = await provider.chat(
                full_prompt, timeout=settings.REQUEST_TIMEOUT
            )
            elapsed = round(time.monotonic() - start, 2)
            logger.info("chat ok provider=%s cost=%.2fs", provider.name, elapsed)
            return ChatResponse(
                success=True,
                provider=provider.name,
                answer=answer,
                sources=sources or None,
            )
        except Exception as exc:
            logger.warning(
                "chat failed provider=%s error_type=%s msg=%s",
                provider.name,
                type(exc).__name__,
                str(exc)[:200],
            )

    logger.error(
        "chat failed all providers cost=%.2fs", round(time.monotonic() - start, 2)
    )
    return ChatResponse(
        success=False, error="All AI providers failed, please retry later."
    )


# ---- 知识库 ----


@app.post("/api/knowledge/add")
async def add_knowledge(
    file: UploadFile = File(...),
    category: str = Form("inbox"),
):
    """上传知识文件，自动解析、切片、向量化存入 Chroma"""
    allowed = {".md", ".txt", ".pdf"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported file type: {suffix}, allowed: {allowed}")

    # 保存到 knowledge 目录
    save_dir = Path(settings.KNOWLEDGE_BASE_DIR) / category
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / file.filename
    content = await file.read()
    save_path.write_bytes(content)

    # 解析 → 切片 → 向量化
    rag = get_rag()
    chunk_count = rag.add_file(str(save_path), category)

    logger.info(
        "knowledge added: %s, chunks=%d, category=%s", file.filename, chunk_count, category
    )
    return {
        "success": True,
        "filename": file.filename,
        "chunks": chunk_count,
        "category": category,
    }


@app.get("/api/knowledge/search")
async def search_knowledge(query: str, top_k: int = 3):
    """测试知识检索"""
    rag = get_rag()
    results = rag.search(query, top_k)
    return {"query": query, "results": results}


# ---- 长期记忆 ----


@app.get("/api/memory")
async def get_memory(category: str | None = None):
    """查看长期记忆"""
    if category:
        memories = memory_manager.get_by_category(category)
    else:
        memories = memory_manager.get_all()
    return {"memories": memories, "count": len(memories)}


@app.post("/api/memory")
async def add_memory(req: MemoryRequest):
    """添加/更新记忆"""
    memory_manager.add(req.category, req.key, req.value)
    logger.info("memory added: [%s] %s", req.category, req.key)
    return {"success": True, "category": req.category, "key": req.key}
