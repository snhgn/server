#!/bin/bash
#
# 一键部署脚本 - 在服务器上以 sudo 执行
# 用法: sudo bash /home/a/snhgn.me/scripts/setup-nginx.sh
#

set -e

PROJECT_DIR="/home/a/snhgn.me"
WEB_DIR="/opt/1panel/apps/openresty/openresty/www/sites/snhgn.me/index"
NGINX_CONF="/opt/1panel/apps/openresty/openresty/conf/conf.d/snhgn.me.conf"
CONF_SOURCE="$PROJECT_DIR/snhgn.me.conf"

echo "=== 1. 部署静态文件 ==="

# 检查构建产物
if [ ! -d "$PROJECT_DIR/dist/client" ] && [ ! -d "$PROJECT_DIR/dist" ]; then
  echo "错误: 未找到构建产物,请先执行 npm run build"
  exit 1
fi

# 确定 dist 目录
if [ -d "$PROJECT_DIR/dist/client" ]; then
  DIST_DIR="$PROJECT_DIR/dist/client"
else
  DIST_DIR="$PROJECT_DIR/dist"
fi

echo "源: $DIST_DIR"
echo "目标: $WEB_DIR"

# 清空旧文件
echo "清空旧文件..."
rm -rf "$WEB_DIR"/*
mkdir -p "$WEB_DIR"

# 复制构建产物
echo "复制构建产物..."
cp -r "$DIST_DIR"/* "$WEB_DIR/"

# 设置权限
echo "设置权限..."
chown -R 1000:1000 "$WEB_DIR"
chmod -R 755 "$WEB_DIR"

echo "=== 2. 更新 Nginx 配置 ==="

# 备份旧配置
if [ -f "$NGINX_CONF" ]; then
  cp "$NGINX_CONF" "${NGINX_CONF}.bak.$(date +%s)"
  echo "已备份旧配置"
fi

# 复制新配置
cp "$CONF_SOURCE" "$NGINX_CONF"
echo "已更新 Nginx 配置"

# 验证配置
echo "=== 3. 验证 Nginx 配置 ==="
if docker exec openresty nginx -t 2>&1; then
  echo "配置验证通过"
else
  echo "配置验证失败,请检查配置文件"
  exit 1
fi

# 重载 Nginx
echo "=== 4. 重载 Nginx ==="
docker exec openresty nginx -s reload
echo "Nginx 已重载"

# 检查 Node.js 服务
echo "=== 5. 检查 Node.js 服务 ==="
if command -v pm2 &> /dev/null; then
  PM2_STATUS=$(pm2 list 2>/dev/null | grep snhgn-me || echo "")
  if [ -z "$PM2_STATUS" ]; then
    echo "启动 Node.js 服务..."
    cd "$PROJECT_DIR"
    pm2 start ecosystem.config.cjs
    pm2 save
  else
    echo "Node.js 服务已在运行"
  fi
else
  echo "警告: PM2 未安装,请执行 npm install -g pm2"
fi

echo ""
echo "=== 部署完成 ==="
echo "网站: http://192.168.1.43/"
echo "Admin: http://192.168.1.43/keystatic/"
echo ""
echo "验证命令:"
echo "  curl -I http://192.168.1.43/"
echo "  curl -I http://192.168.1.43/keystatic/"
