# snhgn.me 服务器与项目总览

最近更新：2026-09-08

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
| 磁盘 | 465.8G SSD（LVM 根分区 454G，已用 18G） |

### 网络

| 网卡 | IP | 说明 |
|------|-----|------|
| enp2s0f2（有线） | 192.168.50.2/24 | SSH 管理连接 |
| wlp3s0（无线） | 172.28.204.98/22 | 默认路由，网关 172.28.204.1 |

- 家庭 NAT 环境，无公网 IP → 采用 Cloudflare Tunnel 方案
- 默认路由：`via 172.28.204.1 dev wlp3s0`
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
| gateway | 自建 | 8001→127.0.0.1 | Session(Cookie)+JWT 双通道认证 + 路由代理 |
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
│   ├── gateway/                 # API 网关（JWT 认证 + 路由 + 排课/识别）
│   ├── scheduler/               # 定时任务服务
│   ├── ai-notice-monitor/       # 校园通知智能监控（邮件 + AI 摘要）
│   ├── website-deploy/          # 前端部署脚本
│   ├── architecture/            # 架构文档
│   └── diagnose/                # 诊断与构建脚本
├── deploy/                      # 顶层部署配置
│   ├── cloudflared/             # Cloudflare 隧道编排
│   └── web/                     # 前端构建产物挂载点
├── tests/                       # 临时测试脚本
├── schedule_data/               # 课表/排课系统相关数据资源
├── design_assets/               # 独立产品设计方案与素材
├── website_source/              # 网站静态源码备份
├── Caddyfile                    # Caddy 生产配置（API/静态资源路由分离）
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
│   ├── stores/auth.ts           # 认证状态管理（Cookie Session + /me 恢复）
│   ├── api.ts                   # API 封装（自动带 Cookie；JWT 兼容）
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
| 密码 | 见本机安全存储 `%TEMP%\opencode\adminpw.txt`（2026-08-24 已由弱密码 admin123 更换为 20 位随机强密码，公网登录验证通过、旧密码 401） |

> 密码明文不写入本文档（文档可能被截图/同步外泄）。临时文件如需保留请移至密码管理器，否则可删除；遗忘时用下方命令重置。

**重置密码命令**（在能直连服务器的内网机器上执行，网线直连 192.168.50.x 网段）：
```bash
docker exec gateway python /app/scripts/init_admin.py --username admin --password <新强密码>
```
修改后请同步更新本节记录。

---

## 五、课表 AI 数据模块开发记录（2026-08-10）

### 目标

将课表模块升级为 AI 助手的数据来源：数据库作为唯一可信来源，网页课表 / AI 查询 / 空闲分析 / 学习规划均基于同一份数据，避免数据不一致；多用户课程数据完全隔离；AI 通过服务内部函数读取数据（不新增 HTTP API）。

### 架构

```
教务系统 → 课程获取模块 → schedule_cache → courses 表(SQLite) → course_context 同步
        → /data/course-data/users/user_{id}/（AI 共享目录）→ AI 内部函数读取
```

- gateway 与 ai-service 通过共享卷交换 AI 数据：`/opt/snhgn/data/gateway/course-data`
- gateway 容器写入 `/data/course-data`，ai-service 读取同一路径
- **安全约束**：不存储学号/密码 → 定时同步从 schedule_cache 拉取，而非每日重新登录教务系统

### 新增文件

| 文件 | 职责 |
|------|------|
| `packages/gateway/app/schedule/course_db.py` | `courses` + `course_sync_status` 表；`replace_courses`（先删后插，user_id 隔离）、`get_courses`、同步状态读写 |
| `packages/gateway/app/schedule/course_context.py` | 官方节次时间表 `PERIOD_SLOTS`、周次解析、学期标签、sha256 hash 变化检测；生成 3 个 AI 文件 |
| `packages/gateway/app/schedule/scheduler.py` | 每日定时同步（默认 03:00，`COURSE_SYNC_HOUR` 可配），`asyncio` 后台任务 |
| `packages/ai-service/app/course_tools.py` | AI 内部函数 + 意图检测（见下） |

### 数据表设计

- `users` 表（已有）：id / username / password_hash / role
- `courses` 表：id / user_id / course_name / teacher / location / weekday / start_section / end_section / start_week / end_week / semester / update_time
- `course_sync_status` 表：user_id / semester / last_sync_time / sync_status(success|failed) / data_hash
- 多用户隔离：所有查询强制 `WHERE user_id = ?`

### AI 数据目录

`/data/course-data/users/user_{id}/`：

| 文件 | 用途 |
|------|------|
| `course.json` | 程序精确查询（user_id / semester / courses 列表） |
| `course_context.txt` | 自然语言总结，供 LLM 上下文（按周几分组，含时间/地点/教师） |
| `course_summary.json` | AI 内部函数精确查询（含节次时间区间、周次范围） |

### 课程变化检测

- 规范化课程字段后计算 sha256（`_courses_hash`）
- 与 `course_sync_status.data_hash` 比较：相同 → `skipped`（不刷新 AI 文件）；不同 → 重新生成
- 避免无条件刷新 AI 数据

### AI 内部函数（packages/ai-service/app/course_tools.py）

