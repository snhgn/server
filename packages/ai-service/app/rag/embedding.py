"""嵌入函数封装：使用 Chroma 内置 ONNX 嵌入（all-MiniLM-L6-v2）"""

import chromadb.utils.embedding_functions as ef

_ef = None


def get_embedding_function():
    """获取单例嵌入函数（首次调用时加载 ONNX 模型）"""
    global _ef
    if _ef is None:
        _ef = ef.DefaultEmbeddingFunction()
    return _ef
