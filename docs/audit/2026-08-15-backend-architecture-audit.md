# Backend Architecture Audit — snhgn.me

> 审计日期:2026-08-15 | 服务器:i5-7200U(4核) / 3.7GB RAM / Ubuntu 22.04
> 审计范围:`d:\project\server` 全部后端代码 + `d:\project\snhgn.me` 前端 API 调用 + 部署配置
> 阶段:第一阶段(只读分析)产出。**未修改任何代码。**

---

## 1. 当前架构图(依据实际代码绘制)

```
Browser (Vue3 SPA, d:\project\snhgn.me)
   │  https://snhgn.me
   ▼
Cloudflare CDN/TLS ──► Cloudflare Tunnel(出站, 无公网IP)
   ▼
cloudflared 容器 (host 网络)
   ▼ http://127.0.0.1:8080
Caddy 容器 (caddy:2.9-alpine)
   ├─ /api/* ────────────► gateway:8001 (自建, FastAPI)
   │                        ├─ /api/auth/*     本地 SQLite (gateway.db/users)
   │                        ├─ /api/ai/*      ──httpx 代理──► ai-service:8000
   │                        ├─ /api/scheduler/* ──────────► scheduler:8002
   │                        ├─ /api/scripts/*  ──────────► scheduler:8002
   │                        ├─ /api/schedule/*  本地课表模块(爬虫+缓存)
   │                        └─ /api/status      psutil + Docker Socket
   └─ /* 静态文件 /srv/web (Vue3 构建产物, SPA 回退)

ai-service 容器 (FastAPI, uvicorn 单 worker, 端口 8000 ⚠发布到 0.0.0.0)
   ├─ app/main.py(1569 行单体: chat/stream/files/knowledge/memory/settings/admin/image)
   ├─ context/    ContextBuilder(Token 预算压缩) + 模型窗口注册表 + token 估算
   ├─ memory/     MemoryManager / ConversationStore / UserSettingsManager / FileManager
   │              (全部 SQLite memory.db, 每次操作新建连接)
   ├─ rag/        Chroma PersistentClient + ONNX MiniLM-L6-v2 本地嵌入
   ├─ providers/  GLM(zai-sdk 同步+线程桥接) / Gemini(httpx) / SiliconFlow(httpx)
   └─ course_tools.py  读取 gateway 共享卷的课表 JSON(意图检测注入)

scheduler 容器 (FastAPI + APScheduler, 127.0.0.1:8002)
   ├─ jobs      command/http 定时任务(SQLAlchemy JobStore→SQLite)
   └─ scripts   自动化脚本 CRUD + subprocess 执行 + 分片日志

宿主机 systemd:clash-meta(7890 代理, Gemini 出网) / bjfu-login / daily-reboot
ai-notice-monitor:独立脚本(不在 compose 内, 由 scheduler/cron 触发)
共享卷:/opt/snhgn/data (memory.db, chroma, uploads, course-data, gateway.db ...)
```

**容器资源基线(无限制配置):** ai-service(chromadb+onnxruntime ≈350-500MB RSS)、gateway(numpy+opencv+ddddocr ≈250-350MB)、scheduler ≈120MB、caddy ≈30MB。合计约 0.8-1GB, 3.7GB 机器尚有余量但无护栏。

---

## 2. 当前真实数据流(一次带 Memory+RAG 的流式聊天)

