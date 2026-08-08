#!/bin/bash
# AI Service v2.0 构建+验证（离线 pip 安装版）
cd /opt/ai-service

echo "=== [1/6] 构建镜像 ==="
DOCKER_BUILDKIT=0 docker compose up -d --build 2>&1
BUILD_EXIT=$?
echo "构建退出码: $BUILD_EXIT"

if [ $BUILD_EXIT -ne 0 ]; then
    echo "构建失败"
    exit 1
fi

echo "=== [2/6] 等待启动 ==="
sleep 5
docker ps --format 'table {{.Names}}\t{{.Status}}'

echo "=== [3/6] Health ==="
curl -s -m 10 http://localhost:8000/health
echo

echo "=== [4/6] Memory 测试 ==="
curl -s -m 10 -X POST http://localhost:8000/api/memory \
    -H 'Content-Type: application/json' \
    -d '{"category":"user","key":"name","value":"snhgn"}'
echo
curl -s -m 10 http://localhost:8000/api/memory
echo

echo "=== [5/6] RAG 测试（首次加载模型 1-2 分钟）==="
echo "Docker 是一个开源的容器化平台，允许开发者将应用及其依赖打包到轻量级容器中。Docker 使用 Linux 内核的 cgroup 和 namespace 功能来隔离进程。" > /tmp/test-knowledge.md

curl -s -m 180 -X POST http://localhost:8000/api/knowledge/add \
    -F 'file=@/tmp/test-knowledge.md' \
    -F 'category=server'
echo

curl -s -m 60 "http://localhost:8000/api/knowledge/search?query=Docker&top_k=3"
echo

echo "=== [6/6] 增强对话 ==="
curl -s -m 130 -X POST http://localhost:8000/api/chat \
    -H 'Content-Type: application/json' \
    -d '{"message":"Docker是什么？","use_memory":true,"use_rag":true}'
echo

rm -f /tmp/test-knowledge.md
echo "=== 完成: $(date) ==="
