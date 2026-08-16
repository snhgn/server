# AI Assistant Context Engine 优化（第二阶段）

> 目标：在不破坏现有功能（Streaming / Memory / RAG / 多用户隔离 / GLM / Gemini）的前提下，
> 建立独立的 Context Manager / Context Engine，使长对话不再无限增加 Token、延迟与服务器负载。
>
> 文档结构：阶段一审计报告 → 阶段二修改方案 → 阶段三实施记录。

---

## 阶段一：代码审计报告

审计范围：`packages/ai-service`（FastAPI 单体，端口 8000，gateway 转发 `/api/ai/*`）。

### 1. 当前 Conversation 流程

- 入口：`POST /api/chat`（一次性）与 `POST /api/chat/stream`（SSE）。
- 身份：gateway 注入 `X-User-Id / X-Username / X-Role` 头（`gateway/app/routers/ai.py`），
  ai-service 每个接口从 Header 取 `x_user_id`，所有查询绑定 `user_id`。
- 会话：`session_id`（客户端传入或自动生成 8 位 uuid）；历史存 SQLite `conversations` 表
  （user_id, session_id, message, response），按轮保存（1 轮 = 1 user + 1 assistant）。
- 元信息：`conversation_meta` 表（user_id, session_id, title, summary, keywords,
  rolling_summary, created_at, updated_at）。
- 连续对话：`_build_chat_messages()` 取最近 `CONTEXT_MAX_ROUNDS=30` 轮 →
  组装 messages → provider.chat / chat_stream → 完成后 `conversation_store.add` 保存。

### 2. 当前 Context 构建方式

- `system_parts`：长期记忆（可选）+ RAG（可选）+ 文件附件（可选）+ 课表（可选），
  全部用 `"\n\n"` join 成一个 system 字符串；滚动摘要（若有）insert 到最前面。
- messages：最近 30 轮历史（user/assistant 展开）+ 当前用户消息。
- **没有 Token 统计，没有预算控制**：窗口只按"轮数"截断（30 轮），不按 Token。
  30 轮里如果有几条超长消息（如代码），会一次性把完整内容发给模型，
  可能超出模型上下文窗口导致 API 报错；也没有"超预算时按优先级压缩"的机制。
- 文件文本内容按 12000 字符截断（已有兜底），课表按消息意图注入（`course_tools.py`）。

### 3. 当前 Memory 调用方式

- `MemoryManager`：SQLite `memories` 表（user_id, category, key, value），
  UNIQUE(user_id, category, key)，所有查询带 `user_id` 过滤 ✓（多用户隔离正确）。
- 调用时机：仅当客户端传 `use_memory=true` 且用户开启 `memory_enabled` 时，
  `get_context(user_id)` 把该用户全部记忆格式化为文本注入 system。
- **没有后端自动判断**：是否带记忆完全取决于前端 flag。
- 记忆写入：AI 回答中嵌入 `<memory category key>value</memory>` 隐藏标签，
  ai-service 解析后写库（`_apply_memory_ops`），流式场景用 `MemoryTagFilter` 跨 chunk 过滤。
- 记忆内容无长度上限（记忆多了可能很长）。

### 4. 当前 RAG 调用方式

- `RAGRetriever` / `VectorStore`：Chroma 持久化 + ONNX MiniLM 本地 Embedding（首次使用懒加载）。
- 调用时机：仅当客户端传 `use_rag=true` 时 `rag.search(message, user_id)`；
  **没有后端判断**，闲聊也会检索（前端开着 flag 时）。
- Top-K：`settings.RAG_TOP_K=3` ✓（不会把整个知识库塞进 prompt）。
- 隔离：Chroma metadata 带 `user_id`，查询 `where={"user_id": ...}` ✓。
- 嵌入已持久化在 Chroma，不会每次请求重新 Embedding 整个知识库 ✓。
- 每次检索会对查询文本做一次 ONNX 推理（CPU，约几十毫秒），属于合理开销。

### 5. 当前 Token 管理方式

- **完全没有 Token 管理**：无估算、无预算、无模型窗口注册表。
- 仅设置各模型 `max_tokens` 输出上限（`MAX_TOKENS_BY_MODEL`，如 glm-4.7-flash=65536）。
- 输入侧无任何限制，这是当前最大的隐患（长对话 + 大文件 → 超窗口报错）。

### 6. 当前数据库结构

| 表 | 关键字段 | 说明 |
|---|---|---|
| memories | user_id, category, key, value | 长期记忆，user 隔离 ✓ |
| conversations | user_id, session_id, message, response, created_at | 对话轮次 |
| conversation_meta | user_id, session_id, title, summary, keywords, rolling_summary, created_at, updated_at | 会话元信息；已含标题/摘要/滚动摘要 |
| user_settings | user_id, memory_enabled, ai_provider | 用户偏好 |
| user_files | user_id, filename, file_type, storage_path, status | 上传文件 |

- 规格书建议的 `conversations.summary / summary_updated_at` 已由 `conversation_meta`
  （title/summary/rolling_summary/updated_at）覆盖 → **复用，不重复建表**。
