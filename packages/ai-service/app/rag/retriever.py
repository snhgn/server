import logging
from pathlib import Path

from ..config import settings
from .loader import chunk_text, load_file
from .vector_store import VectorStore

logger = logging.getLogger("ai-service.rag.retriever")


class RAGRetriever:
    """RAG 检索器：文件入库 + 知识检索"""

    def __init__(self) -> None:
        self.store = VectorStore()

    def add_file(self, file_path: str, user_id: int, category: str = "inbox") -> int:
        """解析文件 → 切片 → 向量化 → 存入 Chroma，返回切片数量"""
        text = load_file(file_path)
        chunks = chunk_text(text, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP)

        source = Path(file_path).name
        # id 加 user_id 前缀，避免不同用户同名文件 id 冲突
        ids = [f"u{user_id}_{source}_{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": source, "category": category, "user_id": user_id, "chunk": i}
            for i in range(len(chunks))
        ]

        self.store.add(chunks, metadatas, ids)
        return len(chunks)

    def search(
        self,
        query: str,
        user_id: int,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[dict]:
        """检索该用户的知识片段，过滤低于 min_score 的无关片段"""
        if top_k is None:
            top_k = settings.RAG_TOP_K
        if min_score is None:
            min_score = settings.RAG_MIN_SCORE

        results = self.store.query(query, top_k, user_id=user_id)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        filtered: list[dict] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            score = round(1 - dist, 4)
            if score >= min_score:
                filtered.append(
                    {
                        "content": doc,
                        "source": meta.get("source", ""),
                        "category": meta.get("category", ""),
                        "score": score,
                    }
                )
            else:
                logger.info(
                    "RAG chunk filtered out (score=%.4f < min_score=%.4f): source=%s snippet=%.60s",
                    score,
                    min_score,
                    meta.get("source", ""),
                    doc.replace("\n", " "),
                )

        return filtered

    def get_context(
        self,
        query: str,
        user_id: int,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> str:
        """检索并格式化为 prompt 上下文"""
        results = self.search(query, user_id, top_k, min_score=min_score)
        if not results:
            return ""
        return "\n\n---\n\n".join(r["content"] for r in results)
