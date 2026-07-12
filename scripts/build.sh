#!/bin/bash
#
# 构建部署脚本 - 在服务器上执行
# 用法:
#   手动执行: /home/a/build.sh
#   Webhook 触发: GIT_PULL=1 /home/a/build.sh
#
# 流程:
#   1. (可选) Git Pull 拉取最新代码
#   2. npm install 安装依赖
#   3. npm run build 构建静态站点
#   4. 部署 dist 到 Nginx web 目录
#

set -e

# === 配置 ===
PROJECT_DIR="/home/a/snhgn.me"
WEB_DIR="/home/a/web"
NODE_BIN="/usr/local/bin/node"
NPM_BIN="/usr/local/bin/npm"
LOG_FILE="/home/a/build.log"

echo "[$(date)] Build started" | tee -a "$LOG_FILE"

cd "$PROJECT_DIR"

# === Step 1: Git Pull (可选) ===
if [ "$GIT_PULL" = "1" ]; then
  echo "[$(date)] Pulling latest code..." | tee -a "$LOG_FILE"
  git pull origin main 2>&1 | tee -a "$LOG_FILE"
fi

# === Step 2: Install dependencies ===
echo "[$(date)] Installing dependencies..." | tee -a "$LOG_FILE"
"$NPM_BIN" install --legacy-peer-deps 2>&1 | tee -a "$LOG_FILE"

# === Step 3: Build ===
echo "[$(date)] Building site..." | tee -a "$LOG_FILE"
"$NPM_BIN" run build 2>&1 | tee -a "$LOG_FILE"

# === Step 4: Deploy ===
echo "[$(date)] Deploying to $WEB_DIR..." | tee -a "$LOG_FILE"

# 备份旧文件
if [ -d "$WEB_DIR" ]; then
  rm -rf "${WEB_DIR}_old"
  cp -r "$WEB_DIR" "${WEB_DIR}_old"
fi

# 清空目标目录(保留 .gitkeep)
mkdir -p "$WEB_DIR"
find "$WEB_DIR" -mindepth 1 -delete

# 复制新文件
cp -r "$PROJECT_DIR/dist/"* "$WEB_DIR/"

echo "[$(date)] Build completed successfully!" | tee -a "$LOG_FILE"
echo "---" | tee -a "$LOG_FILE"
