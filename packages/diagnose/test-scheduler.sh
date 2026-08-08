#!/bin/bash
# 快速测试 Scheduler 接口
sleep 3

echo "=== [1] Scheduler Health ==="
curl -s -m 10 http://localhost:8002/health
echo
echo

echo "=== [2] Gateway 登录 ==="
TOKEN=$(curl -s -m 10 -X POST http://localhost:8001/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"password":"changeme123"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")
echo "Token: ${TOKEN:0:30}..."
echo

echo "=== [3] 通过 Gateway 代理访问 health ==="
curl -s -m 10 http://localhost:8001/api/scheduler/health \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "=== [4] 查看空任务列表 ==="
curl -s -m 10 http://localhost:8001/api/scheduler/jobs \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "=== [5] 添加 echo 测试任务 ==="
curl -s -m 10 -X POST http://localhost:8001/api/scheduler/jobs \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"id":"test-echo","name":"测试-每分钟echo","type":"command","payload":"echo hello from scheduler","cron":"* * * * *","timeout":10}'
echo
echo

echo "=== [6] 添加 HTTP 探活任务 ==="
curl -s -m 10 -X POST http://localhost:8001/api/scheduler/jobs \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"id":"daily-ai-ping","name":"每日AI服务探活","type":"http","payload":"{\"url\":\"http://ai-service:8000/health\",\"method\":\"GET\"}","cron":"0 9 * * *","timeout":30}'
echo
echo

echo "=== [7] 查看任务列表 ==="
curl -s -m 10 http://localhost:8001/api/scheduler/jobs \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo

echo "=== [8] 手动触发 echo 任务 ==="
curl -s -m 30 -X POST http://localhost:8001/api/scheduler/jobs/test-echo/trigger \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "=== [9] 手动触发 HTTP 任务 ==="
curl -s -m 30 -X POST http://localhost:8001/api/scheduler/jobs/daily-ai-ping/trigger \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "=== [10] 查看执行历史 ==="
sleep 2
curl -s -m 10 http://localhost:8001/api/scheduler/history \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo

echo "=== [11] 暂停 + 恢复 ==="
curl -s -m 10 -X POST http://localhost:8001/api/scheduler/jobs/test-echo/pause \
    -H "Authorization: Bearer $TOKEN"
echo
curl -s -m 10 -X POST http://localhost:8001/api/scheduler/jobs/test-echo/resume \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "=== [12] 删除测试任务 ==="
curl -s -m 10 -X DELETE http://localhost:8001/api/scheduler/jobs/test-echo \
    -H "Authorization: Bearer $TOKEN"
echo
echo

echo "=== [13] 最终任务列表 ==="
curl -s -m 10 http://localhost:8001/api/scheduler/jobs \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo

echo "=== [14] Scheduler 日志 ==="
docker logs scheduler --tail 10 2>&1
echo

echo "=== 完成: $(date) ==="
