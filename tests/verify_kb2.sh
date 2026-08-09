#!/bin/bash
docker exec ai-service python3 -c "
import httpx
tests = ['工程制图 三视图 基本体', '毛中特 什么是社会主义', '物理竞赛 电磁学', '高等数学 函数极限', '近代史 选择题', '培养计划 学分要求']
for q in tests:
    r = httpx.get('http://localhost:8000/api/knowledge/search', params={'query': q, 'top_k': 2}, headers={'X-User-Id': '1'})
    d = r.json()
    res = d.get('results', [])
    line = ' | '.join(f\"[{x.get('category')}]{x.get('source')}({x.get('score')})\" for x in res)
    print(f'{q} -> {line}')
"
