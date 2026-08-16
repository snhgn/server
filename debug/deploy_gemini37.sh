#!/bin/bash
set -euo pipefail

echo "=== [1/5] Backing up ==="
mkdir -p /opt/snhgn/backups
TS=$(date +%Y%m%d-%H%M%S)
tar -czf "/opt/snhgn/backups/pre-gemini37-${TS}.tar.gz" -C /opt/ai-service app docker-compose.yml Dockerfile .env
echo "Backup created: /opt/snhgn/backups/pre-gemini37-${TS}.tar.gz"

echo "=== [2/5] Extracting update ==="
tar -xzf /tmp/ai_service_update.tar.gz -C /opt/ai-service/

echo "=== [3/5] Updating .env ==="
if grep -q '^GEMINI_MODEL=' /opt/ai-service/.env; then
    sed -i 's/^GEMINI_MODEL=.*/GEMINI_MODEL=gemini-3.7-flash/' /opt/ai-service/.env
else
    echo 'GEMINI_MODEL=gemini-3.7-flash' >> /opt/ai-service/.env
fi
grep '^GEMINI_MODEL=' /opt/ai-service/.env

echo "=== [4/5] Building and restarting ai-service container ==="
cd /opt/ai-service
docker compose build
docker compose up -d

echo "=== [5/5] Checking container status ==="
sleep 4
docker ps --filter name=ai-service --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
