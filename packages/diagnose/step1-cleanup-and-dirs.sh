#!/bin/bash
# 第一步：清理残留容器 + 整理目录结构
# 原则：不删除现有文件，不移动现有数据，只建新目录和软链接

set -e

echo "===== [1] 清理残留容器 ====="
docker rm -f thirsty_shamir 2>/dev/null && echo "已删除 thirsty_shamir" || echo "thirsty_shamir 不存在或已删除"
# 清理悬空镜像
docker image prune -f 2>/dev/null | tail -1
echo

echo "===== [2] 创建目录结构 ====="
# 服务目录
mkdir -p /opt/snhgn/services/gateway
mkdir -p /opt/snhgn/services/scheduler
mkdir -p /opt/snhgn/services/website

# 数据目录
mkdir -p /opt/snhgn/data/sqlite
mkdir -p /opt/snhgn/data/vector
# knowledge 目录已存在，保留

# 配置目录
mkdir -p /opt/snhgn/config

# 日志目录
mkdir -p /opt/snhgn/logs/gateway
mkdir -p /opt/snhgn/logs/ai
mkdir -p /opt/snhgn/logs/scheduler
mkdir -p /opt/snhgn/logs/website

# 脚本目录
mkdir -p /opt/snhgn/scripts

# 备份目录
mkdir -p /opt/snhgn/backups
echo "新目录创建完成"
echo

echo "===== [3] 创建软链接（统一服务入口）====="
# ai-service 保持原位，通过软链接纳入规范
if [ ! -L /opt/snhgn/services/ai-service ]; then
    ln -s /opt/ai-service /opt/snhgn/services/ai-service
    echo "已创建软链接: /opt/snhgn/services/ai-service -> /opt/ai-service"
else
    echo "软链接已存在: /opt/snhgn/services/ai-service"
fi

# website 软链接
if [ ! -L /opt/snhgn/services/website ]; then
    rm -rf /opt/snhgn/services/website  # 删除刚才建的空目录
    ln -s /opt/website /opt/snhgn/services/website
    echo "已创建软链接: /opt/snhgn/services/website -> /opt/website"
else
    echo "软链接已存在: /opt/snhgn/services/website"
fi
echo

echo "===== [4] 检查 knowledge 目录重复 ====="
# 检查 /opt/snhgn/data/knowledge 是否为空
if [ -d /opt/snhgn/data/knowledge ]; then
    K_COUNT=$(find /opt/snhgn/data/knowledge -type f 2>/dev/null | wc -l)
    if [ "$K_COUNT" -eq 0 ]; then
        rmdir /opt/snhgn/data/knowledge 2>/dev/null && echo "已删除空目录 /opt/snhgn/data/knowledge" || echo "保留 /opt/snhgn/data/knowledge（非空或无法删除）"
    else
        echo "/opt/snhgn/data/knowledge 有 $K_COUNT 个文件，保留不动"
    fi
fi
echo "说明：知识文件统一使用 /opt/snhgn/knowledge/（ai-service 挂载的目录）"
echo

echo "===== [5] 创建 .gitignore ====="
cat > /opt/snhgn/.gitignore <<'EOF'
# 敏感配置
config/.env
**/.env
*.env

# 密钥
*.key
*.pem
*.p12

# 数据库与数据
data/sqlite/*.db
data/sqlite/*.db-journal
data/vector/
data/chroma/
data/chroma-cache/

# 日志
logs/
*.log

# 备份
backups/

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/

# Docker 持久化卷
**/wheels/

# IDE
.vscode/
.idea/
*.swp
EOF
echo ".gitignore 已创建"
echo

echo "===== [6] 创建配置模板 .env.example ====="
cat > /opt/snhgn/config/.env.example <<'EOF'
# ===== Personal Platform 配置模板 =====
# 复制为 .env 并填写实际值

# --- 认证 ---
# bcrypt 哈希后的密码（用 python -c "import bcrypt;print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())" 生成）
ADMIN_PASSWORD_HASH=
# JWT 签名密钥（用 python -c "import secrets;print(secrets.token_hex(32))" 生成）
JWT_SECRET=
# Token 有效期（小时）
JWT_EXPIRE_HOURS=24

# --- AI Service ---
GLM_API_KEY=
GEMINI_API_KEY=
GEMINI_ENABLED=false
GEMINI_MODEL=gemini-3.6-flash
GLM_MODEL=glm-4.7-flash
REQUEST_TIMEOUT=120

# --- 数据库路径 ---
SQLITE_DB_PATH=/data/sqlite/memory.db
CHROMA_PERSIST_DIR=/data/vector
KNOWLEDGE_BASE_DIR=/data/knowledge

# --- 服务端口（内部）---
GATEWAY_PORT=8001
AI_SERVICE_PORT=8000
SCHEDULER_PORT=8002

# --- HuggingFace 镜像（国内加速）---
HF_ENDPOINT=https://hf-mirror.com
EOF
echo ".env.example 已创建"
echo

echo "===== [7] 验证最终结构 ====="
echo "--- /opt/snhgn 目录树 ---"
find /opt/snhgn -maxdepth 3 -not -path '*/chroma/*' -not -path '*/chroma-cache/*' -not -path '*/knowledge/*' | sort
echo
echo "--- 软链接验证 ---"
ls -la /opt/snhgn/services/
echo
echo "===== 第一步完成 ====="
