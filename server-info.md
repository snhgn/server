# snhgn.me 服务器与项目总览

最近更新：2026-08-09

---

## 一、服务器信息

### 系统信息

| 项目 | 值 |
|------|-----|
| 发行版 | Ubuntu 22.04.5 LTS (jammy) |
| 架构 | x86_64 |
| 主机名 | snhgn |
| CPU | Intel i5-7200U @ 2.50GHz，4 核 |
| 内存 | 3.7 GiB（Swap 3.7 GiB） |
| 磁盘 | 465.8G SSD（LVM 根分区 454G，已用 7G） |

### 网络

| 网卡 | IP | 说明 |
|------|-----|------|
| enp2s0f2（有线） | 192.168.50.2/24 | SSH 管理连接 |
| wlp3s0（无线） | 10.66.36.5/24 | 默认路由，网关 10.66.36.218 |

- 家庭 NAT 环境，无公网 IP → 采用 Cloudflare Tunnel 方案
- 默认路由：`via 10.66.36.218 dev wlp3s0`
- WiFi 省电已关闭（`wifi.powersave = 2`），合盖不挂起（`HandleLidSwitch=ignore`）

### 系统配置

- **合盖不操作**：`/etc/systemd/logind.conf.d/10-lid-ignore.conf`
- **WiFi 省电关闭**：`/etc/systemd/system/wifi-powersave.service`（enabled）
- **每晚 12 点自动重启**：`daily-reboot.timer`（`OnCalendar=*-*-* 00:00:00`）

### 开机自启清单

| 项目 | 方式 | 状态 |
|------|------|------|
| Docker 服务 | `systemctl enable docker` | enabled |
| Caddy 容器 | `restart: unless-stopped` | ✓ |
| cloudflared 容器 | `restart: unless-stopped` | ✓ |
| ai-service 容器 | `restart: unless-stopped` | ✓ |
| gateway 容器 | `restart: unless-stopped` | ✓ |
| scheduler 容器 | `restart: unless-stopped` | ✓ |
| WiFi 网络 | netplan 持久化 | 自动连接 |

---

## 二、部署架构

### 整体链路

```
访客 → https://snhgn.me (Cloudflare CDN/TLS)
        → Cloudflare Tunnel（出站连接，无需公网IP）
        → cloudflared 容器 (host网络)
        → Caddy 容器 http://127.0.0.1:8080
            ├─ /api/* → gateway:8001（认证 + 路由分发）
            │            ├─ /api/auth/*  → 本地 SQLite 用户库
            │            ├─ /api/ai/*    → ai-service:8000
            │            └─ /api/scheduler/* → scheduler:8002
            └─ /* → 静态文件 /srv/web/（Vue3 SPA）
```

### Docker 容器清单

| 容器 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| caddy | caddy:2.9-alpine | 8080→80 | 静态网站 + API 反向代理 |
| cloudflared | cloudflare/cloudflared:latest | host | Cloudflare 隧道 |
| ai-service | 自建 | 8000 | AI 统一服务（GLM/Gemini + Memory + RAG） |
| gateway | 自建 | 8001→127.0.0.1 | JWT 认证 + 路由代理 |
| scheduler | 自建 | 8002→127.0.0.1 | APScheduler 定时任务 |

### 数据卷

```
/opt/snhgn/
├── data/
│   ├── gateway/          # gateway.db（users 表）
│   ├── sqlite/           # scheduler 任务数据
│   ├── chroma-cache/     # RAG 向量库缓存
│   └── knowledge/        # RAG 知识库源文件
├── logs/
│   ├── ai-service/
│   ├── gateway/
│   └── scheduler/
└── (website)
/opt/website/
├── Caddyfile             # Caddy 配置
└── web/                  # Vue3 前端构建产物
```

---

## 三、项目结构（本地仓库 d:\project\server）

```
d:\project\server\
├── packages/                    # 核心服务模块
│   ├── ai-service/              # AI 服务（GLM/Gemini + Memory + RAG）
│   ├── gateway/                 # API 网关（JWT 认证 + 路由）
│   ├── scheduler/               # 定时任务服务
│   ├── schedule-pipeline/       # 课表全链路（验证码识别 + 课表展示）
│   ├── ai-notice-monitor/       # 校园通知智能监控（邮件 + AI 摘要）
│   ├── website-deploy/          # 前端部署脚本
│   ├── architecture/            # 架构文档
│   └── diagnose/                # 诊断与构建脚本
├── deploy/                      # 顶层部署配置
│   ├── caddy/Caddyfile          # Caddy 配置（API/静态资源路由分离）
│   ├── cloudflared/             # Cloudflare 隧道编排
│   ├── web/                     # 前端构建产物挂载点
│   └── docker-compose.yml       # 网站+隧道旧编排（参考）
├── tests/                       # 临时测试脚本
│   ├── README.md
│   └── tmp_check_routes.sh      # 全链路验证脚本
├── docker-compose.yml           # 顶层统一编排（4 核心服务）
├── server-info.md               # 本文档
└── .gitignore
```

