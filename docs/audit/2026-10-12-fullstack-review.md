# 全栈审查报告（前端审查助手 + 后端排查助手）

- 日期：2026-10-12
- 范围：`web/`（Vue 3 + Vite + TS 前端）与 `packages/{gateway,ai-service,scheduler}`（FastAPI 后端）+ `Caddyfile` / `docker-compose.yml`
- 深度：完整审查（全量页面与路由登记 + 逐项复现 + 修复 + 复检）
- 访问方式：源码 + 本地构建/类型检查/单元测试（未连接生产服务器，故线上运行态未实测）

## 一、基线与机械校验

| 项目 | 命令 | 结果 |
|---|---|---|
| 前端类型检查 | `vue-tsc --noEmit` | 通过 |
| 前端构建 | `vite build` | 通过（121 modules，~0.9s） |
| 后端单元测试 | `unittest discover -s tests` | 143 通过（新增 6） |
| 页面/路由登记 | 12 个 view + 全部 `/api/*` 路由 | 12 页面 / 6 网关路由组 |

初始基线是「干净」的：类型检查、构建、既有 137 个测试全部通过。因此以下问题都不是编译期能发现的，全部靠人工核对 + 脚本复现确认。

## 二、发现与处置

### F1（P1）设置页读写全部 404 —— 已修复

- 位置：`web/src/views/SettingsView.vue:15,28`
- 证据：`GET/PUT /api/settings → 404`；而 `/api/ai/settings → 401`（存在，需鉴权）
- 根因：设置能力由 ai-service 承载，网关侧统一挂在 `/api/ai` 前缀下；SettingsView 写成了 `/api/settings`，网关无此路由
- 影响：进入设置页读不到服务端真实值（catch 静默 → 开关显示为默认开启）；保存必定失败且无提示（未捕获的 Promise rejection）
- 修复：改用 `/api/ai/settings`（与 AiView 一致），并为读取/保存失败补充可见的错误文案
- 复验：`tests/test_route_contract.py`（扫描前端源码全部 `/api/*` 字面量，逐一匹配网关路由）

### F2（P1）课表页心跳 / 键盘 / 拖放全部失效 —— 已修复

- 位置：`web/src/views/ScheduleView.vue` `onMounted`（原 742–898 行）
- 证据：`onMounted` 内存在 7 处提前 `return`（第 758/786/800/810/854/878/880 行），而 `setInterval`（889）与 5 个 `addEventListener`（893–897）写在函数尾部
- 影响：只要命中任意一条正常分支（本地缓存 / URL 带学号 / 已保存凭据），这些注册就永不执行 ——
  1. `currentTime` 冻结在挂载时刻，"上课中 / 下一节 / 倒计时"不再更新；
  2. Esc 无法关闭任何弹窗（详情 / 周选择 / 自定义日程 / 工具箱 / 图片查看器），键盘用户被困；
  3. 拖拽导入背景图完全无响应
- 修复：抽出 `startHeartbeat()` / `registerWindowListeners()`，在所有数据分支之前注册
- 复验：`web/scripts/check-onmounted-early-return.cjs`（括号感知的控制流扫描，全量扫 12 个 view）

### F3（P1，安全）AI 消息区存储型 XSS —— 已修复

- 位置：`web/src/components/assistant/MessageBubble.vue`（`v-html="html"`）
- 证据：`marked.parse('<img src=x onerror="alert(1)>')` 原样输出，前端无净化直接注入 DOM
- 可达路径：AI 回答 / RAG 知识库片段（用户可上传 .md/.html）／历史会话。`<script>` 不会执行，但 `<img onerror>` 会；同源请求携带 Session Cookie，可代用户调用任意 `/api/*`（含 admin 接口）
- 修复：
  1. `renderer.html` → 原始 HTML 一律转义为文本
  2. `renderer.link` / `renderer.image` → 协议白名单（http/https/mailto/站内路径/内联图片 data URI），拒绝 `javascript:`、`data:text/html`，并先剔除控制字符防 `java\nscript:` 绕过
  3. 代码围栏的 `lang` 一并转义（原本可被注入 HTML）
  4. `html` computed 的 catch 兜底同样转义（原实现直接 `v-html` 原文，是第二条 XSS 通路）
