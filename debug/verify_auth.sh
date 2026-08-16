#!/bin/bash
# 登录持久化改造:全链路验证(临时测试用户,结束自动清理)
set -uo pipefail
GW=http://127.0.0.1:8001
CJ=/tmp/cj_test.txt
PASS=0; FAIL=0
ok()  { echo "  [PASS] $1"; PASS=$((PASS+1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }

echo "== 0. 容器与网关健康 =="
docker ps --format '{{.Names}}  {{.Status}}' | grep -E 'gateway|caddy'
curl -s -m 5 $GW/health; echo

echo "== 1. 创建临时测试用户(id=999, __s_test__/s-test-123)+ sessions 表 =="
docker exec gateway python -c "
import sqlite3, bcrypt
conn = sqlite3.connect('/data/gateway.db')
conn.execute(\"CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', created_at TEXT)\")
h = bcrypt.hashpw(b's-test-123', bcrypt.gensalt(rounds=4)).decode()
conn.execute(\"INSERT OR REPLACE INTO users (id, username, password_hash, role) VALUES (999, '__s_test__', ?, 'user')\", (h,))
conn.commit(); conn.close(); print('user ready')
"
docker exec gateway python -c "from app import sessions; sessions.init(); print('sessions table ready')"

echo "== 2. [测试5] 未登录访问受保护 API(应 401) =="
c=$(curl -s -o /dev/null -w '%{http_code}' $GW/api/auth/me)
[ "$c" = "401" ] && ok "GET /api/auth/me -> 401" || bad "GET /api/auth/me -> $c"
c=$(curl -s -o /dev/null -w '%{http_code}' $GW/api/ai/conversations)
[ "$c" = "401" ] && ok "GET /api/ai/conversations -> 401" || bad "conversations -> $c"

echo "== 3. [测试1] 正常登录 =="
rm -f $CJ
resp=$(curl -s -c $CJ -X POST $GW/api/auth/login -H 'Content-Type: application/json' -d '{"username":"__s_test__","password":"s-test-123"}')
echo "$resp" | grep -q '"success":true' && ok "登录成功(JSON)" || bad "登录失败: $resp"
hdr=$(curl -s -D - -o /dev/null -c /dev/null -X POST $GW/api/auth/login -H 'Content-Type: application/json' -d '{"username":"__s_test__","password":"s-test-123"}' | grep -i 'set-cookie' | head -1)
echo "  Set-Cookie: ${hdr:0:110}..."
echo "$hdr" | grep -qi 'httponly' && ok "HttpOnly" || bad "无 HttpOnly"
echo "$hdr" | grep -qi 'samesite=lax' && ok "SameSite=Lax" || bad "无 SameSite"
echo "$hdr" | grep -qi 'secure' && ok "Secure(生产 HTTPS)" || bad "无 Secure"
echo "$hdr" | grep -q 'Max-Age=2592000' && ok "Max-Age=30天" || bad "Max-Age 异常"
[ -s "$CJ" ] && grep -q snhgn_session $CJ && ok "客户端已存 Cookie" || bad "cookie jar 为空"

echo "== 4. [测试2/3] 仅凭 Cookie 访问(等价于刷新页面/重开浏览器) =="
c=$(curl -s -o /dev/null -w '%{http_code}' -b $CJ $GW/api/auth/me)
[ "$c" = "200" ] && ok "GET /me 仅 Cookie -> 200(登录保持)" || bad "/me -> $c"
body=$(curl -s -b $CJ $GW/api/auth/me)
echo "$body" | grep -q '__s_test__' && ok "/me 返回正确用户" || bad "/me 用户错误: $body"
echo "  /me body: $body"

echo "== 5. JWT 兼容通道(旧客户端/脚本) =="
token=$(echo "$resp" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' 2>/dev/null)
if [ -n "$token" ]; then
  c=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $token" $GW/api/auth/me)
  [ "$c" = "200" ] && ok "Bearer JWT /me -> 200" || bad "Bearer /me -> $c"
  c=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $token" $GW/api/ai/conversations)
  [ "$c" = "200" ] && ok "Bearer JWT /api/ai/conversations -> 200" || bad "ai conversations -> $c"
else
  bad "token 提取失败"
fi

echo "== 6. [测试7] 越权/伪造防护 =="
c=$(curl -s -o /dev/null -w '%{http_code}' -H 'Cookie: snhgn_session=forged-sid-not-exist' $GW/api/auth/me)
[ "$c" = "401" ] && ok "伪造 Session ID -> 401" || bad "伪造 sid -> $c"
# AI 数据按 X-User-Id(网关注入)隔离,请求体无法指定他人 user_id
body=$(curl -s -b $CJ $GW/api/ai/conversations)
echo "  用户999会话列表(隔离数据): ${body:0:100}"

echo "== 7. [测试6] logout 后旧 Session 失效 =="
lout=$(curl -s -b $CJ -X POST $GW/api/auth/logout)
echo "$lout" | grep -q '"success":true' && ok "logout 200" || bad "logout: $lout"
c=$(curl -s -o /dev/null -w '%{http_code}' -b $CJ $GW/api/auth/me)
[ "$c" = "401" ] && ok "logout 后旧 Cookie -> 401(服务端真失效)" || bad "logout 后 -> $c"

echo "== 8. 清理测试用户 =="
docker exec gateway python -c "
import sqlite3
conn = sqlite3.connect('/data/gateway.db')
conn.execute('DELETE FROM users WHERE id=999')
conn.execute('DELETE FROM sessions WHERE user_id=999')
conn.commit(); conn.close(); print('cleaned')
"

echo "== 9. 公网验证(https://snhgn.me,经 Cloudflare) =="
c=$(curl -s -o /dev/null -w '%{http_code}' -m 20 https://snhgn.me/)
[ "$c" = "200" ] && ok "公网首页 200" || bad "公网首页 -> $c"
c=$(curl -s -o /dev/null -w '%{http_code}' -m 20 https://snhgn.me/api/auth/me)
[ "$c" = "401" ] && ok "公网 /me 未登录 401" || bad "公网 /me -> $c"
c=$(curl -s -o /dev/null -w '%{http_code}' -m 20 https://snhgn.me/api/ai/conversations)
[ "$c" = "401" ] && ok "公网受保护 API 未登录 401" || bad "公网 ai -> $c"
# 新前端已上线:入口 js hash 应为本地产物
entry=$(curl -s -m 20 https://snhgn.me/ | grep -o 'assets/index-[A-Za-z0-9_-]*\.js' | head -1)
echo "  公网入口 js: $entry (期望 index-DbjhuwfC.js)"

echo "=================================="
echo "RESULT: PASS=$PASS FAIL=$FAIL"
