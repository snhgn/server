#!/bin/bash
echo "===== A. 服务器 Caddyfile 当前内容(cat -A 显示不可见字符)====="
cat -A /opt/website/Caddyfile

echo
echo "===== B. caddy adapt 校验 ====="
docker exec caddy caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1 | head -50

echo
echo "===== C. 经 caddy GET /api/ai/conversations 无token(应401带JSON)====="
curl -s -w '\nHTTP:%{http_code}\n' --max-time 10 http://127.0.0.1:8080/api/ai/conversations

echo
echo "===== D. 经 caddy POST login 完整响应头 ====="
curl -s -D - -o /tmp/resp_body.txt --max-time 15 -X POST http://127.0.0.1:8080/api/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}'
echo "body file size: $(wc -c < /tmp/resp_body.txt)"

echo
echo "===== E. gateway 实时日志监听窗口内再打一次请求 ====="
(cd /opt/snhgn/services/gateway && docker compose logs --tail 1 -f gateway &) ; sleep 1
curl -s -o /dev/null -w 'login via caddy: HTTP:%{http_code}\n' --max-time 15 -X POST http://127.0.0.1:8080/api/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}'
sleep 2
pkill -f "docker compose logs" 2>/dev/null || true
docker logs gateway --since 30s 2>&1 | tail -10
