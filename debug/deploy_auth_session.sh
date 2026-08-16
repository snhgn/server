#!/bin/bash
# 登录持久化改造部署:gateway(session+cookie+me+logout)+ 前端 dist + .env
set -euo pipefail
GW=/opt/snhgn/services/gateway
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p /opt/snhgn/backups

echo "== [1/7] 备份 =="
tar -czf /opt/snhgn/backups/pre-authsession-$TS.tar.gz -C $GW app/auth.py app/config.py app/main.py app/routers/auth.py scripts/migrate.py 2>/dev/null || true
rm -rf /opt/snhgn/backups/web-pre-authsession-$TS
cp -r /opt/website/web /opt/snhgn/backups/web-pre-authsession-$TS
echo "backup ok: pre-authsession-$TS"

echo "== [2/7] 解压补丁 =="
rm -rf /tmp/auth-patch /tmp/web-dist
mkdir -p /tmp/auth-patch /tmp/web-dist
tar -xzf /tmp/auth-patch.tar.gz -C /tmp/auth-patch
tar -xzf /tmp/web-dist.tar.gz -C /tmp/web-dist

echo "== [3/7] 覆盖 gateway 代码(6 文件) =="
cp /tmp/auth-patch/app/sessions.py        $GW/app/sessions.py
cp /tmp/auth-patch/app/auth.py            $GW/app/auth.py
cp /tmp/auth-patch/app/config.py          $GW/app/config.py
cp /tmp/auth-patch/app/routers/auth.py    $GW/app/routers/auth.py
cp /tmp/auth-patch/app/main.py            $GW/app/main.py
cp /tmp/auth-patch/scripts/migrate.py     $GW/scripts/migrate.py
find $GW -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
ls -la $GW/app/sessions.py

echo "== [4/7] .env 追加 SESSION_COOKIE_SECURE(生产 HTTPS) =="
if grep -q 'SESSION_COOKIE_SECURE' $GW/.env; then
  echo "already set:"; grep SESSION $GW/.env | sed 's/=.*/=<set>/'
else
  echo 'SESSION_COOKIE_SECURE=True' >> $GW/.env
  echo "appended"
fi

echo "== [5/7] 重建 gateway =="
cd $GW
docker compose build 2>&1 | tail -2
docker compose up -d 2>&1 | tail -2

echo "== [6/7] 部署前端 dist =="
rm -rf /opt/website/web/*
cp -r /tmp/web-dist/. /opt/website/web/
ls /opt/website/web/ | head -5

echo "== [7/7] 健康检查 =="
sleep 6
docker ps --format '{{.Names}}  {{.Status}}' | grep -E 'gateway|caddy|ai-service|scheduler|cloudflared'
echo "--- gateway /health ---"
curl -s -m 5 http://127.0.0.1:8001/health
echo
echo "--- /api/auth/me 未登录(应 401) ---"
curl -s -o /dev/null -w '%{http_code}\n' -m 5 http://127.0.0.1:8001/api/auth/me
echo "--- login 探活(错误密码应 401 且无 Set-Cookie) ---"
curl -s -o /dev/null -w '%{http_code}\n' -m 8 -X POST http://127.0.0.1:8001/api/auth/login -H 'Content-Type: application/json' -d '{"username":"__probe__","password":"x"}'
echo "DEPLOY-DONE"
