#!/bin/bash
# 部署 AI 脚本生成/审查功能(scheduler)
set -e
cd /opt/snhgn/services/scheduler

# 1. 备份
BACKUP="pre-aigen-$(date +%Y%m%d-%H%M%S)"
mkdir -p /opt/snhgn/backups/$BACKUP
cp app/config.py app/routers/scripts.py docker-compose.yml /opt/snhgn/backups/$BACKUP/
echo "[1] backup -> /opt/snhgn/backups/$BACKUP"

# 2. 解包新代码(tar 包内结构: app/config.py app/routers/scripts.py)
tar -xzf /tmp/aigen_patch.tar.gz -C /opt/snhgn/services/scheduler/
echo "[2] code extracted"

# 3. compose 加 scripts volume(幂等:sed 仅在缺失时追加)
if ! grep -q '/opt/snhgn/scripts:/app/scripts' docker-compose.yml; then
  sed -i 's|- /opt/snhgn/logs/scheduler:/app/logs|&\n      - /opt/snhgn/scripts:/app/scripts|' docker-compose.yml
  echo "[3] volume added to compose"
else
  echo "[3] volume already present"
fi

# 4. 宿主代码目录
mkdir -p /opt/snhgn/scripts
chmod 755 /opt/snhgn/scripts

# 5. 重建 scheduler
docker compose build 2>&1 | tail -2
docker compose up -d 2>&1 | tail -2
sleep 6
docker ps --filter name=scheduler --format '{{.Names}}  {{.Status}}'
docker exec scheduler python -c "from app.routers.scripts import admin_generate_code, admin_review_code; print('IMPORT-OK')"
docker exec scheduler sh -c 'ls -ld /app/scripts'
echo "DEPLOY-DONE"
