#!/bin/bash
# 服务器部署前探测脚本
echo "===== compose project labels ====="
for c in ai-service gateway scheduler caddy cloudflared; do
  echo "--- $c ---"
  docker inspect "$c" | grep -E 'com\.docker\.compose\.project"|working_dir|config_files' | head -5
done
echo
echo "===== /opt/snhgn/services tree ====="
ls /opt/snhgn/services/ai-service/
ls /opt/snhgn/services/gateway/
ls /opt/snhgn/services/scheduler/
echo
echo "===== compose files on server ====="
find /opt -maxdepth 3 -name 'docker-compose*.yml' -o -maxdepth 3 -name 'compose*.yml' 2>/dev/null
echo
echo "===== /opt/website ====="
ls /opt/website/
echo
echo "===== docker networks ====="
docker network ls
echo
echo "===== server resources ====="
free -h
df -h / | tail -1
