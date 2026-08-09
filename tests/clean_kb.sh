#!/bin/bash
docker exec ai-service python3 -c "
from app.rag.vector_store import VectorStore
vs = VectorStore()
col = vs.collection
# 统计
count = col.count()
print('total documents before:', count)
# 删除 user_id=1 的所有文档
col.delete(where={'user_id': 1})
print('total documents after:', col.count())
"
