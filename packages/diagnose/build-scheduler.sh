#!/bin/bash
# 构建 + 测试 Scheduler 服务
set -e

echo "===== [1] 构建 Scheduler 镜像 ====="
cd /opt/snhgn/services/scheduler
DOCKER_BUILDKIT=0 docker compose up -d --build 2>&1 | tail -10
echo

echo "===== [2] 等待启动 ====="
sleep 4
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'scheduler|gateway'
echo

echo "===== [3] Scheduler Health ====="
curl -s -m 10 http://localhost:8002/health
echo
echo

echo "===== [4] 通过 Gateway 访问（未认证应返回401）====="
curl -s -m 10 -o /dev/null -w "HTTP %{http_code}" http://localhost:8001/api/scheduler/health
echo
echo

echo "===== [5] 登录 Gateway 获取 Token ====="
TOKEN=$(curl -s -m 10 -X POST http://localhost:8001/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"password":"changeme123"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")
echo "Token: ${TOKEN:0:30}..."
echo

echo "===== [6] 通过 Gateway 代理访问 Scheduler Health ====="
curl -s -m 10 http://localhost:8001/api/scheduler/health \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "===== [7] 查看空任务列表 ====="
curl -s -m 10 http://localhost:8001/api/scheduler/jobs \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "===== [8] 添加测试任务（每分钟 echo hello）====="
curl -s -m 10 -X POST http://localhost:8001/api/scheduler/jobs \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "id": "test-echo",
        "name": "测试-每分钟echo",
        "type": "command",
        "payload": "echo hello from scheduler $(date +%s)",
        "cron": "* * * * *",
        "timeout": 10
    }'
echo
echo

echo "===== [9] 添加 HTTP 测试任务（每天09:00 调用 ai-service）====="
curl -s -m 10 -X POST http://localhost:8001/api/scheduler/jobs \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "id": "daily-ai-ping",
        "name": "每日AI服务探活",
        "type": "http",
        "payload": "{\"url\":\"http://ai-service:8000/health\",\"method\":\"GET\"}",
        "cron": "0 9 * * *",
        "timeout": 30
    }'
echo
echo

echo "===== [10] 查看任务列表 ====="
curl -s -m 10 http://localhost:8001/api/scheduler/jobs \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo

echo "===== [11] 手动触发 echo 任务 ====="
curl -s -m 30 -X POST http://localhost:8001/api/scheduler/jobs/test-echo/trigger \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "===== [12] 手动触发 HTTP 任务 ====="
curl -s -m 30 -X POST http://localhost:8001/api/scheduler/jobs/daily-ai-ping/trigger \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "===== [13] 查看执行历史 ====="
sleep 2
curl -s -m 10 http://localhost:8001/api/scheduler/history \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo

echo "===== [14] 暂停任务 ====="
curl -s -m 10 -X POST http://localhost:8001/api/scheduler/jobs/test-echo/pause \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "===== [15] 恢复任务 ====="
curl -s -m 10 -X POST http://localhost:8001/api/scheduler/jobs/test-echo/resume \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "===== [16] 删除测试任务 ====="
curl -s -m 10 -X DELETE http://localhost:8001/api/scheduler/jobs/test-echo \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "===== [17] 最终任务列表 ====="
curl -s -m 10 http://localhost:8001/api/scheduler/jobs \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo

echo "===== [18] Scheduler 日志 ====="
docker logs scheduler --tail 15 2>&1
echo

echo "===== 完成: $(date) ====="
