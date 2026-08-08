import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import settings
from .embedding import get_embedding_function

logger = logging.getLogger("ai-service.rag.vector_store")


class VectorStore:
    """Chroma 向量库封装：持久化存储、文档向量化、相似度检索"""

    def __init__(self) -> None:
        Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.ef = get_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "VectorStore ready: collection='%s', documents=%d",
            settings.CHROMA_COLLECTION_NAME,
            self.collection.count(),
        )

    def add(self, texts: list[str], metadatas: list[dict], ids: list[str]) -> None:
        self.collection.add(documents=texts, metadatas=metadatas, ids=ids)
        logger.info("Added %d chunks to vector store", len(texts))

    def query(self, query_text: str, top_k: int = 3, user_id: int | None = None) -> dict:
        """按 user_id 过滤检索（None 表示不过滤，仅 admin 全局查询时使用）"""
        where = {"user_id": user_id} if user_id is not None else None
        return self.collection.query(
            query_texts=[query_text], n_results=top_k, where=where
        )
