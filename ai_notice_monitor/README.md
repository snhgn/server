# 校园通知智能监控系统

自动监控**北京林业大学理学院通知公告**页面，发现新通知后通过邮件通知，并使用本地大模型生成摘要。

目标页面：<https://cos.bjfu.edu.cn/tzgg/index.html>

---

## 功能特性

- ✅ **网页监控**：抓取通知列表 + 详情正文（User-Agent、超时、重试、异常处理）
- ✅ **数据去重**：SQLite 存储，URL 唯一键，重复运行不重复发送
- ✅ **AI 摘要**：本地 Ollama 生成结构化 JSON（分类/重要程度/截止时间/摘要/建议动作）
- ✅ **邮件通知**：HTML 邮件，QQ/163 邮箱授权码认证
- ✅ **定时运行**：Windows 任务计划 + Linux cron 双方案
- ✅ **AI 可切换**：Ollama → DeepSeek → OpenAI，改配置即可

---

## 项目结构

```
ai_notice_monitor/
├── main.py            # 主入口（编排抓取→去重→摘要→发信）
├── config.py          # 配置读取（.env）
├── scraper.py         # 网页抓取模块
├── database.py        # SQLite 去重存储
├── ai_summary.py      # AI 摘要模块（可切换提供方）
├── email_sender.py    # SMTP 邮件模块
├── scheduler.md       # 定时任务配置说明
├── requirements.txt   # 依赖
├── README.md          # 本文档
└── .env.example       # 配置模板（复制为 .env 填写）
```

---

## 快速开始

### 1. 安装依赖

```bash
cd D:\ai_notice_monitor
py -m pip install -r requirements.txt
```

### 2. 配置 .env

```bash
copy .env.example .env
# 用编辑器打开 .env，填写邮箱和授权码
```

必填项：
- `SMTP_HOST` / `SMTP_PORT`：QQ=`smtp.qq.com:465`，163=`smtp.163.com:465`
- `SMTP_SENDER`：发件邮箱
- `SMTP_AUTH_CODE`：**授权码**（QQ 邮箱在 设置→账户→开启 SMTP 服务 获取；163 同理）
- `SMTP_RECEIVER`：收件邮箱

可选：
- `AI_PROVIDER`：`ollama` / `deepseek` / `openai`
- `AI_API_BASE` / `AI_API_KEY` / `AI_MODEL`

### 3. 测试运行（推荐先用 --test）

```bash
py main.py --test
```

`--test` 会抓取 + 摘要并打印结果，**不发邮件**，用于验证链路。

### 4. 正式运行

```bash
py main.py
```

### 5. 配置定时任务

见 [scheduler.md](scheduler.md)。

---

## 首次运行说明

- 默认首次运行：历史通知**只入库、不发送**，从次日开始的新通知才会发邮件。
- 想首次就发送全部历史：`.env` 中设置 `FIRST_RUN_SEND_ALL=true`（会收到约 220 封，慎用）。

---

## AI 摘要切换

`.env` 中修改三个变量即可切换：

| 提供方 | AI_PROVIDER | AI_API_BASE | AI_API_KEY |
|--------|------------|-------------|------------|
| 本地 Ollama | `ollama` | `http://localhost:11434/v1` | 任意（如 `ollama`） |
| DeepSeek | `deepseek` | `https://api.deepseek.com/v1` | 你的 DeepSeek Key |
| OpenAI | `openai` | `https://api.openai.com/v1` | 你的 OpenAI Key |

AI 不可用时会**自动降级**（摘要显示"AI 摘要不可用"），不影响发邮件。

---

## 测试方法

| 场景 | 命令 |
|------|------|
| 只抓取+摘要，不发邮件 | `py main.py --test` |
| 干跑（抓取+入库+摘要） | `py main.py --dry-run` |
| 完整流程（发邮件） | `py main.py` |
| 只测抓取模块 | `py -c "from config import load_config; from scraper import NoticeScraper; s=NoticeScraper(load_config().scraper); [print(n.title, n.url, n.publish_time) for n in s.fetch_latest()[:5]]"` |
| 只测 AI 模块 | `py -c "from config import load_config; from ai_summary import AISummarizer; a=AISummarizer(load_config().ai); print(a.summarize('数学建模竞赛报名','比赛时间2026年9月10日,报名截止8月20日'))"` |

---

## 常见错误排查

### 1. 网页结构变化
- 症状：日志出现 `列表页未找到容器` / 解析到 0 条
- 解决：打开目标页面，用浏览器开发者工具检查 `.post-list .news-last ul` 结构是否仍存在；若变化，修改 `scraper.py` 中 `_list_container_selector`。

### 2. SMTP 失败
- 症状：`SMTP 发送失败: ... Authentication failed` / `connection refused`
- 排查：
  - 确认用的是**授权码**不是登录密码
  - 确认 `SMTP_PORT=465`（SSL）
  - QQ 邮箱需先开启"SMTP 服务"并获取授权码
  - 163 邮箱需开启"客户端授权密码"
  - 部分邮箱要求发件人=登录账号

### 3. Ollama 连接失败
- 症状：日志大量 `摘要失败`，邮件里摘要显示"AI 摘要不可用"
- 排查：
  - `ollama serve` 是否在运行（`ollama list` 能否列出模型）
  - `AI_API_BASE` 是否指向 `http://localhost:11434/v1`
  - `AI_MODEL` 是否存在于 `ollama list` 输出中
  - 系统是开机自动启动 Ollama 的（见本机部署），正常应可用

### 4. 编码问题
- 症状：标题乱码 / 邮件乱码 / 日志乱码
- 排查：
  - 网页解析使用 `resp.apparent_encoding` 自动判断编码
  - 邮件已指定 `charset=utf-8`，乱码多为邮箱客户端显示问题
  - Windows 控制台乱码可执行 `chcp 65001` 切换 UTF-8

### 5. 重复发送
- 正常不会发生（URL 唯一键）。若怀疑，查看数据库：
  ```bash
  py -c "import sqlite3; c=sqlite3.connect('notices.db'); print(c.execute('SELECT sent,COUNT(*) FROM notices GROUP BY sent').fetchall())"
  ```
  `(0, n)` 表示有 n 条未发送。

---

## 日志

运行日志写入项目目录 `notice_monitor.log`（UTF-8），同时输出到控制台。

## 数据库

`notices.db`（SQLite，WAL 模式），表 `notices` 字段：`url`(唯一键)、`title`、`publish_time`、`first_seen_at`、`sent`。
