#!/bin/bash
# Assistant 部署验证脚本（服务器上执行）
set -u
echo "=== 1. health ==="
curl -s http://127.0.0.1:8000/health
echo

echo "=== 2. login ==="
LOGIN=$(curl -s -X POST http://127.0.0.1:8001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}')
TOKEN=$(echo "$LOGIN" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("token",""))' 2>/dev/null)
if [ -z "$TOKEN" ]; then
  echo "LOGIN FAILED: $LOGIN"
  exit 1
fi
echo "token_len=${#TOKEN}"

echo "=== 3. conversations list ==="
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8001/api/ai/conversations | head -c 500
echo

echo "=== 4. settings (providers) ==="
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8001/api/ai/settings
echo

echo "=== 5. create throwaway session via chat ==="
CHAT=$(curl -s -X POST http://127.0.0.1:8001/api/ai/chat \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"你好，请用一句话自我介绍","use_memory":false,"use_rag":false}')
echo "$CHAT" | head -c 400
echo
SID=$(echo "$CHAT" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("session_id",""))' 2>/dev/null)
echo "session_id=$SID"

if [ -n "$SID" ]; then
  echo "=== 6. rename session ==="
  curl -s -X PATCH "http://127.0.0.1:8001/api/ai/conversations/$SID" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"title":"部署验证-测试会话"}'
  echo
  echo "=== 7. rename again (conflict: not found) ==="
  curl -s -o /dev/null -w "http_code=%{http_code}\n" -X PATCH "http://127.0.0.1:8001/api/ai/conversations/nonexistent" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"title":"x"}'
  echo "=== 8. delete session ==="
  curl -s -X DELETE "http://127.0.0.1:8001/api/ai/conversations/$SID" \
    -H "Authorization: Bearer $TOKEN"
  echo
  echo "=== 9. delete again (expect 404) ==="
  curl -s -o /dev/null -w "http_code=%{http_code}\n" -X DELETE "http://127.0.0.1:8001/api/ai/conversations/$SID" \
    -H "Authorization: Bearer $TOKEN"
else
  echo "SKIP rename/delete tests (no session created)"
fi

echo "=== 10. website index (via caddy) ==="
curl -s -o /dev/null -w "index http_code=%{http_code}\n" http://127.0.0.1:8080/
curl -s http://127.0.0.1:8080/ | grep -o 'AiView-[A-Za-z0-9_-]*\.js' | head -2
echo "=== 11. SPA fallback /ai ==="
curl -s -o /dev/null -w "ai route http_code=%{http_code}\n" http://127.0.0.1:8080/ai
echo "=== 12. new asset served ==="
ASSET=$(curl -s http://127.0.0.1:8080/ | grep -o 'assets/AiView-[A-Za-z0-9_-]*\.js' | head -1)
echo "asset=$ASSET"
curl -s -o /dev/null -w "asset http_code=%{http_code}\n" "http://127.0.0.1:8080/$ASSET"
echo "=== 13. public site via cloudflare ==="
curl -s -o /dev/null -w "https://snhgn.me http_code=%{http_code}\n" --max-time 20 https://snhgn.me/
echo "DONE"
