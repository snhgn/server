#!/bin/bash
for svc in ai-service gateway scheduler; do
  echo "############ $svc Dockerfile ############"
  cat "/opt/snhgn/services/$svc/Dockerfile"
  echo "############ $svc docker-compose.yml ############"
  cat "/opt/snhgn/services/$svc/docker-compose.yml"
done
echo "############ ai-service/app ############"
ls /opt/snhgn/services/ai-service/app/
echo "############ gateway/app ############"
ls /opt/snhgn/services/gateway/app/
echo "############ scheduler/app ############"
ls /opt/snhgn/services/scheduler/app/
echo "############ /opt/website/Caddyfile ############"
cat /opt/website/Caddyfile
echo "############ /opt/website/docker-compose.yml ############"
cat /opt/website/docker-compose.yml