- 自动标题：**已存在**（第一阶段实现）——`summarize_session()` 在首个问答后异步生成
  title/summary/keywords，不阻塞回答；另有手动触发接口 `PATCH /api/conversations/{id}/summarize`。

### 7. 当前存在的问题

| 级别 | 问题 |
|---|---|
| P1 | 无 Token 预算：30 轮完整历史可能超出模型窗口 → API 报错，而不是优雅压缩 |
| P1 | 流式中途失败：已产出的部分 token 在"全部 provider 失败"时会被当作正常回答保存进历史（违反 §十） |
| P1 | 流式跨 provider 回退：A provider 输出一半后失败，回退到 B provider 时输出拼接混乱 |
| P2 | Memory/RAG 完全依赖前端 flag，无后端按消息判断（§六/§七） |
| P2 | 无上下文用量日志（§十三）：不记录 history/memory/RAG/总输入 token |
| P2 | 滚动摘要触发只按轮数（>30 轮），无 Token 阈值（§四） |
| P2 | 记忆内容无长度控制，大量记忆可能挤占上下文 |
| P3 | 无模型上下文窗口注册表（§九）；GLM/Gemini 窗口差异未建模 |
| P3 | `GET /api/conversations/{id}` 只返回最近 30 轮（显示数据被截断，与聊天窗口无关） |

安全审计结论：Memory / RAG / Conversation / Files 全部查询均绑定 `user_id`；
Admin 接口校验 `X-Role=admin`（由 gateway 注入）；日志不包含 API Key/密码/消息内容 ✓。
无越权读取问题。

---

## 阶段二：修改方案

### 设计：新建 `app/context/` 包（独立 Context Engine）

```
app/context/
├── __init__.py
├── tokens.py     # 轻量 Token 估算（无外部依赖，CJK 感知）
├── models.py     # 模型上下文窗口注册表（GLM/Gemini + 环境变量覆盖）
└── builder.py    # ContextBuilder：按优先级组装 + Token 预算内压缩
```

### 1. Token 预算（§九）

- `budget = min(模型上下文窗口, CONTEXT_MAX_TOKENS 硬上限) - 预留输出 - 安全余量`
- 预留输出：默认取该 provider 主文本模型的 `max_tokens`（GLM 查 `MAX_TOKENS_BY_MODEL`，
  Gemini 用 `GEMINI_MAX_OUTPUT_TOKENS`）；可用 `CONTEXT_OUTPUT_RESERVE_TOKENS` 覆盖。
- 安全余量 `CONTEXT_SAFETY_MARGIN=2048`：覆盖估算误差。
- 模型窗口注册表：glm-4.7-flash=200K、glm-4-flash-250414=128K、视觉模型=128K、
  Gemini 3.x/2.5=1M；未知模型回落 `CONTEXT_DEFAULT_WINDOW=128K`；
  可用环境变量 `MODEL_CONTEXT_WINDOW_OVERRIDES`（JSON）覆盖。
- Token 估算：CJK 字符按 1 字 ≈ 1 token，其余按 4 字符 ≈ 1 token（无 tiktoken 依赖，
  纯启发式 + 安全余量）。

### 2. Context 组装与压缩优先级（§二/§八）

组装顺序（优先级从高到低，超预算时从低到高丢弃）：

1. System Prompt（`AI_SYSTEM_PROMPT`，默认空 = 保持现状；永不移除）
2. 用户长期 Memory（含记忆写入权限说明）
3. Conversation Summary（rolling_summary，DB 已缓存 ✓）
4. 文件 / 课表等当前消息相关上下文
5. 最近消息（短期上下文，从最旧轮开始丢）
6. RAG Context（最易被压缩）
7. 当前用户消息（永不移除）

- 短期上下文默认 15 轮（30 条消息），可配置 `CONTEXT_MAX_HISTORY_ROUNDS`。
- 若用户消息本身超过预算 → 只保留 System + 用户消息并告警（模型报错属预期）。

### 3. Summary 生成策略（§三/§四）

- 复用现有 `rolling_summary`（DB 缓存 ✓）+ `_rolling_compress`（异步、不阻塞主回答）。
- 触发条件升级为两类：**轮数超窗**（> CONTEXT_MAX_HISTORY_ROUNDS）或
  **历史 Token 超阈值**（`CONTEXT_SUMMARY_TRIGGER_TOKENS=24000`）。
- 仍不每条消息生成摘要；用户主动总结走现有 `/summarize` 接口 ✓。
- 摘要并发上限沿用现有 Semaphore(4) ✓。

### 4. Memory / RAG 自动判断（§六/§七）

- 新增启发式判断（后端）：`CONTEXT_AUTO_MEMORY=True`、`CONTEXT_AUTO_RAG=True` 时，
  即使客户端 flag 为 false，命中关键词也自动携带记忆 / 检索知识库；
  客户端 flag 仍优先生效（向后兼容）。两个开关可一键回到旧行为。
