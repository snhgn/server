# snhgn.me 服务器与项目总览

最近更新：2026-08-10

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