```
用户消息
 ▼ HTTP POST /api/ai/chat/stream (JWT)
Caddy ──► gateway.proxy_ai
 ▼ require_auth: JWT 解码 + [DB-1] get_user_by_id(同步SQLite, 阻塞事件循环)
 ▼ httpx 共享连接池 ──► ai-service(同容器网络, 1 次内部 HTTP)
_stream_chat_generator:
 1  [DB-2] user_settings.get(同步, 阻塞)
 2  若 use_memory: [DB-3] memories 全量 get_all(同步, 阻塞)
 3  若 use_rag:    Chroma 查询 = ONNX 嵌入计算(同步CPU 50-500ms, 阻塞整个事件循环!)
 4  若 file_ids:   [DB-4] user_files 查询(同步) + 磁盘读文件 + base64(同步, PDF解析可达秒级)
 5  课表意图检测: 读磁盘 JSON(同步)
 6  [DB-5] conversations.get_history(LIMIT 15 轮, to_thread ✅)
    [DB-6] conversation_meta.get(滚动摘要, to_thread ✅)
 7  ContextBuilder.build(纯CPU, 快)
 8  Provider 调用:
      GLM: zai-sdk 同步 → 生产者线程 + queue + executor 消费(每流占 2 线程)
      Gemini: 新建 httpx.AsyncClient → 新 TCP+TLS(经 clash 代理赴日节点, +1~3s)
 9  逐 token: MemoryTagFilter 过滤 → SSE yield → gateway 原样转发 → 浏览器
10  完成后: [DB-7] conversations.add(to_thread ✅)
    [DB-8] conversation_meta.get(同步, 阻塞)
    后台: summarize_session → [AI-2] 1 次标题生成调用 → [DB-9] meta 写入
```

**单次请求资源账单:**

| 项目 | 数量 | 备注 |
|---|---|---|
| SQLite 查询/写入 | **9 次** | 其中 5 次在 async 函数内同步执行(阻塞事件循环) |
| 网络请求 | 3-4 次 | browser→CF→caddy→gateway→ai-service 链 + provider 1 次 + 后台总结 1 次 |
| Embedding 计算 | 0-1 次 | RAG 开启时, 同步阻塞 |
| AI API 调用 | 1-2 次 | 主回答 1 + 新会话标题生成 1(后台) |
| 同步阻塞点 | **6 处** | auth / settings / memories / RAG嵌入 / 文件读取 / 完成后meta |
| 线程占用(流式) | 2 线程/流 | GLM 桥接;默认 executor 仅 8 线程 |

**可异步化而未异步的:** RAG 嵌入、文件读取/PDF解析、SQLite 同步调用、课表文件读取、knowledge 入库(最严重, 见 §9-P0-4)。

**已做得好的:** 历史只取 15 轮(非全量)、滚动摘要异步压缩、总结后台化+信号量限4、对话写入 to_thread、gateway httpx 连接池、意图检测避免无谓 Memory/RAG。

---

## 3. 当前数据库结构

全部 SQLite, 共 **4 个库文件**:

**gateway.db**(gateway 容器)
- `users(id, username, password_hash, role)` — JWT + bcrypt
- `schedule_cache(user_id UNIQUE, semester, schedule_json, updated_time)` — 课表原始缓存
- `courses(id, user_id, course_name, teacher, location, weekday, start/end_section, start/end_week, semester, update_time)` + idx(user_id, semester)
- `course_sync_status(user_id PK, semester, data_hash, last_sync_time, sync_status, ...)`

**memory.db**(ai-service 容器)
- `memories(id, user_id, category, key, value, created/updated_at, UNIQUE(user_id,category,key))` + idx(user_id, category)
- `conversations(id, user_id, session_id, message, response, created_at)` + idx(user_id, session_id) — 1行=1轮
- `conversation_meta(user_id+session_id PK, title, summary, keywords JSON, rolling_summary)`
- `user_settings(user_id PK, memory_enabled, ai_provider)`
- `user_files(id TEXT PK, user_id, filename, file_type, file_size, storage_path, status)` + idx(user_id, status)

**scheduler:jobs.db**(APScheduler SQLAlchemy JobStore)+ **scripts.db**(`scripts`, `script_runs`, `tasks`)+ **scheduler_history.db**(`run_history`, 每次插入后全表 DELETE NOT IN 截断)

