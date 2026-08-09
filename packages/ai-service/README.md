# AI Service Layer

统一 AI 调用服务：默认调用智谱 GLM，失败自动切换 Google Gemini。

## 架构

```
网站 / 脚本
    │  POST /api/chat {"message": "你好"}
    ▼
AI Service Layer (FastAPI, :8000)
    │
    ├─ 主调用 GLM (zai-sdk, glm-4.7-flash) ──成功──► 返回 {"provider":"glm"}
    │      │失败(网络/API错误/超时/服务异常)
    │      ▼
    └─ 备用 Gemini (官方HTTP接口, gemini-flash-latest) ──成功──► 返回 {"provider":"gemini"}
               │失败
               ▼
          返回 {"success":false,"error":"All AI providers failed"}
```

## 目录结构

```
/opt/ai-service/
├── app/
│   ├── main.py            # FastAPI 入口，POST /api/chat
│   ├── config.py          # 配置（从 .env 读取）
│   └── providers/
│       ├── base.py        # Provider 抽象基类
│       ├── glm.py         # GLM（官方 zai-sdk）
│       └── gemini.py      # Gemini（官方 HTTP 接口）
├── requirements.txt
├── .env                   # 密钥（权限 600）
├── Dockerfile
└── docker-compose.yml
```

## API 调用示例

```bash
curl -X POST http://192.168.50.2:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}'
```

成功响应：

```json
{"success": true, "provider": "glm", "answer": "你好！有什么可以帮您？"}
```

失败响应（两个 Provider 都失败）：

```json
{"success": false, "provider": null, "answer": null, "error": "All AI providers failed, please retry later."}
```

健康检查：

```bash
curl http://192.168.50.2:8000/health
# {"status":"ok","providers":["glm","gemini"]}
```

## 配置密钥

编辑 `/opt/ai-service/.env`（需要 sudo）：

```
GLM_API_KEY=你的智谱Key
GEMINI_API_KEY=你的GeminiKey
SILICONFLOW_API_KEY=你的硅基流动Key   # 必填：翻译/总结走这里
```

可选参数（仅可调用以下白名单模型，默认选最新）：

```
GLM_TEXT_MODEL=glm-4.7-flash                  # 文本（最新）
GLM_TEXT_FALLBACK_MODEL=glm-4-flash-250414    # 文本备选
GLM_VISION_MODEL=glm-4.6v-flash               # 视觉（最新）
GLM_VISION_THINK_MODEL=glm-4.1v-thinking-flash # 视觉思考型
GLM_VISION_FALLBACK_MODEL=glm-4v-flash        # 视觉备选
GLM_IMAGE_MODEL=cogview-3-flash               # 图片生成
GLM_IMAGE_SIZE=1024x1024
GEMINI_MODEL=gemini-flash-latest
GEMINI_ENABLED=false     # 默认 false：关闭 Gemini（国内无法直连 Google API，避免超时等待）
                        # 有代理能访问 Google 时改为 true 启用备用
# 硅基流动专用任务（默认值，可覆盖）
# SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
# HUNYUAN_TRANSLATE_MODEL=tencent/Hunyuan-MT-7B   # 翻译模型
# QWEN_SUMMARY_MODEL=Qwen/Qwen3-8B                # 对话总结模型
REQUEST_TIMEOUT=120
```

修改后重启（注意：改了 `.env` 必须用 `--force-recreate` 重建容器才会生效）：

```bash
cd /opt/ai-service
sudo docker compose up -d --force-recreate
```

## Docker 管理命令

```bash
# 启动/重启/停止
sudo docker compose -f /opt/ai-service/docker-compose.yml up -d
sudo docker compose -f /opt/ai-service/docker-compose.yml restart
sudo docker compose -f /opt/ai-service/docker-compose.yml down

# 查看状态
docker ps | grep ai-service

# 查看日志
docker logs -f ai-service

# 重新构建（代码或依赖变更后）
cd /opt/ai-service
sudo docker compose up -d --build
```

开机自启已由 `restart: unless-stopped` 保证，无需额外配置。

## 日志查看

```bash
docker logs -f ai-service          # 实时日志
docker logs --tail 100 ai-service  # 最近 100 行
```

日志会记录：调用 Provider、耗时、失败原因（不包含 API Key）。

## 接入 Vue 网站

前端 Vite 已配置 `/api` 代理（见 `vite.config.ts`），可这样调用：

```ts
const res = await fetch("/api/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: "你好" }),
});
const data = await res.json();
console.log(data.provider, data.answer); // "glm" / "gemini"
```

生产环境（Caddy 托管静态站）如需同域调用，需在 Caddy 加反向代理：

```
snhgn.me {
    handle /api/* {
        reverse_proxy localhost:8000
    }
    ...
}
```

（目前 AI 服务仅监听 8000 端口，未暴露公网，按需决定是否开放。）
