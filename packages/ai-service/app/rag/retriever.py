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

    def add_file(self, file_path: str, category: str = "inbox") -> int:
        """解析文件 → 切片 → 向量化 → 存入 Chroma，返回切片数量"""
        text = load_file(file_path)
        chunks = chunk_text(text, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP)

        source = Path(file_path).name
        ids = [f"{source}_{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": source, "category": category, "chunk": i}
            for i in range(len(chunks))
        ]

        self.store.add(chunks, metadatas, ids)
        return len(chunks)

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """检索相关知识片段"""
        if top_k is None:
            top_k = settings.RAG_TOP_K

        results = self.store.query(query, top_k)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        return [
            {
                "content": doc,
                "source": meta.get("source", ""),
                "category": meta.get("category", ""),
                "score": round(1 - dist, 4),
            }
            for doc, meta, dist in zip(documents, metadatas, distances)
        ]

    def get_context(self, query: str, top_k: int | None = None) -> str:
        """检索并格式化为 prompt 上下文"""
        results = self.search(query, top_k)
        if not results:
            return ""
        return "\n\n---\n\n".join(r["content"] for r in results)