- 复验：`web/scripts/check-markdown-sanitize.cjs`（直接取组件真实源码片段转译后运行，7 条恶意输入全部净化）

### F4（P2）代码围栏未标语言 → 整条消息退回纯文本 —— 已修复（F3 排查中连带发现）

- 位置：`MessageBubble.vue` `renderer.code`
- 证据：项目用 `highlight.js/lib/core`，未注册 `plaintext`；`hljs.highlight(text, {language:'plaintext'})` 抛 `Unknown language: "plaintext"`
- 影响：AI 回答里只要出现一个无语言标注的 ``` 代码块，`marked.parse` 整体抛错 → catch 返回 markdown 源码 → 整条消息不渲染
- 修复：未知语言不走 hljs，直接输出转义后的纯文本

### F5（P3）模型降级提示未接线 —— 已修复

- 证据：后端 SSE `complete` 事件与 `/api/chat` 都返回 `fallback_from`，前端 `AiView` 从不读取，`providerFallback` 恒为 `false`；且 `ChatWindow` / `ChatInput` 收到该 prop 后也从未渲染
- 修复：`onComplete` 消费 `fallback_from`；`ChatWindow` 顶部遥测区新增 `Fallback: <provider>` 徽标

### B1（P2，后端）登录限流表可被用户名枚举撑爆 —— 已修复

- 位置：`packages/gateway/app/routers/auth.py` `_login_fails`
- 证据：复现脚本实测 5000 个不同用户名各失败 1 次 → 5000 条常驻，约 4.2MB；这些键永远不会被 `_login_blocked` 查询到，因此永不清理。gateway `mem_limit=384m`
- 修复：写入前检查容量（上限 5000），超限先清理过期项、仍超限则整体清空；查询时若窗口内已无有效记录则连带删除条目
- 复验：`tests/test_login_rate_limit.py`（4 个用例，含 20000 次枚举下的有界性断言）

### F6（P1）课表横滑时课程卡片盖住吸顶“节次时间”列 —— 已修复（用户反馈，二轮审查）

- 位置：`web/src/views/ScheduleView.vue` 桌面/整周课表格（吸顶时间列 + 课程卡片层级）
- 复现证据（本地 dev server + 无头 Chromium 实测，390×844 视口）：
  1. 课表容器 `overflow-x-auto`（`min-w-[580px] sm:min-w-[800px]`），7 天视图在手机宽度下必然可横滑；且 `scrollToToday()` 在进入整周视图时会**自动横滑到当天列**（今天非周一时 scrollLeft > 0），用户不手动滑也会触发；
  2. 时间列单元格为 `sticky left-0 z-10`，课程卡片为 `relative z-10`（冲突堆叠时 `zIndex: 10 + stackIndex`）——两者 z-index 相同，卡片在 DOM 中更靠后 → **画在时间列上面**；
  3. 实测 `scrollLeft=200` 时“数据结构 / 物理实验”卡片与“1-2 / 3-4 / 5”时间标签重叠 40px（整列宽），`elementFromPoint` 命中测试点中的是卡片而非时间标签 → 时间被完全遮住
- 影响：移动端整周视图（以及窄窗口桌面端）一看课表，节次和时间被课程卡片盖住，无法辨认当前是第几节课
- 修复：
  1. 吸顶“节次”表头单元格与 7 个时间标签单元格统一提升到 `z-30`；
  2. 课程卡片冲突堆叠 z-index 加上限 `10 + Math.min(stackIndex, 19)`（最高 29），从机制上保证任何数据量下卡片都不可能盖过吸顶时间列
- 复验：
  - 浏览器实测 7 天 / 5 天视图、scrollLeft ∈ {0, 100, 120, 200, 300, 400}：时间列被卡片遮挡数均为 **0/8**（修复前为 3/8 起）
  - App 专属模式课表格（无横滑）：0 重叠，冲突卡片堆叠正常（z=10/11）
  - `web/scripts/check-schedule-sticky-zindex.cjs`（静态不变量检查，已用回归副本验证能抓到此问题）

## 三、已检查但未改（保留设计意图 / 需产品确认）

| 项 | 判断 |
|---|---|
| `GET /api/schedule/query`、`/view/{user_id}`、`POST /share/create` 免鉴权 | 与"学号/邀请码即可看课表"的分享设计一致；但 `share/create` 可让他人 `regenerate` 掉受害者原有邀请码（可用性风险）。改鉴权属产品决策，未动 |
| `dist/` 内 `sw.js`、`workbox-*.js`、`manifest.webmanifest` 为残留死文件 | `index.html` 未引用、无 PWA 插件；`main.ts` 与 `index.html` 反而主动注销 SW。建议后续清理，不影响功能 |
| `ChatWindow` 监听 `scrollHeight` 自动滚到底 | 流式输出时用户上翻会被拉回。属体验取舍，未动 |
| 背景图 dataURL 存 localStorage | 已压缩到 1920px/JPEG 0.86，配额风险可控；超限时的报错文案不友好，属 P3 文案问题 |

## 四、复检结果

| 检查 | 结果 |
|---|---|
| `vue-tsc --noEmit` | 通过 |
| `vite build` | 通过 |
| `unittest discover -s tests` | 143 通过 |
| onMounted 早退扫描（12 个 view） | 0 命中 |
| markdown 净化验证（7 条恶意输入） | 全部净化 |
| 前端 API 路径 ↔ 网关路由契约 | 全部匹配 |
| 课表时间列层级（横滑 5 个位置 × 7天/5天视图） | 遮挡 0/8（修复前 ≥3/8） |

## 四之二、部署记录（2026-10-12 12:06）

复检全部通过后，按仓库规范流程部署上线：

- **命令**：`powershell -ExecutionPolicy Bypass -File packages\website-deploy\deploy-website.ps1 -Server 172.28.204.40 -SkipBuild`
  （服务器当前内网 IP 经 DoH 解析 `lan.snhgn.me` → `172.28.204.40` 获得；系统 DNS 被 Mihomo TUN 劫持为 Fake-IP `198.18.0.159`，须 `--noproxy` 走 DoH）
- **载荷**：`web/dist`（89 文件；`ScheduleView-DuO7jiYB.js` 89048 字节 = 线上字节数，逐字节一致）
- **服务器执行日志**：
  ```text
  [12:06:03] 1/6 前置断言: 载荷文件数 89，断言通过
  [12:06:03] 2/6 备份现状 -> /opt/snhgn/backups/website-20261012-120603 (89 个文件)
  [12:06:03] 3/6 原地 rsync（保留目录 inode: 19923895）
  [12:06:04] 4/6 bind mount 体检: inode 一致 (19923895)
  [12:06:04] 5/6 重载 Caddy
  [12:06:04] 6/6 验证: 线上主 chunk assets/index-Dbk5HKFr.js 可取，全部通过
  ```
- **公网端到端验证**：
  - `https://snhgn.me/` → 200；`https://snhgn.me/schedule` → 200；`/api/auth/me` → 401（网关正常）
  - 线上 `assets/ScheduleView-DuO7jiYB.js` 含 `z-30`（F6 修复生效）；线上 `SettingsView` chunk 含 `/api/ai/settings`（F1 修复生效）
- **备注**：PowerShell 客户端最后会把 `sudo` 的 stderr 密码提示升级为异常打印（脚本注释中已知问题），导致退出码为 1 并刷屏一段红色错误——服务器侧 6/6 已全部通过、部署实际成功。若在意可仅作 cosmetics 修复（把最后一次 plink 的 stderr 也并流处理）。
- **回滚点**：`/opt/snhgn/backups/website-20261012-120603`

## 五、新增的常驻检查

- `tests/test_route_contract.py`：扫描前端源码里的 `/api/*` 字面量，逐一在网关路由表匹配（已兼容 starlette 1.x 的 `_IncludedRouter` 嵌套）
- `tests/test_login_rate_limit.py`：限流表内存边界
- `web/scripts/check-onmounted-early-return.cjs`：`onMounted` 提前 return 跳过副作用注册的控制流扫描
- `web/scripts/check-markdown-sanitize.cjs`：取组件真实源码片段运行，验证 markdown 输出净化
- `web/scripts/check-schedule-sticky-zindex.cjs`：校验吸顶“节次时间”列 z-index 恒高于课程卡片堆叠上限（F6 不变量）
