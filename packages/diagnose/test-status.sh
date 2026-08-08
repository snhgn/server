#!/bin/bash
# 重建并测试 status 接口
cd /opt/snhgn/services/gateway

echo "=== 重建镜像 ==="
DOCKER_BUILDKIT=0 docker compose up -d --build 2>&1 | tail -5
sleep 3

echo "=== 登录 ==="
TOKEN=$(curl -s -m 10 -X POST http://localhost:8001/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"password":"changeme123"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")
echo "Token: ${TOKEN:0:30}..."
echo

echo "=== 系统状态（含容器列表）==="
curl -s -m 10 http://localhost:8001/api/status \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo

echo "=== 完成: $(date) ==="
