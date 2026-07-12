#!/bin/bash
#
# 部署脚本 - 在服务器上执行
# 用法: ssh a@192.168.1.43 'bash -s' < scripts/deploy.sh
#
# 前提: 代码已推送到 GitHub
#

set -e

PROJECT_DIR="/home/a/snhgn.me"
WEB_DIR="/home/a/web"
CONF_FILE="/home/a/snhgn.me/snhgn.me.conf"

echo "=== Deploying snhgn.me ==="

# === Step 1: Clone or pull project ===
if [ -d "$PROJECT_DIR/.git" ]; then
  echo ">>> Pulling latest code..."
  cd "$PROJECT_DIR"
  git pull origin main
else
  echo ">>> Cloning repository..."
  git clone https://github.com/snhgn/snhgn.me.git "$PROJECT_DIR"
  cd "$PROJECT_DIR"
fi

# === Step 2: Install dependencies ===
echo ">>> Installing dependencies..."
npm install --legacy-peer-deps

# === Step 3: Build ===
echo ">>> Building site..."
npm run build

# === Step 4: Deploy static files ===
echo ">>> Deploying static files..."
mkdir -p "$WEB_DIR"
find "$WEB_DIR" -mindepth 1 -delete
cp -r dist/client/* "$WEB_DIR/" 2>/dev/null || cp -r dist/* "$WEB_DIR/"

# === Step 5: Setup environment ===
echo ">>> Setting up environment..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
  echo "Warning: .env file not found. Copy from .env.example and fill in values."
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  echo ">>> Edit $PROJECT_DIR/.env with your OAuth credentials"
fi

# === Step 6: Start/restart Node.js server ===
echo ">>> Starting Node.js server with PM2..."
if command -v pm2 &> /dev/null; then
  pm2 delete snhgn-me 2>/dev/null || true
  pm2 start "$PROJECT_DIR/ecosystem.config.cjs"
  pm2 save
else
  echo "PM2 not found. Install with: npm install -g pm2"
  echo "Then run: pm2 start $PROJECT_DIR/ecosystem.config.cjs"
fi

# === Step 7: Configure Nginx ===
echo ">>> Configuring Nginx..."
if [ -d "/www/sites/snhgn.me" ]; then
  # 1Panel structure
  cp "$CONF_FILE" "/www/sites/snhgn.me/proxy/sniggn.me.conf"
  docker exec openresty nginx -s reload 2>/dev/null || true
elif [ -d "/etc/nginx/conf.d" ]; then
  cp "$CONF_FILE" "/etc/nginx/conf.d/snhgn.me.conf"
  nginx -s reload 2>/dev/null || systemctl reload nginx
fi

echo "=== Deployment complete! ==="
echo "Site: http://192.168.1.43"
echo "Admin: http://192.168.1.43/keystatic/"
