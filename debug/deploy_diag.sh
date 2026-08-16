#!/bin/bash
echo "===== A. gateway 容器日志(尾部40行)====="
docker logs gateway --tail 40 2>&1

echo
echo "===== B. 直连 gateway 登录测试 ====="
curl -s -w '\nHTTP:%{http_code} time:%{time_total}s\n' --max-time 15 -X POST http://127.0.0.1:8001/api/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}' | head -c 500

echo
echo "===== C. 直连 gateway 无token chat(应401)====="
curl -s -o /dev/null -w 'HTTP:%{http_code}\n' --max-time 10 -X POST http://127.0.0.1:8001/api/ai/chat \
  -H 'Content-Type: application/json' -d '{"message":"hi"}'

echo
echo "===== D. 经 caddy 的响应详情(登录)====="
curl -sv --max-time 15 -X POST http://127.0.0.1:8080/api/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}' 2>&1 | grep -E '^< |^> POST|HTTP|error|Empty' | head -15

echo
echo "===== E. caddy 容器日志(尾部20行)====="
docker logs caddy --tail 20 2>&1

echo
echo "===== F. caddy 内部到 gateway 的网络连通 ====="
docker exec caddy wget -q -O- --timeout=5 http://gateway:8001/health 2>&1 | head -c 200
echo
