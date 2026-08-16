#!/bin/bash
# P0+P1 重构部署脚本 (2026-08-15)
# 服务器拓扑: 三个独立 compose 项目 (/opt/snhgn/services/*) + caddy (/opt/website)
set -euo pipefail

TS=$(date +%Y%m%d-%H%M%S)
BK=/opt/snhgn/backups/pre-p0p1-$TS.tar.gz
SVCDIR=/opt/snhgn/services

echo "[1/8] 备份 app/Dockerfile/compose/Caddyfile"
mkdir -p /opt/snhgn/backups
tar -czf "$BK" -C "$SVCDIR" \
  ai-service/app gateway/app scheduler/app \
  ai-service/Dockerfile gateway/Dockerfile scheduler/Dockerfile \
  ai-service/docker-compose.yml gateway/docker-compose.yml scheduler/docker-compose.yml \
  -C /opt/website Caddyfile docker-compose.yml
echo "  -> $BK ($(du -h "$BK" | cut -f1))"

echo "[2/8] 解压新代码到暂存区"
rm -rf /tmp/p0p1 && mkdir -p /tmp/p0p1
tar -xzf /tmp/p0p1-payload.tar.gz -C /tmp/p0p1

echo "[3/8] 替换 app/ + Dockerfile + requirements.txt"
for svc in ai-service gateway scheduler; do
  rm -rf "$SVCDIR/$svc/app"
  cp -r "/tmp/p0p1/packages/$svc/app" "$SVCDIR/$svc/app"
  cp "/tmp/p0p1/packages/$svc/Dockerfile" "$SVCDIR/$svc/Dockerfile"
  cp "/tmp/p0p1/packages/$svc/requirements.txt" "$SVCDIR/$svc/requirements.txt"
done
echo "  files: $(find "$SVCDIR" -name '*.py' -path '*/app/*' | wc -l) py files staged"

echo "[4/8] 点改 compose: ai-service 端口收回回环(S2) + mem_limit"
sed -i 's/- "8000:8000"/- "127.0.0.1:8000:8000"/' "$SVCDIR/ai-service/docker-compose.yml"
set_memlimit() {
  local f=$1 lim=$2
  grep -q 'mem_limit' "$f" || sed -i "/restart: unless-stopped/a\\    mem_limit: $lim" "$f"
}
set_memlimit "$SVCDIR/ai-service/docker-compose.yml" 1536m
set_memlimit "$SVCDIR/scheduler/docker-compose.yml" 256m
set_memlimit "$SVCDIR/gateway/docker-compose.yml" 384m
set_memlimit /opt/website/docker-compose.yml 128m

echo "[5/8] 点改 Caddyfile: reverse_proxy 加 flush_interval -1(SSE 零缓冲)"
if ! grep -q 'flush_interval' /opt/website/Caddyfile; then
  sed -i 's|reverse_proxy gateway:8001$|reverse_proxy gateway:8001 {\n            flush_interval -1\n        }|' /opt/website/Caddyfile
fi

echo "[6/8] 构建三个镜像(依赖层缓存命中,只重建代码层)"
for svc in scheduler ai-service gateway; do
  echo "  --- build $svc ---"
  (cd "$SVCDIR/$svc" && docker compose build 2>&1 | tail -2)
done

echo "[7/8] 滚动重启(scheduler -> ai-service -> gateway)"
for svc in scheduler ai-service gateway; do
  (cd "$SVCDIR/$svc" && docker compose up -d 2>&1 | tail -1)
done

echo "[8/8] caddy: reload 配置 + 应用 mem_limit"
(cd /opt/website && docker compose config -q && docker compose up -d 2>&1 | tail -1)

echo
echo "===== 部署完成 ====="
docker ps --format '{{.Names}} | {{.Status}}' | sort
echo
echo "回滚命令(如需):"
echo "  tar -xzf $BK -C /  # 恢复所有被覆盖文件后逐服务 docker compose up -d --build"
