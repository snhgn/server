#!/bin/bash
echo "=== Chroma 统计 ==="
docker exec ai-service python3 -c "
from app.rag.vector_store import VectorStore
vs = VectorStore()
print('total documents:', vs.collection.count())
"
echo ""
echo "=== 检索测试 ==="
docker exec ai-service python3 -c "
import json, httpx
r = httpx.get('http://localhost:8000/api/knowledge/search', params={'query': '线性代数期末试卷', 'top_k': 3}, headers={'X-User-Id': '1'})
d = r.json()
print('count:', d.get('count'))
for item in d.get('results', []):
    print('-', item.get('category'), '|', item.get('source'), '| score', item.get('score'))
    print('  ', item.get('content', '')[:60])
"
