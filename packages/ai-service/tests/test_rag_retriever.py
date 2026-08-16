import re
import sys
import unittest
from unittest.mock import MagicMock

# 模拟 chromadb（本地未安装 C++ 构建的 chromadb 库）
sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("chromadb.config", MagicMock())
sys.modules.setdefault("chromadb.utils.embedding_functions", MagicMock())

_RAG_NEED_RE = re.compile(
    r"(知识库|知识点|资料库|我的文档|上传的文档|上传的文件|我的文件|项目文档|"
    r"查阅文档|查看文档|查下资料|查资料|搜资料|从库里|库里面|知识库里|"
    r"教材内容|课件内容|论文内容|说明书内容|手册内容|代码库内容|课程设计文档|报告内容)"
)


def _needs_rag(message: str) -> bool:
    return bool(_RAG_NEED_RE.search(message or ""))


from app.rag.retriever import RAGRetriever


class TestRAGNeeds(unittest.TestCase):
    def test_needs_rag_explicit(self):
        self.assertTrue(_needs_rag("查一下知识库里的说明书"))
        self.assertTrue(_needs_rag("从我的文档里找一下报告"))
        self.assertTrue(_needs_rag("查阅文档"))
        self.assertTrue(_needs_rag("上传的文件里写了什么"))

    def test_needs_rag_avoids_generic_words(self):
        # 通用对话词不应误触发 RAG
        self.assertFalse(_needs_rag("帮我分析一下这段代码"))
        self.assertFalse(_needs_rag("请总结这几个要点"))
        self.assertFalse(_needs_rag("根据常识，地球是圆的吗？"))
        self.assertFalse(_needs_rag("今天天气怎么样"))
        self.assertFalse(_needs_rag("查询当前时间"))


class TestRAGRetrieverFilter(unittest.TestCase):
    def test_search_score_threshold_filtering(self):
        retriever = RAGRetriever.__new__(RAGRetriever)
        retriever.store = MagicMock()
        # 模拟 Chroma 返回 3 条结果，相似度分别为 0.75, 0.40, 0.15 (dist: 0.25, 0.60, 0.85)
        retriever.store.query.return_value = {
            "documents": [["文档内容A", "文档内容B", "无关文档C"]],
            "metadatas": [
                [
                    {"source": "a.txt", "category": "inbox"},
                    {"source": "b.txt", "category": "inbox"},
                    {"source": "c.txt", "category": "inbox"},
                ]
            ],
            "distances": [[0.25, 0.60, 0.85]],
        }

        # 默认 min_score=0.35: A (score=0.75) 和 B (score=0.40) 保留，C (score=0.15) 过滤
        results = retriever.search("测试查询", user_id=1, min_score=0.35)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["source"], "a.txt")
        self.assertEqual(results[0]["score"], 0.75)
        self.assertEqual(results[1]["source"], "b.txt")
        self.assertEqual(results[1]["score"], 0.40)

        # min_score=0.50: 仅 A 保留
        results_strict = retriever.search("测试查询", user_id=1, min_score=0.50)
        self.assertEqual(len(results_strict), 1)
        self.assertEqual(results_strict[0]["source"], "a.txt")


if __name__ == "__main__":
    unittest.main()