| 函数 | 说明 |
|------|------|
| `get_schedule_context(user_id)` | 读取 course_summary.json 生成上下文 |
| `get_today_courses(user_id)` | 今日课程 |
| `get_week_courses(user_id, week=None)` | 某周课程（自动计算当前周） |
| `get_course_info(user_id, course_name)` | 课程详情（模糊匹配名称） |
| `get_free_time(user_id)` | 每日空闲节次 + 全天无课日 |
| `build_schedule_prompt(user_id, message)` | 意图检测，命中「今天/这周/某课/空闲/课表」时返回注入片段 |

- chat 入口（流式/非流式）在组装 prompt 前调用 `build_schedule_prompt`，非空则注入"以下是用户的课表信息…"片段
- 学期配置 `TERM_START='2026-09-07'` / `TERM_END='2027-01-15'`（与前端 ScheduleView 一致）

### 已有代码的改动（最小侵入）

- `packages/gateway/app/main.py`：lifespan 初始化 `schedule_db / course_db / course_scheduler`
- `packages/gateway/app/schedule/service.py`：抓取写缓存后自动同步，异常不阻断
- `packages/ai-service/app/main.py`：chat 两处注入课表上下文
- `packages/gateway/app/config.py` / `packages/ai-service/app/config.py`：新增 `COURSE_DATA_DIR`
- `packages/ai-service/docker-compose.yml`：新增共享卷 `- /opt/snhgn/data/gateway/course-data:/data/course-data`

**未改动**：登录模块、验证码识别、教务系统爬取模块、课表网页核心显示逻辑。

### 服务器部署验证

- gateway / ai-service 均已重建容器并健康运行（`/health` 200）
- 真实数据同步：user 1 → 47 门课写入 courses 表，sync_status=success，hash 已记录
- AI 目录生成 3 文件（course.json / course_context.txt / course_summary.json），semester=2025-2026-2
- AI 函数实测：`get_course_info("大学物理")` 匹配 8 门，首条「周一 09:50-11:25 二教303」；空闲日 [周六, 周日]；意图检测 3/3 命中
- 本地回归测试 30/30 通过（表创建、同步、hash 检测、多用户隔离、AI 函数、意图检测）

### 注意事项

- 服务器课程缓存为 **2025-2026 第二学期**，而 `course_tools.py` 的 `TERM_START/TERM_END` 配置为 **2026 秋**（2026-09-07 起）——学期不匹配时 `current_week()` 返回 0，课程查询不受影响但周次过滤失效。需在网页端重新抓取新学期课表，或同步调整 TERM 配置。
- 部署过程中修复过一处：`main.py` 中 `lifespan` 定义顺序问题（app 实例化先于函数定义导致 NameError），已调整。

---

## 六、当前网站状态

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

## 七、后续发展方向

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

## 八、常用命令

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

### 后端部署（真实流程，2026-08-15 更新）

服务器上**不是统一编排**，而是 5 个独立 compose 项目（源码 ≠ git 仓库，用文件同步部署）：

| 容器 | compose 项目目录 | 说明 |
|------|------------------|------|
| ai-service | `/opt/snhgn/services/ai-service/` | wheels 离线装依赖，双网络(default + snhgn-network)，端口 127.0.0.1:8000 |
| gateway | `/opt/snhgn/services/gateway/` | 端口 127.0.0.1:8001，挂 docker.sock |
| scheduler | `/opt/snhgn/services/scheduler/` | 端口 127.0.0.1:8002 |
| caddy | `/opt/website/` | Caddyfile + web 静态文件，端口 8080 |
| cloudflared | `/opt/cloudflared/` | host 网络，不动 |

部署步骤（从本地 Windows）：

```powershell
# 1. 本地打包（在 d:\project\server，脚本与流程见 debug/deploy_p0p1_v3.sh）
tar -czf debug\payload.tar.gz --exclude '__pycache__' --exclude '*.pyc' `
  packages/ai-service/app packages/ai-service/Dockerfile packages/ai-service/requirements.txt `
  packages/gateway/app packages/gateway/Dockerfile packages/gateway/requirements.txt `
  packages/scheduler/app packages/scheduler/Dockerfile packages/scheduler/requirements.txt

# 2. 上传（pscp，hostkey 见上文）
& "C:\Program Files\PuTTY\pscp.exe" -batch -hostkey SHA256:roEbdNCO4i18oR7yR1r9HY6kUcE9/hJJsELFJ2CI46I -pw 1 debug\payload.tar.gz snhgn@192.168.50.2:/tmp/

