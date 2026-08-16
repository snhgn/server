# Assistant 前端重构：DeepSeek Harness 设计语言（第三/四/五阶段）

> 目标：保留当前 ChatGPT 式聊天结构（左侧 Conversation Sidebar + 中间 Chat + 底部 Input），
> 以 DeepSeek Harness 官方 Web UI 为视觉参考做"皮肤级"重构。
> 参考来源：GitHub `deepseek-ai/deepseek-harness`（master 分支，MIT），
> 关键包：`packages/client/ui-theme`（design tokens）、`ui-conversation`（chat/composer）、
> `ui-sidebar`、`ui-primitives`（Button/Input/Menu/CodeBlock）、`ui-model-selection`、
> `ui-attachment`。本仓库未包含前端源码，本次依据官方源码逐文件提取设计语言。

---

## 阶段二：当前前端审计

项目：`D:\project\snhgn.me`（Vue 3 + Vite + Tailwind 4 + TypeScript），路由 `/ai` 全屏。

| 文件 | 现状 |
|---|---|
| `AiView.vue` | 页面编排：SSE 流式发送/中断、会话加载/切换/新建、文件上传、知识库弹窗、provider 偏好持久化 |
| `AssistantSidebar.vue` | 280px 侧栏（桌面固定/移动抽屉），New Chat、会话列表、用户卡片、退出 |
| `ConversationList.vue` | 会话列表（标题/摘要/关键词/时间/条数），选中态=深色（slate-900） |
| `ChatWindow.vue` | 顶栏状态 pills（Memory/Knowledge/Provider）+ 欢迎页（渐变大字 + 4 张能力卡片）+ 消息流 |
| `MessageBubble.vue` | 用户=深色气泡（slate-900 白字）；AI=渐变"A"头像 + Markdown（marked + highlight.js，深色代码块） |
| `ChatInput.vue` | 顶部选项行（provider 单选/记忆/RAG 开关）+ 附件卡片 + 输入框（圆角 16，indigo focus）+ 发送/停止 |
| `api.ts` | fetch 封装 + SSE 流式解析（status/token/complete/error） |

当前问题（相对目标）：
1. 视觉：indigo/violet/fuchsia 渐变 + slate 体系，与 Harness 的白/黑/蓝灰语言不一致；
   用户气泡深色、AI 带渐变头像，气泡感强。
2. 交互缺失：会话无删除/重命名/搜索；列表无日期分组；无 hover 操作。
3. 代码块深色主题；无 LaTeX；无复制按钮。
4. 输入框为内嵌样式，非 Harness 的悬浮胶囊卡片。
5. 后端无会话删除/重命名接口（需补充，属扩展而非重构）。

## 阶段三：设计对比（当前 vs DeepSeek Harness 实际源码）

| 维度 | 当前 Assistant | DeepSeek Harness（源码提取） |
|---|---|---|
| 主色 | indigo-600 #4F46E5 系列 | 品牌=墨黑 #0F1115（主按钮）；业务蓝 #4176E6（发送/链接/激活态）；deepseek-100 #E4EDFD（选中底） |
| 中性色 | slate 系列 | bluish 系列：bg #FFFFFF、surface #F9FAFB/#F5F6F7、border rgba(0,0,0,.04~.16)、文字 #0F1115/#61666B/#81858C/#ADB2B8 |
| 用户消息 | 深色大块（slate-900 白字） | 右侧浅蓝胶囊 bubble：bg #EDF3FE、r22、10px16px、16/24 |
| AI 消息 | 渐变头像 + 正文 | 无头像叙述式：16/28、块间距 16、下方 28px 图标操作行（hover 淡显） |
| 输入框 | 内嵌圆角框 + 上方选项行 | 悬浮胶囊卡片：r22、border l2、shadow、上 10 下 8、textarea 16/24；左下 28px 圆形 attach（#F5F6F7）、右下 34px 蓝色发送圆 |
| 模型选择 | 单选小标签 | 28px chip 触发器 + r12 浮层菜单（选项 r10 h38、右侧 check） |
| 代码块 | 深色 + 无复制 | 浅色：bg #F9FAFB、r12、banner（语言 + copy）、pre 16px padding |
| 按钮 | 彩色/渐变 | 胶囊 r18(h36)/r14(h28)；primary=黑底白字，ghost=透明+hover 6% 黑 |
| 侧栏 | 白底 + 深色选中 | fill #F9FAFB；New Session h38 r12 白底 1px 边；选中 #EBEEF2 + 蓝 accent；hover #F1F3F5 |
| 状态 | emoji/彩色 pills | 转轮状态条：蓝渐变 shimmer 文字（deepseek 500→200），26px 行 |
| 空状态 | 渐变大字 + 卡片 | 鱼 Logo + 标题 + 居中 composer + 底部蓝光晕 |
| 会话列表 | 平铺 | 日期分组（Today/Yesterday/...）、hover 行操作 |
| 圆角体系 | 10~16 | 8(输入)/12(代码块/菜单/New Chat)/18-22(按钮/输入卡/气泡) |
| 阴影 | shadow-sm/md | lv2（输入卡/悬浮按钮）、lv3（菜单浮层） |

## 阶段四：重构方案