**数据库问题:**
- 无连接池:每个操作 `connect→execute→commit→close`(3 个 Manager 全如此)
- `conversations` 缺 `(user_id, session_id, id)` 复合索引 → `ORDER BY id DESC LIMIT n` 需额外排序(小数据量影响有限)
- 对话/运行历史**无保留期限策略**, 无限增长
- `get_conversation` API 默认只回最近 20 轮(前端加载旧会话不完整, 功能性限制)
- WAL 已启用 ✅, busy_timeout=10s ✅(scripts.db 每连接重复设 PRAGMA, 浪费但无害)

---

## 4. AI 调用流程(Provider 层)

```
chat/stream → _build_providers_to_try(请求参数 > 用户设置 > 默认序)
  翻译检测(正则)命中 → SiliconFlow Hunyuan-MT 优先
  GLM(zai-sdk, 单例 client)
    ├─ 文本链: glm-4.7-flash → glm-4-flash-250414(模型级 fallback)
    ├─ 视觉链: glm-4.6v-flash → glm-4.1v-thinking-flash → glm-4v-flash
    └─ 非流式: asyncio.to_thread + wait_for
       流式:   生产者线程 → queue → run_in_executor(q.get) 逐 token 消费
  Gemini(httpx, 默认 GEMINI_ENABLED=False)
    chat/chat_stream/chat_with_images 每次调用新建 AsyncClient(无连接复用!)
  SiliconFlow(翻译/总结专用, 同样每次新建 AsyncClient)
失败切换: provider 抛异常 → 尝试列表下一个(流式已产出内容则中断不回退 ✅)
```

**问题:** ①Gemini/SiliconFlow 无连接复用(每次 TLS 握手, Gemini 经代理 +1~3s TTFT);②GLM 流式桥接每流占 2 线程, 默认 executor=min(32, cpu+4)=**8 线程** → 并发 7-8 流后线程饥饿;③无超时分级(chat_stream 硬编码 120s, REQUEST_TIMEOUT=30s 不一致);④无熔断/健康度, provider 持续故障时每请求都冷重试;⑤**视觉链不走 Context Engine**——带图消息完全丢失对话历史与 memory/rag 上下文(full_prompt 仅为拼接文本);⑥代理环境变量(NO_PROXY 等)在 compose 层注入, 但代码层未统一 HTTP 客户端, 与"代理统一在 Provider 层"的目标不符(Gemini/SiliconFlow 依赖 env 默认行为)。

---

## 5. Conversation 流程

- 写入:回答完成后 `conversations.add`(1 行=1 轮 Q&A), `memory_enabled=false` 时**完全不保存**(连历史都没有——开关语义混淆: "记忆开关"实际控制了"对话历史保存", 关闭后无法多轮对话)
- 读取:`get_history(user, session, limit=15)` 只取最近 15 轮 ✅;旧内容靠 `rolling_summary`(≥10 轮且超窗时异步压缩, 交给 Qwen 总结)
- 会话列表:`list_sessions` 单 SQL + 相关子查询取 first_msg(可接受)
- 首轮后台生成 title/summary/keywords(已有标题则跳过 ✅)
- 前端:`/api/ai/conversations/{sid}` 拉历史(默认 20 轮上限)

**问题:** settings/memory 双路径重复读取 meta;`memory_enabled` 语义过载;历史 API 无分页参数;删除会话不清 Chroma 中该会话相关内容(无关联, 可接受)。

## 6. Memory 流程

- **读**:命中关键词(客户端 flag 或 `_MEMORY_NEED_RE` 正则)→ 全量 `get_all` → 格式化为 prompt 片段(无嵌入检索, 全量注入;条目多时被 ContextBuilder 整体丢弃, 无截断策略)
- **写**:两条路径 — ① AI 回答中嵌入 `<memory category key>value</memory>` 隐藏标签, 流式过滤器提取并从用户可见文本移除(实现完整, 跨 chunk 正确);② 无用户手动写 API 之外的记忆提取
- **每轮成本**:memory 开启时每请求注入 `_MEMORY_WRITE_NOTE` ≈200 token
- **评价**:没有"每条消息一次 AI 提取"的反模式 ✅;标签协议是低成本方案 ✅;但无量化上限、无相关性检索、写入完全依赖模型自觉。