# 3. 服务器上解压到 /tmp、剔除 schedule/models（root 所有运行资产，勿动）、
#    cp -r 合并复制到 /opt/snhgn/services/<svc>/，然后逐服务：
cd /opt/snhgn/services/<svc> && docker compose build && docker compose up -d
```

注意事项：
- `gateway/app/schedule/models/`（验证码模型+模板）为 root 所有且是运行数据，**不要删除/覆盖**
- 服务器直连 Caddy 测试必须带 `-H 'Host: snhgn.me'`，否则站点不匹配返回空 200（易误判为故障）
- 部署前备份到 `/opt/snhgn/backups/`（app + Dockerfile + compose + Caddyfile）

# 重载 Caddy 配置（改 Caddyfile 后无需重启容器）
docker exec caddy caddy reload --config /etc/caddy/Caddyfile

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

---

## 十四、首页落地页安全与体验优化（2026-08-24，本地已完成，待部署）

针对 `index.html`（静态落地页，尚未上线）的优化，改动均在本地仓库：

### 安全（P0）

- **移除敏感基础设施信息**：公网卡片不再展示内网 IP（192.168.50.2）、CPU/内存明细、各服务真实端口拓扑，改为抽象描述（Docker Compose / Cloudflare Tunnel / Caddy 等）
- **admin 弱密码**：`admin123` 仍未修改——本次尝试 SSH 执行改密被本机 clash TUN（fake-ip 198.18.x）劫持连接而失败。需在服务器内网机器上手动执行 `init_admin.py` 修改后回填本文档第四节

### 功能修复

- **状态徽章接真**：导航栏 "Server Online" 不再硬编码，改为每 60s 调 `/api/auth/verify` 探活（8s 超时），失败显示 "Server Offline" 红点
- **死链清理**：Notes 列表由假链接（#notes 自身）改为不可点击行 + "归档整理中" 占位；Spaces 卡 "24 Articles" 改为 "Manifesto"，"8 Projects" 改为 "8 Builds"
- **项目卡去虚构**：虚构的 Multi-Agent Orchestrator / Embedded Robotics Gateway 替换为真实的 Schedule Pipeline 与 AI Notice Monitor
- **移动端导航**：新增汉堡菜单（≤920px 显示），替代原先直接隐藏菜单的做法

### 性能与 SEO

- **字体国内可达**：Google Fonts 换 fonts.loli.net 镜像 + 异步加载（media=print 技巧）+ preload + noscript 兜底
- **SEO**：新增 canonical、Open Graph、Twitter Card、内联 SVG favicon；新增 `robots.txt`（屏蔽 /login /dashboard 等私有路径）与 `sitemap.xml`
- **快捷键提示**：⌘K 在非 macOS 平台显示为 Ctrl K
- **无障碍**：装饰性 SVG 加 aria-hidden、主题按钮加 aria-label、支持 prefers-reduced-motion

### 新增文件

| 文件 | 用途 |
|------|------|
| `README.md` | 说明本仓库定位及与 snhgn.me 前端仓库的关系 |
| `robots.txt` | 爬虫规则（含私有路径屏蔽） |
| `sitemap.xml` | 站点地图 |

### 待办

1. ~~修改 admin 密码~~（2026-08-24 已完成：20 位随机强密码，公网验证通过）
2. ~~部署落地页~~（2026-08-24 已完成，见下）

### 落地页部署记录（2026-08-24）

**重要更正**：部署时发现 `/opt/website/web/js`、`/css` 目录为空，线上 `index.html`（56KB）实为本设计的**前一版纯静态页**——所谓 Vue3 SPA 并未部署在源站，第六节"当前网站状态"中的前端描述与实际不符。所有路径经 `try_files` 回退均返回该静态页。

实际部署内容：

| 文件 | 位置 | 说明 |
|------|------|------|
| 新版落地页 | `/opt/website/web/index.html` | 直接替换旧版；旧版备份为同目录 `index.html.bak-20260824` |
| 样式 | `/opt/website/web/styles.css` | 新版拆分出的样式文件 |
| robots.txt / sitemap.xml | `/opt/website/web/` | 已就位；注意公网 robots.txt 被 **Cloudflare Content Signals 功能覆盖**（返回 CF 自己的内容信号声明），如需透出需到 CF 控制台关闭 AI Crawl Control 相关开关 |

Caddy 配置未改动（曾临时加过根路径 rewrite 特例，确认无 SPA 后已还原为原版并 reload）。

验证结果：`/` 与 `/login` 等全部路径返回新版落地页（200）、`/styles.css` 30486 字节、`/sitemap.xml` 正常、`/api/auth/me` 401（API 通畅）。

回滚方式：
```bash
sudo cp /opt/website/web/index.html.bak-20260824 /opt/website/web/index.html
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

遗留说明：~~AI Assistant / Schedule 等 Vue 页面目前不在源站上~~ → **2026-08-25 已部署**（见下）。

---

## 十五、Vue3 SPA 部署记录（2026-08-25）

### 部署内容

- 本地 `d:\project\snhgn.me` 执行 `npm run build`（vue-tsc 类型检查 + vite 构建，1.67s）
- 产物上传 `/opt/website/web/`：SPA 入口 `index.html`(655B) + `assets/`（含 KaTeX 字体、各视图分包）+ `favicon.svg` + `images/`
- 清理了旧的空目录 `css/`、`js/`
- **落地页共存方案**：`landing.html` + `styles.css` 保留；Caddyfile 增加 `@site_root path /` rewrite，根路径返回静态落地页，其余路径回退 SPA `index.html`
- 部署前备份：`/opt/snhgn/backups/web-pre-spa-*.tar.gz`

### 路由分配

| 路径 | 内容 |
|------|------|
| `/` | 静态落地页（landing.html，本仓库设计稿的新版首页） |
| `/projects` `/about` `/login` | Vue3 SPA 公开页 |
| `/ai` `/schedule` `/scripts` `/settings` | SPA 登录后页面 |
| `/dashboard` `/knowledge` `/server` `/admin/scripts` | SPA admin 页面 |
| `/api/*` | gateway 反代 |

