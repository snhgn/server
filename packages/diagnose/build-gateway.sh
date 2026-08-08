#!/bin/bash
# 下载 gateway wheels + 构建 + 测试
cd /opt/snhgn/services/gateway

echo "=== [1] 下载 wheels ==="
docker run --rm \
  -v /opt/snhgn/services/gateway/wheels:/wheels \
  -v /opt/snhgn/services/gateway/requirements.txt:/requirements.txt:ro \
  python:3.12-slim \
  pip download -r /requirements.txt -d /wheels \
    -i https://pypi.tuna.tsinghua.edu.cn/simple --prefer-binary 2>&1 | tail -5
echo "wheels: $(ls wheels/ | wc -l) files"
echo

echo "=== [2] 构建 + 启动 ==="
DOCKER_BUILDKIT=0 docker compose up -d --build 2>&1
BUILD_EXIT=$?
echo "构建退出码: $BUILD_EXIT"
if [ $BUILD_EXIT -ne 0 ]; then echo "构建失败"; exit 1; fi
echo

echo "=== [3] 等待启动 ==="
sleep 3
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'gateway|ai-service|caddy'
echo

echo "=== [4] Health 检查（公开）==="
curl -s -m 10 http://localhost:8001/health
echo
echo

echo "=== [5] 未认证访问（应返回401）==="
curl -s -m 10 http://localhost:8001/api/status
echo
echo

echo "=== [6] 登录获取 Token ==="
TOKEN=$(curl -s -m 10 -X POST http://localhost:8001/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"password":"changeme123"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")
echo "Token: ${TOKEN:0:30}..."
echo

echo "=== [7] 验证 Token ==="
curl -s -m 10 http://localhost:8001/api/auth/verify \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "=== [8] 系统状态 ==="
curl -s -m 10 http://localhost:8001/api/status \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool 2>/dev/null || \
curl -s -m 10 http://localhost:8001/api/status \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "=== [9] AI 代理测试（转发到 ai-service）==="
curl -s -m 130 -X POST http://localhost:8001/api/ai/api/chat \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"message":"hello","use_memory":false,"use_rag":false}'
echo
echo

echo "=== 完成 ==="
echo "时间: $(date)"
