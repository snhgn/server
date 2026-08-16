#!/bin/bash
# P0+P1 部署验证(修正: 带 Host: snhgn.me 头模拟 cloudflared 流量)
H='Host: snhgn.me'
B=http://127.0.0.1:8080

echo "===== 1. 无token API 保护(应401 JSON)====="
curl -s -w '\nHTTP:%{http_code}\n' --max-time 10 -H "$H" $B/api/ai/conversations | head -c 300

echo
echo "===== 2. 登录(全链路)====="
LOGIN=$(curl -s --max-time 10 -X POST -H "$H" $B/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}')
echo "  resp: $(echo "$LOGIN" | head -c 100)"
TOKEN=$(echo "$LOGIN" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("token") or "")' 2>/dev/null || true)
echo "  token length: ${#TOKEN}"

echo
echo "===== 3. 非流式 chat(GLM 真实调用,P0/P1 新管道)====="
time curl -s --max-time 90 -X POST -H "$H" $B/api/ai/chat \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"请只回复两个字:收到"}' | head -c 400
echo

echo
echo "===== 4. 流式 chat SSE(P0 心跳管道 + Caddy flush_interval)====="
timeout 60 curl -s -N -X POST -H "$H" $B/api/ai/chat/stream \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"从1数到5,每个数字一行"}' | head -14
echo "  [...截断]"

echo
echo "===== 5. 静态首页(应返回HTML)====="
curl -s -H "$H" $B/ | head -c 120
echo