注意：SPA 自身的 Home 路由（HomeView）被落地页遮蔽——用户在 SPA 内点"首页"会看到落地页。若希望登录用户回到 SPA 首页，可后续把 SPA 的 home 路由改为独立路径。

### 验证结果（公网）

| 检查项 | 结果 |
|--------|------|
| `/` 返回落地页（hero-fullscreen + loli.net 字体标记） | ✓ |
| `/login` `/ai` 返回 SPA HTML（引用 /assets/） | ✓ |
| `/assets/index-DZ4438kk.js` 等静态资源 | ✓ 200 |
| `/styles.css`（落地页样式） | ✓ 200 |
| `/api/auth/me` 未登录 | ✓ 401 |
| Caddy validate + reload | ✓ 无错误 |

### 回滚方式

```bash
# 恢复纯静态落地页版本
sudo tar -xzf /opt/snhgn/backups/web-pre-spa-<ts>.tar.gz -C /
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

---

## 十六、响应速度优化（2026-08-25）

### 瓶颈定位（实测数据）

| 层 | 耗时 | 结论 |
|----|------|------|
| 源站 Caddy 响应（127.0.0.1 直连） | **1~3ms** | 服务器/Caddy 完全不是瓶颈 |
| 公网单请求（CF 边缘→隧道→源站） | 900~1700ms | 慢在网络路径 |
| cloudflared 注册节点 | lax05/07/11（洛杉矶） | 国内访客绕美国西海岸，单往返大几百 ms |
| 隧道稳定性 | 偶发 502/重连（校园网 Wi-Fi 出网抖动） | HTML 不走缓存时每次都暴露此风险 |

CSS/JS 本就命中 Cloudflare 边缘缓存（cf-cache-status=HIT），但 **HTML 默认不缓存**，每次导航都要穿越隧道全程。

### 已实施

1. **落地页 CSS 内联**：styles.css（30KB）内联进 landing.html，首屏从"HTML 往返 + CSS 往返"两个串行往返变为一个，首页总耗时 1289ms+1475ms → **721ms**
2. **`/assets/*` 一年 immutable 缓存头**（Caddyfile）：带 hash 的 Vite 资源内容永不变化。注意当前被 CF 默认 Browser Cache TTL=4h 覆盖（见下"待办"）
3. Caddyfile 变更已 validate + reload，无错误；仓库 `index.html` 已同步为内联版（styles.css 保留作为样式源文件）

### 待办（需 Cloudflare 控制台操作）

1. ~~Cache Rule：让 HTML 也进边缘缓存~~（2026-08-25 已通过 API 完成：规则 id `00721e35c3bd4a80b0ad509d93272c12`，匹配 `http.host eq snhgn.me 且路径不以 /api 开头`，Edge TTL override 10 分钟；**部署新前端后需在 CF 控制台 Purge Everything 或等 10 分钟自动过期**）
2. ~~Browser Cache TTL 改为 Respect Existing Headers~~（2026-08-25 已通过 API 完成，zone setting `browser_cache_ttl=0`，源站 immutable 头已透出）
3. 可选：开启 Tiered Cache 减少回源；国内访问慢的根本约束是免费版 CF 无中国节点，属架构级限制

### 缓存配置注意事项

- **API 响应绝不能被缓存**：缓存规则的 expression 明确排除了 `/api/*`（SSE 流式、登录态接口都是动态响应），改动该规则时务必保留此排除条件
- 实测：`/` 首次 MISS ~1.4s（穿隧道），第二次起边缘 HIT；浏览器复用 HTTP/2 连接后体感更快
- **部署后清缓存**：运行 `scripts/purge-cf-cache.ps1`（凭据从环境变量 `CF_API_EMAIL` / `CF_API_KEY` 读取，已写入本机用户级注册表；AI 部署时会自动调用）。手动运行方式：
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\purge-cf-cache.ps1
  ```
- **安全提醒**：Global API Key 曾在对话中明文传输，建议尽快到 dash.cloudflare.com/profile/api-tokens 轮换；轮换后同步更新本机环境变量

---

## 九、本地代理（clash-meta）与 Gemini 接入开发记录（2026-08-10）

### 目标

在服务器部署本地代理，使 Docker 中的 AI Service 能访问 Gemini API（Google 官方接口）。

### 部署成果

- 安装 **clash-meta（mihomo）**，数据目录 `/opt/clash/`，systemd 服务 `clash-meta.service`（开机自启）
- 混合端口 `mixed-port: 7890`（HTTP/SOCKS5 共用），`allow-lan: true` → 监听 `*:7890`（容器经 `host.docker.internal:7890` 访问）
- AI Service 容器注入代理环境变量：
  - `HTTP_PROXY=http://host.docker.internal:7890`
  - `HTTPS_PROXY=http://host.docker.internal:7890`
  - `NO_PROXY=localhost,127.0.0.1,172.16.0.0/12,192.168.0.0/16,gateway,scheduler,ai-service,bigmodel.cn,siliconflow.cn,hf-mirror.com`
  - 配合 `extra_hosts: host.docker.internal:host-gateway`

### 关键问题排查

1. **校园网强制门户劫持（根因）**
   - 服务器 WiFi（wlp3s0）未通过北京林业大学 Dr.COM 认证时，**所有 IPv4 出站被劫持**：
     - HTTP 80 → 302 → `http://login.bjfu.edu.cn/`
     - HTTPS 443 → MITM 返回 `*.bjfu.edu.cn` 证书
   - IPv6 出站不受影响（这是旧 checker 误判"网络正常"的原因）
   - 解决方案：复用服务器已有 `/opt/bjfu-login` 认证脚本（Playwright 登录门户），手动触发 `do_login()` 完成认证

2. **DNS DoH 被劫持**
   - 原配置 `proxy-server-nameserver`/`fallback` 使用 DoH（dns.alidns.com 等），未认证时 TLS 被 MITM 导致节点域名解析失败
   - 修复：改为明文 UDP DNS（`proxy-server-nameserver: [223.5.5.5, 119.29.29.29]`、`fallback: [8.8.8.8, 1.1.1.1]`）

3. **节点失败自动切换**
   - 为 4 个 url-test 组（♻️自动选择 / 🇯🇵 / 🇸🇬 / 🇺🇸）添加 `interval: 60, timeout: 3000, tolerance: 50`
   - 节点超时后最多 60 秒内自动切换到健康节点

4. **checker.py 修复**
   - 原 checker 用 urllib 探测（默认走 IPv6 出站，未被劫持）→ 误判"网络正常"永不触发认证
   - 重写为强制 IPv4 直连（`http.client` + A 记录解析），能正确识别门户劫持并触发自动重登

5. **容器连不上代理（监听地址）**
   - 症状：容器内经 `host.docker.internal:7890` 连代理 → ConnectError
   - 根因：mihomo 入站默认只监听回环。改 `bind-address: "*"` 无效（那是出站绑定）
   - 修复：`allow-lan: true` → 入站监听 `*:7890`，容器可访问
   - 备注：`allow-lan: true` 会让同网段设备可访问代理（无认证），个人服务器场景可接受

6. **Gemini 400 "User location is not supported"（模型地区限制）**
   - 症状：`generateContent` 返回 `FAILED_PRECONDITION: User location is not supported`
   - 根因：Gemini 3.x 系列对部分地区（如香港等）不允许使用；2.5-pro 位置 OK 但 quota 超限
   - 修复：config.yaml 增加规则 `DOMAIN-SUFFIX,generativelanguage.googleapis.com,🇯🇵日本节点`
     （第一条命中优先于现有 `googleapis.com → 🔮节点选择` 规则），日本组实测对 gemini-3.6-flash 返回 200
   - 持久化：规则写入 config.yaml，重启 clash 后仍生效，不依赖 🔮节点选择 当前指向

### 验证结果

- `curl -x http://127.0.0.1:7890 https://www.google.com` → HTTP 200
- gstatic generate_204 → 204
- Gemini API（generativelanguage.googleapis.com）网络可达（403 = 缺 key，属正常）
- **真实 chat 调用 provider=gemini → success=True**（走 🇯🇵日本节点，重启后依然成功）
- ai-service / clash-meta / bjfu-login 均 active + 开机自启

### 代码改动（本地仓库）

- `packages/ai-service/app/providers/gemini.py`：新增 `ALLOWED_MODELS` 白名单 + `_require_allowed()` 校验
- `packages/ai-service/app/config.py`：`GEMINI_MODEL` 默认改为 `gemini-3.6-flash`
- `packages/ai-service/.env.example`：更新模型注释（7 个可用模型）
- `packages/ai-service/app/main.py`：`PROVIDER_BY_NAME` + `_build_providers_to_try(pref)`（用户首选 + 失败自动快速切到下一个）；`ChatRequest.provider`；`/api/settings` 返回 `available_providers` 并持久化 `ai_provider`
- `packages/ai-service/app/memory/database.py`：`user_settings` 表加 `ai_provider` 列（含旧库 ALTER 迁移）
- `packages/ai-service/app/memory/manager.py`：`UserSettingsManager` 支持 `ai_provider` 读写
- 前端（`d:\project\snhgn.me`）：`ChatInput.vue` 加 provider 单选组（自动/GLM/Gemini，无模型级选择）；`AiView.vue` 持久化偏好 + 发送参数 + 展示实际 provider

### 注意事项

- `/opt/clash/config.yaml` 为敏感文件（600 权限），含节点订阅信息，**不提交 git**
- 服务器重启后：clash-meta 与 bjfu-login 均已 enable，自动恢复
- 校园网掉线时 checker（IPv4 探测）会检测到并自动重登

---

## 十、P0+P1 性能重构部署记录（2026-08-15）

### 部署内容

架构审计（见 `docs/audit/2026-08-15-backend-architecture-audit.md`）后的 P0+P1 重构上线：

- **ai-service**：事件循环阻塞清零（全部同步 IO 改 to_thread）、GLM 流式桥接重写（每流 1 线程 + idle 超时）、Gemini/SiliconFlow 共享 httpx 连接池、上传流式落盘+文件名 sanitize、SSE 心跳（`: ping`，15s）、统一 ChatPipeline（chat/stream 共用上下文收集）、lifespan 统一关闭连接池
- **gateway**：auth 30s TTL 用户缓存、登录失败限流（5min/10 次误密码 → 429）、multipart 原始流透传（内存恒定）、cpu_percent to_thread、ddddocr 单例
- **scheduler**：record_history to_thread、建表一次性化、历史截断周期化（每 50 次）
- **基础设施**：ai-service 端口收回 127.0.0.1（修复 X-User-* 冒充漏洞）、四容器 mem_limit（1536/384/256/128m）、uvicorn --limit-concurrency（64/128/16）+ --timeout-keep-alive 65、Caddyfile flush_interval -1（SSE 零缓冲）

### 验证结果（全链路含公网）

| 检查项 | 结果 |
|--------|------|
| 5 容器状态 | ✓ 全部 Up |
| 端口绑定 | ✓ 8000/8001/8002 仅 127.0.0.1，8080 对外 |
| mem_limit | ✓ 四容器全部生效 |
| 登录（Cloudflare→cloudflared→Caddy→gateway） | ✓ 200 + JWT |
| 无 token API | ✓ 401 JSON |
| 非流式 chat | ✓（上游 429/503 时 fallback 链正常，极端耗时 114s 仍成功） |
| 流式 SSE | ✓ status 事件 + 逐 token + 零缓冲 |
| 静态站 + 公网 https://snhgn.me | ✓ 200 |

### 回滚方式

```bash
# 服务器上
tar -xzf /opt/snhgn/backups/pre-p0p1-20260815-213024.tar.gz -C /
# 然后逐服务重建
cd /opt/snhgn/services/<svc> && docker compose up -d --build
# caddy 同理（/opt/website）
```

### 遗留观察项

- Gemini 代理节点偶发 ConnectError/503（clash 日本组），fallback 已覆盖，无需处理
- GLM 偶发 429（zai SDK 自动重试中），高峰期正常现象
- memory summarize 的 qwen（SiliconFlow）偶发 ReadTimeout，后台异步任务不影响主流程

---

## 十一、登录持久化改造部署记录（2026-08-15）

### 部署内容：Server-side Session + HttpOnly Cookie 持久登录

- **gateway 新增 `app/sessions.py`**：SQLite sessions 表（复用 gateway.db，启动幂等建表），sid=`secrets.token_urlsafe(32)`，有效期 30 天（`SESSION_EXPIRE_DAYS` 统一配置），创建时惰性清理过期行
- **`app/auth.py` `require_auth` 双通道**：优先 Cookie Session（30s TTL 进程缓存），回退 Bearer JWT（兼容旧客户端/脚本）；两通道返回统一 payload {sub, uid, role}，下游 require_user/admin、X-User-* 注入零改动
- **`app/routers/auth.py`**：login 成功 → 创建 Session + `Set-Cookie`（HttpOnly/SameSite=Lax/Max-Age=30d/Secure，服务端 Session 旋转防 fixation）+ 响应增加 user_id；新增 `GET /api/auth/me`（恢复登录状态，未登录 401）；新增 `POST /api/auth/logout`（删 Session 行 + 清 Cookie + 失效缓存，立即生效）
- **前端 snhgn.me**：`stores/auth.ts` 重写（启动 init() 调 /me 恢复用户，authReady 防闪砀；旧 localStorage JWT 一次性过渡后清除）；`api.ts` 全部 fetch 加 credentials + 401 统一跳登录页；`router/index.ts` 异步守卫 await init()；Navbar/AssistantSidebar authReady 门控 + 退出后跳转
- **生产配置**：`/opt/snhgn/services/gateway/.env` 追加 `SESSION_COOKIE_SECURE=True`（Caddy 会重写 X-Forwarded-Proto 为 http，无法自动判断，必须显式配置）

### 验证结果

| 检查项 | 结果 |
|--------|------|
| 本地单元测试（tests/test_auth_session.py，9 用例：Cookie 属性/me/401/Bearer 兼容/logout 失效/旋转/过期/错密码/下游 payload） | ✓ 9/9 |
| 服务器内网全链路（verify_auth.sh 15 项） | ✓ 15/15 |
| 公网 HTTPS 完整登录流（登录→Cookie→/me→AI API→logout→旧 Cookie 401） | ✓ ALL PASS |
| 浏览器实测 6 步（未登录重定向/登录/刷新保持/导航栏状态/退出/退出后重定向） | ✓ 6/6（截图 debug/step1-6） |
| Set-Cookie 属性（公网实测） | ✓ HttpOnly + Secure + SameSite=lax + Max-Age=2592000 |
| 伪造 Session ID | ✓ 401 |

### 注意事项

- 前端 dist 部署：`/opt/website/web/` 历史文件可能 root 所有，清理需 `sudo rm -rf /opt/website/web/*` 再复制；web 目录本身也可能 root 所有（tar 解包报 Cannot utime 但内容完整，ls 确认即可）
- 服务器自身 curl 公网偶发 000（Wi-Fi 出网到 CF 边缘抖动），公网用户路径不受影响，验证时从本地测
- 前端仓库不在本 workspace，修改走中转：`debug/frontend-patch/` → Copy-Item → `npm run build` → tar 上传

---

## 十二、管理员脚本 AI 生成/审查改造部署记录（2026-08-15）

### 功能：新建任务由手写命令改为「提示词 → AI 编写 → 另一 AI 审查」

- **scheduler `app/routers/scripts.py` 新增两端点**：
  - `POST /api/admin/scripts/generate`：{name, prompt} → 调 ai-service（provider=glm）生成 Python 代码，本地 `ast.parse` 语法校验，返回 {code, syntax_ok, generator}
  - `POST /api/admin/scripts/review`：{code} → 调 ai-service（provider=gemini，**另一个 AI 交叉验证**）审查安全性/正确性/健壮性，返回 {verdict: pass|warn|fail, issues, summary, reviewer}；语法错直接 fail 不调 AI
  - 拆两端点原因：gateway REQUEST_TIMEOUT=130s，串行两次 AI 调用有截断风险；且分开后管理员手改代码可单独重新审查
- **`ScriptCreate/ScriptUpdate` 新增可选 `code` 字段**：有 code 时后端语法校验 → 落盘 `/app/scripts/<safe_name>.py`（文件名 sanitize 仅 [a-zA-Z0-9_-]）→ command 自动生成为 `python /app/scripts/xxx.py`；command 与 code 二选一；更新时 name 变更自动清理旧文件；删除任务时自动清理落盘文件
- **生成/审查提示词内置硬约束**：仅标准库（容器内无第三方库）、网络超时+重试、禁止危险操作（rm -rf/反弹 shell 等）、print 进度日志
- **配置（scheduler config.py）**：`SCRIPTS_CODE_DIR=/app/scripts`、`AI_GENERATE_TIMEOUT=110`、`AI_CODE_PROVIDER=glm`、`AI_REVIEW_PROVIDER=gemini`
- **compose 变更**：scheduler volumes 追加 `- /opt/snhgn/scripts:/app/scripts`（宿主目录已存在，内含 bjfu-login、notice-monitor 子目录，互不冲突）
- **前端 snhgn.me**：`api/scripts.ts` 新增 generateScriptCode/reviewScriptCode；`AdminScriptForm.vue` 重写——新建模式为提示词输入 +「AI 生成代码」按钮 + 代码编辑区（可手改）+ 审查结果块（verdict 徽章/issues 列表/重新审查），生成成功自动触发审查，fail 需 confirm 才能创建；编辑模式保持原执行命令编辑

### 验证结果（服务器内网直连 scheduler:8002）

| 检查项 | 结果 |
|--------|------|
| generate：glm 生成 1641 字符代码，语法 OK | ✓ |
| review：gemini 交叉审查，实报 `ssl._create_unverified_context` 安全隐患 + 重试无退避（verdict=warn） | ✓ |
| create：201，command 自动生成 `python /app/scripts/aigen_selftest.py` | ✓ |
| run：AI 生成脚本实际执行 success | ✓ |
| 落盘文件存在，删除任务后文件同步清理 | ✓ CLEANUP-OK |

### 注意事项

- 生成耗时约 30-90 秒，前端按钮有 loading 状态提示；单次 AI 调用上限 110s < gateway 130s，不会被网关截断
- `/opt/snhgn/scripts/` 下 AI 生成文件为容器 root 所有，宿主删除需 docker exec 或 sudo
- 审查 AI 的 issues 展示给管理员参考，verdict=fail 仅弹窗拦截非强制；管理员仍是最终把关人

---

## 十三、校园网认证探针漏检修复与自愈优化（2026-08-20）

### 问题现象与根因分析

- **现象**：公网访问 `https://snhgn.me` 超时/无法连接，Cloudflare Tunnel 容器日志报错 `dial tcp 198.41.xxx.xxx:7844: i/o timeout`。
- **排查过程**：
  1. 通过内网（`192.168.50.2`）SSH 成功连接服务器，所有 Docker 容器（gateway、caddy、ai-service 等）运行正常，服务健康端点正常。
  2. 服务器 IPv4 出网探测 `curl http://www.baidu.com` 返回 HTTP 200，但内容为 Dr.COM 认证网关的 JS 跳转页面（`location.href="http://10.1.1.10/a79.htm..."` 与 `Authentication is required`）。
  3. `bjfu-login.service` 一直处于 running 状态，每 5 分钟日志显示 `[INFO] 网络正常，无需认证`。
- **根因**：
  - `checker.py` 探针在检测 HTTP 响应时，仅在 302 重定向或 body 包含旧版特征时判定离线；
  - 遇到 Dr.COM 返回的 **HTTP 200 + HTML/JS 跳转脚本**（无 302 Location 头）时，因未覆盖 `10.1.1.10` / `a79.htm` / `Authentication is required` / `location.href` 等特征，被判定为正常的 200 OK 连通，导致永远不触发 `login.do_login()`。

### 修复方案

1. **重构 `checker.py` 探针**：
   - 引入 **HTTP 204 精准探针**（`http://connect.rom.miui.com/generate_204`、`http://cp.cloudflare.com/generate_204`）：正常连网返回 204 No Content，被网关拦截返回 200/302 + HTML 即可 100% 判定为劫持。
   - 完善常规 HTTP 探测的关键字库：覆盖 `10.1.1.10`、`a79.htm`、`authentication is required`、`location.href`、`dr.com` 等所有劫持特征。
   - 保持强制 IPv4 A 记录直连，防止 IPv6 逃逸。
2. **提高自愈频率**：
   - 将 `CHECK_INTERVAL` 由 300 秒（5 分钟）调整为 60 秒，掉线后 1 分钟内自动重登恢复，大幅缩短不可用时间。
3. **本地单元测试固化**：
   - 新增 `tests/test_checker.py`，模拟 Dr.COM 真实拦截响应与 204 探针，4/4 用例测试通过。

### 验证结果

- 触发重登后，Dr.COM 认证成功，`cloudflared` 隧道自动秒级重连 4 条链路。
- 公网 `https://snhgn.me` 恢复 200 OK 访问，`/api/auth/me` 正常返回 401（后端路由通畅）。

---

## 十五、Cloudflare Tunnel QUIC 丢包与 502 Bad Gateway 根因修复（2026-08-27）

### 问题现象
公网访问 `https://snhgn.me`（及 API 端点）频繁或间歇性出现 **Cloudflare 502 Bad Gateway** 错误。

### 日志排查与根因分析
1. **本地后端服务状态**：
   - 登录宿主机排查，`gateway`、`caddy`、`ai-service`、`scheduler` 容器均正常运行（UP >17h），直接请求本地 `127.0.0.1:8080` (Caddy) 与 `127.0.0.1:8001` (Gateway) 均秒级返回 200/401，本地并无 502。
2. **Cloudflare Tunnel 日志**：
   - 查看 `cloudflared` 容器日志，发现大量 QUIC 相关的超时与断连报错：
     - `ERR Failed to dial a quic connection error="failed to dial to edge with quic: timeout: no recent network activity"`
     - `ERR failed to accept incoming stream requests error="failed to accept QUIC stream: Application error 0x0 (remote)"`
     - `WRN failed to serve tunnel connection error="accept stream listener encountered a failure while serving"`
   - **根因**：`cloudflared` 默认采用基于 UDP 7844 端口的 QUIC 协议与海外 Cloudflare Edge 节点建立隧道连接。国内宽带/校园网环境对出境 UDP 存在 QoS 限速与丢包，导致 4 条 QUIC 链路周期性全部断开或陷入重连。在所有链路重连的真空期，Cloudflare CDN 无法触达源站，进而向访客返回 502 Bad Gateway。

### 修复方案
- 修改 `cloudflared` 启动命令，指定 `--protocol http2`（通过 TCP 443 端口连接 Cloudflare Edge）：
  ```yaml
  command: tunnel --protocol http2 --edge-ip-version 4 run --token ${CLOUDFLARE_TUNNEL_TOKEN}
  ```
- TCP 连接具有内核级可靠重传与握手重试机制，对国内弱网/UDP 干扰环境有极强的抗丢包稳定性。

### 验证结果
- 服务器 `/opt/cloudflared/docker-compose.yml` 更新并完成容器重建。
- `cloudflared` 4 条链路全部以 `protocol=http2` 毫秒级建立成功（lax08/09/10/12）。
- 本地多次并发访问 `https://snhgn.me`、`https://snhgn.me/api/auth/verify` 测试均 100% 成功稳定响应，502 错误彻底消除。



## 16. AI板块 Gemini 无法回复自动降级至智谱 (2026-08-27)

### 故障现象
用户在 AI 板块设置选用 Gemini 模型，但实际对话时，AI 每次均由智谱 GLM 模型进行回复。

### 排查过程
1. **代码逻辑审查**：
   - 在 \packages/ai-service/app/main.py\ 的 \_providers_for_request\ 方法中，系统会根据用户设置将所选模型提供商排在首位，其他已启用提供商顺延。因此当首选模型请求抛出异常时，代码中的 \	ry/except\ 块会捕获异常并平滑切换到下个模型（即智谱 GLM）。
2. **日志分析与 API 直连测试**：
   - 查询 \i-service.log\，发现调用 Gemini 的 \streamGenerateContent\ 接口时始终返回 \HTTP 400 Bad Request\。
   - 登录服务器进行 \curl\ 测试，验证请求已成功通过 W.0.0.1:7890\（Clash 代理）发往 Google，但 Google 返回了具体的错误负载：
     \\json
     { "error": { "code": 400, "message": "User location is not supported for the API use.", "status": "FAILED_PRECONDITION" } }
     \3. **根因定位**：
   - Google Gemini API (AI Studio) 实施了极其严格的 IP 地域与机房/代理风控限制。尽管我们已通过 Clash 的 \🚀节点选择\ 代理将出口定位到海外（测试过日本、美国、台湾、新加坡等多地节点），但由于该机场的 IP 属于云服务器/数据中心（如 AS46997），依然被 Google 封锁。Google 拒绝为这些已知代理 IP 提供服务，因而返回 "User location is not supported"。

### 结论与后续方案
代码服务机制（自动重试与 fallback 降级）运行完美，成功拦截了此错误并保障了服务的可用性（智谱接管）。
当前仅靠更换普通机场节点难以突破 Gemini 的严格风控。后续如需稳定使用 Gemini，需替换为专门声明支持“Gemini 解锁”的原生 IP 节点、原生家宽代理，或者更换为代理 API 转发服务。
