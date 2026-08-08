#!/bin/bash
pkill -f 'docker compose' 2>/dev/null
pkill -f 'docker build' 2>/dev/null
docker rm -f $(docker ps -aq --filter status=exited) 2>/dev/null
docker builder prune -f 2>/dev/null
echo '=== MEM ==='
free -h
echo '=== CONTAINERS ==='
docker ps --format '{{.Names}} {{.Status}}'