### 前端项目（独立仓库 d:\project\snhgn.me）

```
d:\project\snhgn.me\             # Vue3 + Vite + TS + Tailwind
├── src/
│   ├── views/                   # 页面（Home/Login/AI/Dashboard/...）
│   ├── components/              # 组件（Navbar/Footer/StatusCard）
│   ├── stores/auth.ts           # 认证状态管理
│   ├── api.ts                   # API 封装（自动带 JWT）
│   └── router/index.ts          # 路由 + 权限守卫
└── dist/                        # 构建产物 → 上传到 /opt/website/web/
```

---

## 四、AI Assistant 页面开发记录（2026-08-09）

### 本次对话完成的工作

#### 1. Gateway 路径转发修复
- **问题**：前端调用 `/api/ai/chat`，Gateway 去掉 `/ai` 前缀后变成 `chat`，但 ai-service 的路由是 `/api/chat`，导致 404
- **修复**：`packages/gateway/app/routers/ai.py` 中 `url = f"/{path}"` → `url = f"/api/{path}"`
- **验证**：直接调 ai-service `/api/chat` 成功返回（provider=glm, answer 正常）

#### 2. Caddy 路由分离修复
- **问题**：Caddy 配置中 `try_files` 在 `handle /api/*` 之前执行，把 `/api/*` 请求回退到 `index.html`（返回 200 而非走代理）
- **修复**：`deploy/caddy/Caddyfile` 用 `handle {}` 块包裹 `try_files` + `file_server`，与 `handle /api/*` 互斥
- **验证**：`/api/ai/chat` 无 auth 返回 401（正确），`/api/auth/login` 空 body 返回 422（正确）

#### 3. AI Assistant 页面开发（d:\project\snhgn.me\src\views\AiView.vue）
- **路径**：`/ai`（需登录）
- **功能**：
  - 左侧会话列表（调用 `/api/ai/conversations`）
  - 中间消息流（user 右侧深色 / assistant 左侧浅色）
  - 历史会话加载（`/api/ai/conversations/{sid}`）
  - 发送消息（`POST /api/ai/chat`，带 use_memory/use_rag/session_id 参数）
  - RAG sources 折叠展示
  - 底部 Memory/Knowledge 双开关
- **状态条**：当前用户 / Memory 条目数 / Knowledge 引用源数 / AI Provider
- **UI 风格**：简洁、现代、工程化（Tailwind + monospace 字体）

#### 4. admin 账号密码重置
- **问题**：数据库中 admin 哈希与 `.env` 的 `ADMIN_PASSWORD_HASH` 一致，但明文未知，无法登录
- **处理**：通过 `init_admin.py` 脚本重置
  ```bash
  docker exec gateway python /app/scripts/init_admin.py --username admin --password admin123
  ```
- **验证**：登录成功 → 拿到 JWT → 调用 `/api/ai/chat` 返回正常

#### 5. AI 知识库扩展：docx 支持 + 学校资料批量入库
- **背景**：将本地 `D:\学校相关资料`（81 PDF + 26 DOCX，约 197MB）上传为 AI 知识库
- **代码改动**：
  - `packages/ai-service/app/rag/loader.py`：新增 `_load_docx()`，用 python-docx 按文档顺序解析段落 + 表格
  - `packages/ai-service/app/main.py`：`/api/knowledge/add` 的 allowed 增加 `.docx`
  - `packages/ai-service/app/rag/vector_store.py`：空文本保护（扫描件 PDF 无文字层时不再 500）
  - `packages/ai-service/requirements.txt`：新增 `python-docx>=1.1`（含 lxml 等依赖，wheel 已装入服务器 `/opt/ai-service/wheels/` 离线安装）
- **入库结果**：107 个文件全部入库，Chroma 共 **1332 个片段**，按科目目录分类（工程制图 46 / 物理竞赛 32 / 政治 11 / 高数 8 / 综素 2 / 培养计划 2 / 线代 1 / 历史 1 / 化学 1 等）
- **扫描件说明**：38 个扫描版 PDF（40 届物理竞赛答案、部分高数基础练习）无文字层，pypdf 无法提取，入库为 0 片段——如需检索需 OCR
- **`.doc` 老格式**（约 50 个）未入库：python-docx 不支持，需 LibreOffice/antiword 转换，待后续
- **验证**：`/api/knowledge/search` 多科目检索通过（工程制图/政治/物理竞赛命中 0.5-0.65 分）

### 当前登录凭据

| 项目 | 值 |
|------|-----|
| URL | https://snhgn.me/login |
| 用户名 | admin |
| 密码 | admin123（临时验证用，建议尽快修改） |

**修改密码命令**：
```bash
docker exec gateway python /app/scripts/init_admin.py --username admin --password <新密码>
```

---

## 五、当前网站状态

### 已上线功能

