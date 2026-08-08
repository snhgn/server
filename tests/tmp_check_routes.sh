#!/bin/bash
# 模拟浏览器登录后访问各页面
echo "=== SPA routes (应返回 200 + index.html) ==="
for p in / /ai /dashboard /scripts /schedule /settings /knowledge /server /login; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: snhgn.me' "http://localhost:8080$p")
  echo "$p -> $code"
done

echo ""
echo "=== 登录拿 token ==="
TOKEN=$(curl -s -X POST -H 'Host: snhgn.me' -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' \
  "http://localhost:8080/api/auth/login" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")
echo "token: ${TOKEN:0:40}..."

echo ""
echo "=== 带 token 调各 API ==="
for ep in /api/auth/verify /api/ai/memory /api/ai/settings /api/ai/conversations; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: snhgn.me' -H "Authorization: Bearer $TOKEN" "http://localhost:8080$ep")
  echo "$ep -> $code"
done

echo ""
echo "=== POST /api/ai/chat ==="
curl -s -X POST -H 'Host: snhgn.me' -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"hi","use_memory":false,"use_rag":false}' \
  "http://localhost:8080/api/ai/chat" | head -c 200
echo
