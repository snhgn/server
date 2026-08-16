#!/bin/bash
set -e
cd /opt/snhgn/services/scheduler
tar -xzf /tmp/aigen_patch2.tar.gz
docker exec scheduler rm -f /app/scripts/aigen_selftest.py
docker compose up -d --build 2>&1 | tail -2
sleep 5
docker ps --filter name=scheduler --format '{{.Names}}  {{.Status}}'
docker exec scheduler python -c "from app.routers.scripts import admin_generate_code; print('IMPORT-OK')"
echo "--- /opt/snhgn/scripts ---"
ls /opt/snhgn/scripts/
echo "PATCH2-DONE"
