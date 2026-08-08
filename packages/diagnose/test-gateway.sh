#!/bin/bash
# Gateway 测试脚本
cd /opt/snhgn/services/gateway

echo "=== [1] 重建容器 ==="
DOCKER_BUILDKIT=0 docker compose up -d --force-recreate 2>&1 | tail -5
sleep 3
echo

echo "=== [2] Health（公开）==="
curl -s -m 10 http://localhost:8001/health
echo
echo

echo "=== [3] 未认证访问（应返回401）==="
curl -s -m 10 -o /dev/null -w "HTTP %{http_code}" http://localhost:8001/api/status
echo
echo

echo "=== [4] 登录获取 Token ==="
LOGIN_RESP=$(curl -s -m 10 -X POST http://localhost:8001/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"password":"changeme123"}')
echo "$LOGIN_RESP"
TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
echo "Token: ${TOKEN:0:40}..."
echo

echo "=== [5] 验证 Token ==="
curl -s -m 10 http://localhost:8001/api/auth/verify \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "=== [6] 系统状态 ==="
curl -s -m 10 http://localhost:8001/api/status \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "=== [7] AI 代理（转发到 ai-service /health）==="
curl -s -m 10 -o /dev/null -w "HTTP %{http_code}" http://localhost:8001/api/ai/health \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "=== [8] AI 对话（转发到 ai-service /api/chat）==="
curl -s -m 130 -X POST http://localhost:8001/api/ai/api/chat \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"message":"hello","use_memory":false,"use_rag":false}'
echo
echo

echo "=== 完成: $(date) ==="