- Memory：关键词如"记住/记得/上次/我说过/我叫/我喜欢/偏好/习惯/别忘…"。
- RAG：关键词如"知识库/资料/文档/项目/分析/总结/根据/搜索/查找/查询/检索/报告…"；
  Top-K 沿用 `RAG_TOP_K=3`，不把知识库全量塞入。
- 记忆内容由 ContextBuilder 纳入预算，超预算自动丢弃（不影响 System 与用户消息）。

### 5. Streaming 兼容与失败处理（§十）

- 流程保持：Load Context → Call Provider → Stream Response → 完整结束 → 保存。
- **修复**：某 provider 已产出部分 token 后失败 → 立即中断（不再回退到下一个 provider，
  避免输出拼接混乱），发送 `error` 事件，**不保存不完整回答**，不执行记忆写回；
  仅在"完全成功"后才保存历史 / 应用记忆标签 / 生成标题。
- 零产出失败仍按原逻辑回退下一个 provider。

### 6. 日志（§十三）

每次请求记录：provider、user_id、session_id、耗时、输入总 token、
system/memory/summary/rag/files/history/user_msg 分项 token、输出估算 token、是否发生压缩。
**绝不记录**消息内容、API Key、密码等敏感信息（沿用现有日志规范）。

### 7. 不破坏项确认（§十五/十六）

| 能力 | 影响评估 |
|---|---|
| Streaming | SSE 事件结构不变（status/token/complete/error）；仅新增"中断 error"场景 |
| Memory | 读/写/隔离逻辑不动；仅在预算内组装，多用户隔离不变 |
| RAG | Chroma 隔离不变；仅增加自动判断开关（可关） |
| 多用户隔离 | 所有查询仍绑定 user_id；builder 纯函数不接触数据层 |
| GLM / Gemini | Provider 接口不变，仅新增两个只读属性 |
| 自动标题 | 已存在，不动 |
| 数据库 | 不加表；复用 conversation_meta（含自动补列逻辑，向后兼容旧库） |

---

## 阶段三：实施记录

### 变更文件清单

| 文件 | 变更 |
|---|---|
| `app/context/__init__.py` | 新增：Context Engine 包 |
| `app/context/tokens.py` | 新增：轻量 Token 估算（CJK 感知，无外部依赖） |
| `app/context/models.py` | 新增：模型上下文窗口注册表（GLM/Gemini + `MODEL_CONTEXT_WINDOW_OVERRIDES` 覆盖） |
| `app/context/builder.py` | 新增：`ContextBuilder` 按优先级组装 + Token 预算内压缩 + `ContextUsage` 统计 |
| `app/config.py` | 新增 Context Engine 配置段（窗口/余量/预留输出/历史轮数/摘要阈值/自动判断开关等） |
| `app/providers/base.py` | 新增只读属性 `primary_text_model` / `max_output_tokens` |
| `app/providers/glm.py` | 实现上述属性（主文本模型 + 模型输出上限） |
| `app/providers/gemini.py` | 实现上述属性（`GEMINI_MAX_OUTPUT_TOKENS`） |
| `app/providers/siliconflow.py` | 实现 `primary_text_model` |
| `app/main.py` | `_build_context()` 接入 ContextBuilder；Memory/RAG 自动判断（`_needs_memory`/`_needs_rag`）；流式中断不保存不完整回答；`_log_chat_usage()` 上下文用量日志；`GET /api/conversations/{id}` 返回全量历史 |
| `app/memory/manager.py` | `get_history` 支持 `limit=None`（全量） |
| `.env.example` | 补充 Context Engine 配置说明 |
| `tests/test_context_engine.py` | 新增单元测试（估算器 + Builder 压缩逻辑） |

### 验证结果

- 全部改动文件 `py_compile` 通过（含 app 内全部模块）。
- `tests/test_context_engine.py` 7 个用例全部通过：
  优先级顺序（base 在前 / rag 在后）、用户消息与基础 System 永不移除、
  超预算先丢 RAG 再截断最旧历史、极端压缩只留 base+用户消息、历史轮数上限、消息展开。
- 无数据库结构变更（复用 `conversation_meta`，含自动补列逻辑，兼容旧库）。
- 兼容性确认：Provider 接口签名不变（仅新增属性）；SSE 事件结构不变；
  客户端 `use_memory`/`use_rag` flag 优先生效；`CONTEXT_AUTO_MEMORY`/`CONTEXT_AUTO_RAG`
  可一键关闭自动判断回到旧行为。

### 行为变更提示（部署前知悉）

1. 短期上下文默认 30 轮 → `CONTEXT_MAX_HISTORY_ROUNDS=15`（更省 token/延迟，可调回）。
2. `GET /api/conversations/{id}` 现在返回全量历史（原先截断 30 轮）。
3. 后端自动判断：未开启 flag 但消息命中关键词时也会携带记忆/检索知识库（可关闭）。
4. 流式中断（已产出部分内容后失败）不再回退到其他 provider，直接返回 error 事件且不保存。
5. 日志新增 `input_tokens/system/memory/summary/rag/history/output_est/compressed` 等字段。