## 7. RAG 流程

- **入库**:`/api/knowledge/add` 或 files→knowledge:load_file(md/txt/pdf/docx) → chunk(500/50 字符滑窗) → Chroma add(metadata 带 user_id)
  ⚠ **同步执行于 async 路由内**:100 页 PDF = 数百 chunk × ONNX 嵌入, **阻塞事件循环数十秒~分钟级**, 期间整个 ai-service 所有用户的所有请求(含进行中的流式 token 转发)全部冻结
- **检索**:`rag.search` → ONNX 嵌入 query(同步 50-500ms CPU) → HNSW cosine Top-3 → where={"user_id": X} 强制隔离 ✅
- **无查询缓存**, 相似问题重复嵌入;无 score 阈值过滤(dist 大的也注入);chunk 按字符切, 不按语义/段落
- Chroma+ONNX 常驻 ≈300-400MB RSS(首次检索触发懒加载 ✅)

## 8. Streaming 流程

- 方案:**SSE over HTTP/1.1**(POST + fetch ReadableStream 解析), 事件:status/token/complete/error
- 链路:ai-service → gateway(`aiter_raw` 原样转发, 无缓冲 ✅) → Caddy(`/api/*` 不压缩 ✅) → Cloudflare Tunnel → 浏览器
- TTFT 构成:gateway 代理(≈1ms) + 前置检索(0-500ms+) + provider 首包(GLM≈0.5-2s;Gemini 需新建 TLS 经代理 ≈+1-3s)
- **无 SSE 心跳**:Cloudflare 空闲约 100s 超时, 若 provider 长时间无 token(推理慢/排队), 连接可能被 CF 静默掐断, 前端表现为卡死
- 视觉请求伪流式(整段生成后切 40 块), 已注释说明
- 中断策略:已产出内容后失败 → 不回退不保存 ✅(实现正确)

---

## 9. 性能问题清单(按类别)

**CPU/事件循环**
- P0-① async 处理器内 6 处同步阻塞(见 §2);最重是 RAG 嵌入与 knowledge 入库、PDF 解析
- GLM 流式桥接的 per-token `run_in_executor` 调度开销 + 线程占用
- ddddocr 在 gateway 每次验证码识别重新实例化(重复加载 ONNX 模型)

**内存**
- P0-⑤ 上传:`await file.read()` 全量读入后才校验大小;gateway 代理 multipart 又 `await value.read()` 全量读一遍(同一文件双份内存);无流式落盘
- Chroma 常驻 ~300-400MB;无容器 mem_limit, 异常时可能拖垮整机
- base64 图片(≤20MB 文件 → ~27MB base64 字符串)直接进 prompt

**IO/数据库**
- 每操作新建 SQLite 连接;auth 每请求查库
- conversations 缺复合索引;历史无保留策略

**网络/API**
- P0-② Gemini/SiliconFlow 每请求新建 TLS 连接
- 无 SSE 心跳;无 HTTP/2;gateway→ai-service 虽有连接池但 SSE read=None 无整体超时

**Token**
- `_MEMORY_WRITE_NOTE` 每请求 ~200 token(可条件化)
- RAG 无相似度阈值, 低质片段也注入
- 标题生成/滚动压缩已用廉价模型 ✅

**并发(10 用户模拟)**
- 7-8 路流式后默认 executor 饱和 → 所有 GLM token 转发卡顿
- 任一用户触发 RAG/入库 → 全服冻结数百 ms~分钟
- SQLite 单写者:高并发写靠 WAL+busy_timeout 排队(可接受)
- 结论:**User A 的大请求会显著劣化 User B 的流式体验**(单 worker + 事件循环阻塞 + 线程池饱和三重叠加)

---

