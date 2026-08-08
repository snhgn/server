#!/bin/bash
# 服务器状态检查脚本
echo "===== 1. 系统信息 ====="
uname -a
echo "CPU: $(nproc) cores"
free -h | head -2
df -h / | tail -1
echo

echo "===== 2. /opt/snhgn 目录结构 ====="
if [ -d /opt/snhgn ]; then
    find /opt/snhgn -maxdepth 3 -type d 2>/dev/null | sort
    echo "--- 顶层文件 ---"
    ls -la /opt/snhgn/ 2>/dev/null
else
    echo "/opt/snhgn 不存在"
fi
echo

echo "===== 3. /opt 其他服务 ====="
ls -la /opt/ 2>/dev/null
echo

echo "===== 4. Docker 容器 ====="
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
echo

echo "===== 5. Docker 镜像 ====="
docker images --format 'table {{.Repository}}:{{.Tag}}\t{{.Size}}' | head -20
echo

echo "===== 6. Docker 网络 ====="
docker network ls
echo "--- snhgn-network 详情 ---"
docker network inspect snhgn-network --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null || echo "snhgn-network 不存在"
echo

echo "===== 7. Docker Compose 文件位置 ====="
find /opt -name "docker-compose.yml" -o -name "compose.yml" 2>/dev/null
echo

echo "===== 8. 监听端口 ====="
ss -tlnp 2>/dev/null | head -20
echo

echo "===== 9. systemd 服务（snhgn相关） ====="
systemctl list-units --type=service --state=running 2>/dev/null | grep -iE 'snhgn|caddy|cloud|docker|ai-service|wifi' || echo "无匹配"
echo

echo "===== 10. Git 检查 ====="
which git && git --version
echo "--- /opt/snhgn 是否有 git ---"
[ -d /opt/snhgn/.git ] && echo "是" || echo "否"
echo

echo "===== 11. Caddy 配置位置 ====="
find /opt -name "Caddyfile" 2>/dev/null
docker exec caddy cat /etc/caddy/Caddyfile 2>/dev/null | head -30 || echo "无法读取 Caddyfile"
echo

echo "===== 12. AI Service 配置（不显示密钥） ====="
[ -f /opt/ai-service/.env ] && grep -vE 'KEY|SECRET|PASSWORD|TOKEN' /opt/ai-service/.env || echo "/opt/ai-service/.env 不存在"
echo

echo "===== 检查完成 ====="
