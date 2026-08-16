#!/bin/bash
# P0+P1 重构部署脚本 v2 (2026-08-15)
# v2 修复: gateway/app/schedule/models 为 root 所有无法删除 -> 改用 tar 覆盖式解压并排除 models
set -euo pipefail

SVCDIR=/opt/snhgn/services

echo "[1/8] 备份(已存在则复用)"
mkdir -p /opt/snhgn/backups
BK=$(ls -t /opt/snhgn/backups/pre-p0p1-*.tar.gz 2>/dev/null | head -1 || true)
if [ -z "$BK" ]; then
  TS=$(date +%Y%m%d-%H%M%S)
  BK=/opt/snhgn/backups/pre-p0p1-$TS.tar.gz
  tar -czf "$BK" -C "$SVCDIR" \
    ai-service/app gateway/app scheduler/app \
    ai-service/Dockerfile gateway/Dockerfile scheduler/Dockerfile \
    ai-service/docker-compose.yml gateway/docker-compose.yml scheduler/docker-compose.yml \
    -C /opt/website Caddyfile docker-compose.yml
fi
echo "  -> $BK ($(du -h "$BK" | cut -f1))"

echo "[2/8] 解压新代码到暂存区"
rm -rf /tmp/p0p1 && mkdir -p /tmp/p0p1
tar -xzf /tmp/p0p1-payload.tar.gz -C /tmp/p0p1

echo "[3/8] 覆盖式同步代码(排除 schedule/models 服务器运行资产)"
# 覆盖解压不删除服务器已有文件:models(root 所有)原样保留,代码全部以本地新版覆盖
tar -xzf /tmp/p0p1-payload.tar.gz -C "$SVCDIR" --strip-components=1 \
  --exclude='*/app/schedule/models' --exclude='*/app/schedule/models/*' \
  packages/ai-service packages/gateway packages/scheduler
echo "  py files: $(find "$SVCDIR" -name '*.py' -path '*/app/*' | wc -l)"
echo "  models kept: $(find "$SVCDIR/gateway/app/schedule/models" -type f 2>/dev/null | wc -l) files"

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

echo "[8/8] caddy: 应用 mem_limit"
(cd /opt/website && docker compose config -q && docker compose up -d 2>&1 | tail -1)

echo
echo "===== 部署完成 ====="
docker ps --format '{{.Names}} | {{.Status}}' | sort
echo
echo "备份: $BK"
echo "回滚: tar -xzf $BK -C / && 逐服务 docker compose up -d --build"
