#!/bin/bash
H='Host: snhgn.me'
B=http://127.0.0.1:8080

echo "===== A. ai-service 最近日志(含流式成功的记录)====="
docker logs ai-service --since 6m 2>&1 | tail -30

echo
echo "===== B. 直连 ai-service 非流式 chat(绕过 gateway,60s 超时)====="
time curl -s -w '\nHTTP:%{http_code}\n' --max-time 60 -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -H 'X-User-Id: 1' -H 'X-Username: admin' -H 'X-Role: admin' \
  -d '{"message":"请只回复两个字:收到"}' | head -c 400

echo
echo "===== C. 请求后 ai-service 新增日志 ====="
docker logs ai-service --since 1m 2>&1 | tail -15