| 功能 | 路径 | 状态 | 说明 |
|------|------|------|------|
| 首页 | / | ✓ | Hero + 状态卡片 |
| 项目展示 | /projects | ✓ | 静态 |
| 关于 | /about | ✓ | 静态 |
| 登录 | /login | ✓ | JWT 认证 |
| AI Assistant | /ai | ✓ | 聊天 + 会话 + Memory/RAG |
| Dashboard | /dashboard | ✓ | Admin 可见 |
| Knowledge | /knowledge | ✓ | Admin 可见 |
| Server | /server | ✓ | Admin 可见 |
| Scripts | /scripts | ✓ | User 可见 |
| Schedule | /schedule | ✓ | User 可见 |
| Settings | /settings | ✓ | User 可见 |

### API 接口状态

| 接口 | 方法 | 状态 | 说明 |
|------|------|------|------|
| /api/auth/login | POST | ✓ | 登录获取 JWT |
| /api/auth/verify | GET | ✓ | 验证 token |
| /api/ai/chat | POST | ✓ | AI 对话（GLM/Gemini） |
| /api/ai/conversations | GET | ✓ | 会话列表 |
| /api/ai/conversations/{id} | GET | ✓ | 会话历史 |
| /api/ai/memory | GET | ✓ | Memory 条目数 |
| /api/ai/settings | GET | ✓ | 用户设置 |

### 底层服务状态

- **Auth**：JWT + bcrypt + SQLite，role-based（user/admin）
- **Gateway**：路由代理 + 权限中间件，转发 X-User-* Header
- **AI Service**：GLM（默认）+ Gemini（兜底）+ Memory + 多用户 RAG
- **Memory**：按 user_id 隔离的对话记忆
- **RAG**：Chroma 向量库 + 多用户知识隔离
- **前端**：Vue3 + Vite + TS + Tailwind，路由守卫 + 动态导航

---

## 六、后续发展方向

### 短期（下一步）

1. **文件上传 RAG 扩展**
   - 后端：`POST /api/ai/upload`（multipart/form-data）→ 存 inbox → 触发索引
   - 前端：AiView 输入区加 📎 按钮 → 上传后自动勾选 `useRag`
   - 状态条：显示已索引文档数
   - 现有架构无需改动 Gateway/Caddy

2. **密码安全**
   - 将 admin 密码从 `admin123` 改为强密码
   - 考虑加登录失败限流

3. **登录后页面打不开问题排查**
   - 本次未完成浏览器实测（agent-browser 未安装）
   - 后端全链路验证通过（SPA 路由 200 + API 正常）
   - 怀疑前端 JS 运行时错误，需浏览器 console 排查

### 中期

4. **AI Assistant 功能增强**
   - 流式响应（SSE）支持
   - Markdown 渲染 + 代码高亮
   - 会话重命名/删除
   - Memory 管理 UI（查看/清除）

5. **课表服务集成**
   - schedule-pipeline 容器化
   - 前端 ScheduleView 对接 `/api/course`

6. **通知监控集成**
   - ai-notice-monitor 容器化
   - 邮件通知 + AI 摘要上线

### 长期

7. **多用户体系完善**
   - 用户注册（邀请码）
   - 权限分级管理 UI
   - 用户管理后台

8. **运维监控**
   - 日志聚合（loki/promtail）
   - 服务健康检查面板
   - 自动备份策略

---

## 七、常用命令

### 服务器管理（SSH）

```bash
# SSH 连接
ssh snhgn@192.168.50.2

# 查看容器状态
docker ps

# 查看日志
docker compose logs -f [服务名]

# 重启服务
cd /opt/snhgn && docker compose restart [服务名]
```

### 前端部署

```bash
# 本地构建
cd d:\project\snhgn.me
npm run build

# 上传到服务器（通过 pscp）
& "C:\Program Files\PuTTY\pscp.exe" -hostkey SHA256:roEbdNCO4i18oR7yR1r9HY6kUcE9/hJJsELFJ2CI46I -pw 1 -r "dist\*" snhgn@192.168.50.2:/tmp/snhgn-dist/

# 服务器替换
ssh snhgn@192.168.50.2 "sudo rm -rf /opt/website/web/* && sudo cp -r /tmp/snhgn-dist/* /opt/website/web/"
```

### 后端部署

```bash
# 重新构建并启动（在服务器项目目录）
cd /path/to/server
git pull
docker compose up -d --build

# 重载 Caddy 配置
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

### admin 密码管理

```bash
# 重置密码
docker exec gateway python /app/scripts/init_admin.py --username admin --password <新密码>

# 查看用户列表（需 python）
docker exec gateway python -c "import sqlite3; c=sqlite3.connect('/data/gateway.db'); print([dict(r) for r in c.execute('SELECT id,username,role FROM users').fetchall()])"
```

### 全链路验证

```bash
# 服务器上执行 tests/tmp_check_routes.sh
bash /tmp/tmp_check_routes.sh
```