## 10. 架构问题

1. **ai-service/app/main.py 1569 行单体**:chat、stream、files、knowledge、memory、settings、admin、image 全在一个文件;非流式与流式两套 ~200 行几乎重复的上下文组装逻辑(已经出现行为漂移风险)
2. **认证架构**:ai-service 盲信 `X-User-*` 头(内部信任模型), 但端口 `8000:8000` 发布到 **0.0.0.0** → 局域网任意设备可伪造身份直连(gateway/scheduler 都正确绑定 127.0.0.1)
3. **`memory_enabled` 语义过载**:同时控制长期记忆、对话历史保存、(间接)标题生成——关闭后多轮对话直接失效
4. **三份 Caddyfile 漂移**:compose 挂载的 `./deploy/Caddyfile` 是**没有 /api 反代的旧版**(用它重新 up 会 404);正确版在根目录 `/Caddyfile` 与 `deploy/caddy/Caddyfile`
5. **packages 内残留每服务 docker-compose.yml**(网络拓扑与顶层不一致)
6. uvicorn 全部单 worker 且未配 `--limit-concurrency`;无 healthcheck;无资源限制
7. scheduler 服务与其说必要, 不如说历史产物:其 API 面很薄, 但独立占用一个容器+端口(可合并候选, 见 §15)
8. 视觉链绕过 Context Engine(丢历史)
9. 前端 `/api/ai/conversations/{sid}` 默认 20 轮上限, 长会话历史展示不完整(后端 rolling_summary 有数据却未用于展示)

## 11. 安全问题

| # | 级别 | 问题 | 位置 |
|---|---|---|---|
| S1 | **高** | `/api/knowledge/add` 路径穿越:`save_path = save_dir / file.filename`, filename 可为 `../../x` 或绝对路径 | ai-service main.py L1393 |
| S2 | **高** | ai-service 8000 端口发布 0.0.0.0 + 盲信 X-User 头 → 内网任意伪造身份读/写任意用户记忆、对话、文件 | docker-compose.yml L27-28 |
| S3 | 中 | 上传先全量读内存后验大小(DoS/OOM 向量;应先看 Content-Length + 流式) | main.py L1184-1189 |
| S4 | 中 | 登录无限流/失败锁定;bcrypt 虽慢但可被并行打爆 CPU | gateway auth |
| S5 | 中 | `admin123` 弱密码 + 明文记录于仓库内 server-info.md | server-info.md L191 |
| S6 | 低 | gateway `/api/status` psutil 间隔采样阻塞 1s(管理端, 影响小) | status.py L53 |
| S7 | 低 | scheduler 执行任意 shell(设计如此, 但 owner_id 未参与鉴权, 所有 admin 脚本互通——单管理员场景可接受) | scripts 路由 |
| S8 | 低 | CORS 未显式配置(默认同源, 当前拓扑下安全) | — |

做得对的:SQL 全参数化 ✅;日志不落敏感信息(实测核对)✅;JWT 过期+用户存在性校验 ✅;RAG user_id 强制隔离 ✅;模型白名单 ✅;爬虫凭据不落盘 ✅。

## 12. 冗余清单(可删除)

| 项 | 说明 |
|---|---|
| `packages/schedule-pipeline/` | captcha_solver/course_app 全套与 gateway/app/schedule 重复(迁移源, 已完成使命) |
| 根目录 `captcha_solver/`、`course_app/` | 又一份副本(含 samples 模板数据) |
| `deploy/Caddyfile`(旧版) | 与根 Caddyfile、deploy/caddy/Caddyfile 三份并存, 且 compose 挂载的是错的 |
| `packages/*/docker-compose.yml` ×3 | 与顶层 compose 重复且网络配置不一致 |
| `.deploy-staging/` | 测试产物 |
| `tests/`(空) | 仅 README 与临时脚本 |
| main.py 内部 | `_stream_chat_generator` 与 `chat` 的重复组装段(~200 行);`prompt_parts` 构建后仅用于翻译检测 |
| scheduler `record_history` | 每次执行都 `CREATE TABLE IF NOT EXISTS` + 全表截断 DELETE |
| gateway uvicorn 双写日志(StreamHandler+RotatingFile 重复 addHandler 模式) | 三服务同款样板, 无害但重复 |