1. **Design tokens**（`style.css` @theme）：引入 bluish 中性色、deepseek 蓝、墨黑品牌色、边框/阴影层级。
2. **AiView**：逻辑不动；新增会话 删除/重命名/搜索 状态与处理；侧栏/聊天区重构编排；知识库弹窗改 Harness 风格。
3. **Sidebar**：Harness 风格（浅灰底、New Chat 胶囊、搜索框、日期分组列表、hover 删除/重命名、用户脚部）。
4. **ChatWindow**：精简顶栏（品牌 + 极简状态 chips）；欢迎页改为 小标题 + 快捷入口 chips + 蓝光晕；消息流 16px 节奏。
5. **MessageBubble**：用户=浅蓝胶囊（右对齐）；AI=无头像叙述式 + 轻量 Markdown（浅色代码块 + banner + copy）+ 复制按钮 + 来源折叠 + LaTeX(katex)。
6. **ChatInput**：Harness composer（悬浮胶囊、attach 圆、模型选择浮层菜单、Memory/RAG chips、蓝色发送圆、附件 rail、拖拽遮罩）。
7. **后端扩展**（ai-service）：`DELETE /api/conversations/{id}`、`PATCH /api/conversations/{id}`（重命名），均绑定 user_id（多用户隔离不变）。
8. **搜索**：前端过滤当前用户自己的会话列表（数据已按 user_id 隔离）。
9. 不改：Streaming SSE 协议、文件上传接口、记忆/RAG、provider 逻辑。

## 阶段五：实施与验证

### 变更文件清单

**前端（D:\project\snhgn.me）**
| 文件 | 变更 |
|---|---|
| `src/style.css` | 新增 Harness 设计 tokens（bluish 中性色 / deepseek 蓝 / 墨黑品牌 / 阴影层级 / dsw-scroll 滚动条） |
| `src/views/AiView.vue` | 接入会话搜索/重命名/删除；移动端顶栏与知识库弹窗改 Harness 风格；ChatInput 空状态 hero 光晕 |
| `src/components/assistant/AssistantSidebar.vue` | Harness 侧栏：浅灰底、Logo 动画品牌区、搜索框、New Chat 胶囊（h38/r12）、hover 操作、用户脚部 |
| `src/components/assistant/ConversationList.vue` | 日期分组（今天/昨天/7 天内/更早）、搜索过滤、行内重命名（Enter/Esc）、两步删除确认、选中蓝 accent |
| `src/components/assistant/ChatWindow.vue` | 精简顶栏（品牌 + 极简状态点）、欢迎页（小标识 + 中性快捷入口 chips）、消息流 16px 节奏 |
| `src/components/assistant/MessageBubble.vue` | 用户=右侧浅蓝胶囊（#EDF3FE/r22）；AI=无头像叙述式 + 浅色代码块（banner 语言+复制）+ LaTeX(katex 扩展) + 复制按钮 + 来源折叠 + shimmer 状态 |
| `src/components/assistant/ChatInput.vue` | Harness composer：r22 悬浮卡（border l2 + shadow lv2）、28px attach 圆、Memory/RAG chips、模型选择浮层菜单、34px 蓝色发送圆、附件 rail、拖拽遮罩、hero 蓝光晕 |
| `src/api.ts` | 新增 `api.patch` |
| `package.json` | 新增依赖 `katex` |

**后端（packages/ai-service，仅扩展不改架构）**
| 文件 | 变更 |
|---|---|
| `app/memory/manager.py` | `ConversationStore.delete_session` / `rename_session`（均绑定 user_id） |
| `app/main.py` | `DELETE /api/conversations/{id}`、`PATCH /api/conversations/{id}`（重命名），404 处理 |

### 保留项（未改动）
Streaming SSE 协议与事件结构、文件上传/知识库接口、Memory/RAG、GLM/Gemini provider、
多用户隔离（所有新接口均按 `X-User-Id` 校验归属）、自动标题（后端已有，前端列表刷新展示）。

### 验证结果
- 前端 `npm run build`（vue-tsc + vite build）通过。
- highlight.js 按需注册常用语言，AiView 分包体积显著下降。
- 后端改动文件 `py_compile` 通过；Context Engine 单元测试不受影响。
- 会话删除/重命名接口按 user_id 过滤：User A 无法删除/重命名 User B 的会话（SQL WHERE user_id）。

### 设计来源（MIT）
DeepSeek Harness 官方仓库（deepseek-ai/deepseek-harness, master）：
`packages/client/ui-theme/src/styles/design-platform.css`（color/border/shadow tokens）、
`ui-conversation/src/client/skeleton/InputBar.module.css`（composer 几何）、
`ui-conversation/src/client/chat/MessageItem.module.css`（用户气泡）、
`ui-conversation/src/client/chat/AssistantMarkdown.module.css`（叙述排版）、
`ui-conversation/src/client/skeleton/ConversationRoot.module.css`（列宽 748/780）、
`ui-primitives/src/markdown/CodeBlock.module.css`（代码块）、
`ui-sidebar/src/client/SidebarRoot.module.css`（侧栏）、
`ui-model-selection/src/client/ModelSelect.module.css`（模型菜单）、
`ui-conversation/src/client/chat/ChatView.module.css`（turnStatus shimmer）。

