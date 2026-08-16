#!/bin/bash
# 流式 + 日志 + 数据库列 验证
set -u
echo "=== 1. SSE streaming via gateway ==="
TOKEN=$(curl -s -X POST http://127.0.0.1:8001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("token",""))')
curl -s -N -X POST http://127.0.0.1:8001/api/ai/chat/stream \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"数到三，用英文","use_memory":false,"use_rag":false}' \
  --max-time 40 | head -c 700
echo
echo "=== 2. memory endpoint ==="
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8001/api/ai/memory | head -c 200
echo
echo "=== 3. conversation_meta columns ==="
docker exec ai-service python -c "import sqlite3; c=sqlite3.connect('/data/memory.db'); print([r[1] for r in c.execute('PRAGMA table_info(conversation_meta)').fetchall()])"
echo "=== 4. ai-service recent logs (context usage) ==="
docker logs ai-service --since 10m 2>&1 | grep -E "chat ok|stream ok|context|ERROR|Traceback" | tail -8
echo "=== 5. gateway recent logs ==="
docker logs gateway --since 5m 2>&1 | grep -E "ERROR|Traceback|405|422" | tail -5
echo DONE