---

## 13. 最严重的 10 个瓶颈(排序)

| # | 瓶颈 | 影响 | 量级 |
|---|---|---|---|
| 1 | **事件循环同步阻塞**(RAG 嵌入/knowledge 入库/PDF 解析/SQLite 同步调用) | 单 worker 下一个用户的重操作冻结所有用户的流式与请求 | 50ms~分钟级/次 |
| 2 | **Gemini/SiliconFlow 无连接复用** | 每次 AI 调用重付 TCP+TLS(经代理), TTFT 劣化 | +1~3s/次 |
| 3 | **GLM 流式线程桥接占 2 线程/流, executor 仅 8 线程** | 并发 ~7 流后全线卡顿, 多用户能力封顶 | 并发上限≈7 |
| 4 | **knowledge/add 同步入库** | 大文档入库期间全服不可用 | 分钟级 |
| 5 | **上传全量读内存×2(ai-service+gateway)** | 大文件 OOM 风险(3.7GB 机器) | 峰值 2×文件 |
| 6 | **ai-service 端口暴露 + 头信任**(S2) | 安全:内网可冒充任意用户 | — |
| 7 | **knowledge/add 路径穿越**(S1) | 安全:任意写文件 | — |
| 8 | **auth 每请求同步查库, 无缓存无限流** | 每请求 +1 次 SQLite + 暴力破解面 | ~1ms/req |
| 9 | **chat 与 stream 200 行重复 + 1569 行单体** | 维护性与漂移风险(改一处漏一处) | — |
| 10 | **无 SSE 心跳 + compose 挂载错误 Caddyfile + 无容器资源限制** | 长回答被 CF 掐断;重新部署即断 API;异常时整机 OOM | — |

## 14. 优化优先级

**P0(严重影响性能/稳定性/安全, 立即做)**
1. 消除事件循环阻塞:所有 SQLite/磁盘/Chroma/嵌入调用 → `asyncio.to_thread`(专用 bounded executor);knowledge 入库改后台任务(file status: temp→indexing→knowledge, 失败可重试)
2. Provider 层连接复用:模块级共享 `httpx.AsyncClient`(keep-alive, 代理统一注入);GLM 流式桥接改用独立 executor 或换异步实现;流式超时与 REQUEST_TIMEOUT 统一分级
3. 上传安全与内存:先查 Content-Length, 分块流式落盘;文件名 `Path(name).name` sanitize(修 S1/S3)
4. ai-service 端口收回内网(删除 ports, 走 snhgn-network;修 S2)
5. SSE 心跳(15s `: ping`)+ compose 挂载正确 Caddyfile

**P1(明显影响响应速度/资源)**
6. chat/stream 统一 ChatPipeline(一次实现, 两端复用);检索步骤并行化(`asyncio.gather` memory/rag/files/schedule)
7. auth 用户信息 TTL 缓存(60s, 写穿透)+ 登录限流(内存令牌桶)
8. 视觉链接入 Context Engine(带图也带历史)
9. RAG:score 阈值 + 查询 LRU 缓存(128 条, TTL 10min);chunk 升级为段落感知切分
10. 容器 mem_limit/cpus + healthcheck;uvicorn `--limit-concurrency`;conversations 复合索引与保留策略

**P2(架构质量)**
11. main.py 拆分(routers/ + services/chat_pipeline + providers + rag + memory);memory_enabled 拆成两个开关(memory / history)
12. 删除冗余(schedule-pipeline、根目录两套 solver、旧 Caddyfile、每服务 compose、.deploy-staging)
13. 会话历史 API 分页 + 前端补加载

