#!/bin/bash
# P0+P1 部署后全链路验证
echo "===== 1. 容器状态 ====="
docker ps --format '{{.Names}} | {{.Status}}' | sort

echo
echo "===== 2. 端口绑定(S2: 8000 应只绑 127.0.0.1)====="
ss -tlnp 2>/dev/null | grep -E ':(8000|8001|8002|8080)\s'

echo
echo "===== 3. 配置点改确认 ====="
grep -Hn 'mem_limit\|127.0.0.1:8000' /opt/snhgn/services/ai-service/docker-compose.yml /opt/snhgn/services/gateway/docker-compose.yml /opt/snhgn/services/scheduler/docker-compose.yml /opt/website/docker-compose.yml
grep -n -A1 'flush_interval' /opt/website/Caddyfile

echo
echo "===== 4. 健康检查(直连)====="
echo -n "  gateway:8001/health    -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://127.0.0.1:8001/health
echo -n "  ai-service:8000/health -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://127.0.0.1:8000/health
echo -n "  scheduler:8002/health  -> "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://127.0.0.1:8002/health

echo
echo "===== 5. 登录(经 Caddy 全链路)====="
LOGIN=$(curl -s --max-time 10 -X POST http://127.0.0.1:8080/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}')
echo "  resp: $(echo "$LOGIN" | head -c 120)"
TOKEN=$(echo "$LOGIN" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("token") or d.get("access_token") or "")' 2>/dev/null || true)
echo "  token length: ${#TOKEN}"

echo
echo "===== 6. 非流式 chat(GLM 真实调用)====="
curl -s --max-time 90 -X POST http://127.0.0.1:8080/api/ai/chat \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"请只回复两个字:收到"}' | head -c 400
echo

echo
echo "===== 7. 流式 chat SSE(验证 flush + status 事件)====="
timeout 60 curl -s -N -X POST http://127.0.0.1:8080/api/ai/chat/stream \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"从1数到5,每个数字一行"}' | head -12
echo "  [...截断]"

echo
echo "===== 8. 网站首页 + API 401 保护 ====="
echo -n "  /            -> "; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/
echo -n "  /api/ai/chat 无token -> "; curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8080/api/ai/chat -H 'Content-Type: application/json' -d '{"message":"hi"}'

echo
echo "===== 9. uvicorn 启动参数 + 内存水位 ====="
docker logs ai-service 2>&1 | grep -m2 -iE 'started|uvicorn|error' || docker logs ai-service 2>&1 | tail -3
docker logs gateway 2>&1 | grep -m2 -iE 'started|uvicorn|error' || true
docker stats --no-stream --format '{{.Name}} | {{.MemUsage}} | {{.CPUPerc}}' | sort
