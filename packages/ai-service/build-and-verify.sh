#!/bin/bash
# AI Service v2.0 构建 + 验证脚本
# 用法：sudo bash /tmp/build-and-verify.sh
# 结果输出到 /tmp/build-result.log

LOG=/tmp/build-result.log
echo "=== AI Service v2.0 构建验证 ===" > $LOG
echo "时间: $(date)" >> $LOG
echo "" >> $LOG

# 1. 构建
echo ">>> [1/6] 构建 Docker 镜像..." >> $LOG
cd /opt/ai-service
DOCKER_BUILDKIT=0 docker compose up -d --build >> $LOG 2>&1
BUILD_EXIT=$?
echo "构建退出码: $BUILD_EXIT" >> $LOG

if [ $BUILD_EXIT -ne 0 ]; then
    echo "构建失败！查看上方日志。" >> $LOG
    exit 1
fi

echo "" >> $LOG
echo ">>> [2/6] 等待容器启动..." >> $LOG
sleep 5
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' >> $LOG 2>&1
echo "" >> $LOG

# 2. Health 检查
echo ">>> [3/6] Health 检查..." >> $LOG
curl -s -m 10 http://localhost:8000/health >> $LOG 2>&1
echo "" >> $LOG

# 3. Memory 测试
echo "" >> $LOG
echo ">>> [4/6] 长期记忆测试..." >> $LOG
echo "--- 添加记忆 ---" >> $LOG
curl -s -m 10 -X POST http://localhost:8000/api/memory \
    -H 'Content-Type: application/json' \
    -d '{"category":"user","key":"name","value":"snhgn"}' >> $LOG 2>&1
echo "" >> $LOG
echo "--- 查看记忆 ---" >> $LOG
curl -s -m 10 http://localhost:8000/api/memory >> $LOG 2>&1
echo "" >> $LOG

# 4. 知识库测试（首次会下载 ONNX 模型，可能需要 1-2 分钟）
echo "" >> $LOG
echo ">>> [5/6] RAG 知识库测试（首次加载模型可能需要 1-2 分钟）..." >> $LOG

# 创建测试文件
echo "Docker 是一个开源的容器化平台，允许开发者将应用及其依赖打包到轻量级容器中。Docker 使用 Linux 内核的 cgroup 和 namespace 功能来隔离进程。" > /tmp/test-knowledge.md

echo "--- 上传知识文件 ---" >> $LOG
curl -s -m 120 -X POST http://localhost:8000/api/knowledge/add \
    -F 'file=@/tmp/test-knowledge.md' \
    -F 'category=server' >> $LOG 2>&1
echo "" >> $LOG

echo "--- 知识检索测试 ---" >> $LOG
curl -s -m 60 "http://localhost:8000/api/knowledge/search?query=Docker%E6%98%AF%E4%BB%80%E4%B9%88&top_k=3" >> $LOG 2>&1
echo "" >> $LOG

# 5. 增强对话测试
echo "" >> $LOG
echo ">>> [6/6] 增强对话测试（use_memory + use_rag）..." >> $LOG
curl -s -m 130 -X POST http://localhost:8000/api/chat \
    -H 'Content-Type: application/json' \
    -d '{"message":"Docker是什么？","use_memory":true,"use_rag":true}' >> $LOG 2>&1
echo "" >> $LOG

# 清理
rm -f /tmp/test-knowledge.md

echo "" >> $LOG
echo "=== 验证完成 ===" >> $LOG
echo "时间: $(date)" >> $LOG
echo "" >> $LOG
echo "完整构建日志: /tmp/build.log" >> $LOG
echo "验证结果日志: /tmp/build-result.log" >> $LOG

echo ""
echo "===== 验证结果 ====="
cat $LOG