**P3(可维护性)**
14. 补测试(auth/conversation 隔离/fallback/pipeline);/api/conversations/{sid} 返回 total_count;文档更新

## 15. 推荐新架构(目标:低资源、异步、缓存、按需加载;不新增重型服务)

```
                     ┌────────────────────────────────────────────┐
Browser ─► CF ─► Caddy ─► gateway(认证+代理+课表)                     │
                     │   ├─ 用户缓存(TTL 60s) + 登录限流             │
                     │   └─ httpx 共享池 ──► ai-service(仅内网)      │
                     └────────────────────────────────────────────┘
ai-service(单进程多协程, 全异步边界):
  routers/  chat.py files.py knowledge.py memory.py settings.py admin.py
  services/chat_pipeline.py   ← 唯一的组装实现(stream 与非流式共用)
      并行采集: gather(memory_cache, rag_search, files, schedule) → ContextBuilder
      → provider_manager(共享 AsyncClient 池 + 简单健康计数/半开熔断 + 超时分级)
      → SSE writer(心跳/背压) → 完成后 defer(save + title + rolling, 信号量限流)
  infra/blocking.py  专用 ThreadPoolExecutor(大小=4)承载所有同步 IO/嵌入
  infra/cache.py     进程内 TTLCache(settings/memories/RAG 结果)
  rag/    入库改 BackgroundTask(状态机) + 阈值过滤 + 结果缓存
scheduler: 保留(任务面独立, 资源占用小);compose 加 limit
存储: 维持 SQLite×N(不引入 Redis/PG——机器资源与收益不匹配)
      + 复合索引 + 对话保留策略(如 180 天)
删除: schedule-pipeline、根目录 captcha_solver/course_app、旧 Caddyfile、
      每服务 compose、.deploy-staging
```

**关键决策理由:** ①不合并 gateway/ai-service——独立扩缩与信任边界清晰, 合并收益小;②不引入 Redis——TTLCache+SQLite 足够, 3.7GB 机器省一个进程;③不换 Chroma——懒加载后可接受, 换 sqlite-vec 需重嵌入全库, 收益/风险比低(列为 P3 可选);④不引入 MQ——asyncio.Queue+Semaphore 即可覆盖总结/入库异步化。

## 16. 预计优化收益(重构前 vs 后)

| 指标 | 当前(估算) | 重构后目标 | 手段 |
|---|---|---|---|
| 事件循环单次最长阻塞 | 50ms~分钟(嵌入/入库) | <5ms | P0-1 |
| TTFT(Gemini) | +1~3s 握手 | ≈首包即流 | P0-2 |
| 并发流式能力 | ~7 路 | 30+ 路(受限于上游 API) | P0-2/P0-1 |
| 用户间干扰 | 强(A 冻结 B) | 无 | P0-1 |
| 每请求 SQLite 查询 | 9 | 5(auth/settings/memories 走缓存) | P1-7/缓存 |
| 上传内存峰值 | 2×文件大小 | ~1MB 常量 | P0-3 |
| Token/请求(记忆开) | +~200 固定注入 | 条件注入 | P1-9 可选 |
| 安全 | 2 高危(S1/S2) | 0 已知高危 | P0-3/4 |
| 部署可重现性 | compose 挂错 Caddyfile | 单一事实源 | P0-5 |
| 代码 | 1569 行单体+200 行重复 | 分层 ≤300 行/文件 | P2-11 |

---

## 附:本次审计覆盖的代码范围

ai-service(main/config/context×3/memory×2/providers×4/rag×4/course_tools, 1569+行全读)、gateway(main/auth/config + routers×6 + schedule×9)、scheduler(main/core/executor/scripts_db/scripts_runner/routers)、ai-notice-monitor(main/ai_summary 概览)、compose×5、Dockerfile×3、Caddyfile×3、前端 api.ts/api/scripts.ts/AiView.vue API 面、ai-service tests。

