#!/bin/bash
# 快速测试 status
TOKEN=$(curl -s -m 10 -X POST http://localhost:8001/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"password":"changeme123"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")
echo "Token: ${TOKEN:0:30}..."
echo
echo "=== 系统状态 ==="
curl -s -m 10 http://localhost:8001/api/status \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
