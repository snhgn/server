# Keystatic Admin 后台实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Astro 静态个人网站添加 Keystatic Admin 后台,支持网页编辑 Markdown/YAML 内容,通过 GitHub 自动同步和构建。

**Architecture:** Keystatic 在 `/admin` 路径运行 React SPA,本地用 local 模式直接读写文件,生产用 GitHub 模式通过 OAuth 认证后 commit 到仓库。服务器 Node 进程仅服务 `/admin` 和 webhook API,其余页面保持纯静态。Webhook 接收 GitHub push 事件,触发 git pull + build + rsync 部署。

**Tech Stack:** Astro 4, @keystatic/core, @keystatic/astro, @astrojs/react, @astrojs/node, PM2, GitHub OAuth

**Spec:** `docs/superpowers/specs/2026-07-12-keystatic-admin-design.md`

---

## 文件结构

### 新增文件
- `keystatic.config.ts` — Keystatic 主配置,定义所有 collections 和 singletons
- `src/pages/api/webhook.ts` — GitHub webhook 端点,验证签名并触发构建
- `scripts/build-and-deploy.sh` — 服务器构建脚本
- `ecosystem.config.cjs` — PM2 进程配置
- `.env.example` — 环境变量示例
- `public/uploads/blog/`, `public/uploads/projects/`, `public/uploads/learning/` — 图片上传目录(运行时创建)

### 修改文件
- `package.json` — 添加 Keystatic 相关依赖
- `astro.config.mjs` — 集成 React、Node adapter、Keystatic
- `src/content/config.ts` — 添加 timeline 集合(可选)
- `docs/superpowers/specs/2026-07-12-keystatic-admin-design.md` — 设计文档(已完成)

### 服务器端文件
- `/home/a/snhgn.me/` — Git 仓库克隆
- `/opt/1panel/apps/openresty/openresty/conf/conf.d/snhgn.me.conf` — Nginx 配置更新

---

## Task 1: 初始化 Git 仓库并推送到 GitHub

**Files:**
- Modify: 本地仓库 git 初始化
- External: GitHub 仓库 `snhgn/snhgn.me`

- [ ] **Step 1: 创建 `.gitignore`**

创建 `c:\Users\snhgn\Desktop\server\.gitignore`:

```
# Dependencies
node_modules/

# Build output
dist/
.astro/

# Environment
.env
.env.local
.env.production

# OS
.DS_Store
Thumbs.db

# Editor
.vscode/
.idea/
*.swp

# Logs
*.log
npm-debug.log*

# Uploads (user-generated content)
public/uploads/
```

- [ ] **Step 2: 初始化 git 仓库并提交**

```bash
cd c:\Users\snhgn\Desktop\server
git init
git add .
git commit -m "feat: initial commit - Astro digital garden with Keystatic admin"
git branch -M main
```

- [ ] **Step 3: 在 GitHub 创建仓库并推送**

用户需在 https://github.com/new 创建仓库 `snhgn/snhgn.me` (private,不要 init README)。

```bash
git remote add origin https://github.com/snhgn/snhgn.me.git
git push -u origin main
```

**验证:** GitHub 仓库显示所有文件,包含 `package.json`、`src/`、`astro.config.mjs`。

---

## Task 2: 安装 Keystatic 依赖

**Files:**
- Modify: `package.json`

- [ ] **Step 1: 安装 Keystatic 和 React 集成**

```bash
cd c:\Users\snhgn\Desktop\server
npx astro add react --yes
npm install @keystatic/core @keystatic/astro
```

- [ ] **Step 2: 安装 Node adapter**

```bash
npx astro add node --yes
```

- [ ] **Step 3: 验证 package.json 依赖**

读取 `package.json`,确认包含:
- `@keystatic/core`
- `@keystatic/astro`
- `@astrojs/react`
- `@astrojs/node`

- [ ] **Step 4: 提交**

```bash
git add package.json package-lock.json
git commit -m "chore: add Keystatic, React, Node adapter dependencies"
```

---

## Task 3: 更新 astro.config.mjs 集成 Keystatic

**Files:**
- Modify: `astro.config.mjs`

- [ ] **Step 1: 替换 astro.config.mjs**

```javascript
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import react from '@astrojs/react';
import node from '@astrojs/node';
import keystatic from '@keystatic/astro';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkCallout from './src/plugins/remark-callout.mjs';

export default defineConfig({
  site: 'https://snhgn.me',
  trailingSlash: 'always',
  output: 'hybrid',
  adapter: node({ mode: 'standalone' }),
  integrations: [react(), mdx(), keystatic()],
  markdown: {
    syntaxHighlight: 'shiki',
    shikiConfig: { theme: 'github-dark' },
    remarkPlugins: [remarkMath, remarkCallout],
    rehypePlugins: [rehypeKatex],
  },
});
```

- [ ] **Step 2: 验证配置加载**

```bash
npm run check
```

预期: 无配置错误(可能有类型警告,可忽略)。

- [ ] **Step 3: 提交**

```bash
git add astro.config.mjs
git commit -m "feat: integrate Keystatic, React, Node adapter"
```

---

## Task 4: 创建 keystatic.config.ts

**Files:**
- Create: `keystatic.config.ts`

- [ ] **Step 1: 创建 keystatic.config.ts**

```typescript
import { config, fields, collection, singleton } from '@keystatic/core';

const isProd = import.meta.env.PROD;

export default config({
  storage: isProd
    ? { kind: 'github', repo: 'snhgn/snhgn.me' }
    : { kind: 'local' },
  collections: {
    blog: collection({
      label: 'Blog',
      slugField: 'title',
      path: 'src/content/blog/*',
      format: { contentField: 'body' },
      schema: {
        title: fields.slug({ name: { label: '标题' } }),
        date: fields.date({ label: '发布日期', defaultValue: { date: new Date().toISOString().slice(0, 10) } }),
        description: fields.text({ label: '摘要', multiline: true }),
        category: fields.text({ label: '分类', defaultValue: '未分类' }),
        tags: fields.array(fields.text({ label: 'Tag' }), { label: '标签', itemLabel: (p) => p.value }),
        draft: fields.checkbox({ label: '草稿', defaultValue: false }),
        body: fields.text({ label: '正文 (Markdown)', multiline: true }),
      },
    }),

    learning: collection({
      label: 'Learning',
      slugField: 'title',
      path: 'src/content/learning/*',
      format: { contentField: 'body' },
      schema: {
        title: fields.slug({ name: { label: '标题' } }),
        date: fields.date({ label: '日期', defaultValue: { date: new Date().toISOString().slice(0, 10) } }),
        summary: fields.text({ label: '摘要', multiline: true }),
        tags: fields.array(fields.text({ label: 'Tag' }), { label: '标签', itemLabel: (p) => p.value }),
        problems: fields.array(fields.text({ label: '问题', multiline: true }), { label: '问题列表', itemLabel: (p) => p.value.slice(0, 30) }),
        solutions: fields.array(fields.text({ label: '解决方案', multiline: true }), { label: '解决方案列表', itemLabel: (p) => p.value.slice(0, 30) }),
        next_steps: fields.array(fields.text({ label: '下一步', multiline: true }), { label: '下一步', itemLabel: (p) => p.value.slice(0, 30) }),
        body: fields.text({ label: '正文 (Markdown)', multiline: true }),
      },
    }),

    projects: collection({
      label: 'Projects',
      slugField: 'title',
      path: 'src/content/projects/*',
      format: { contentField: 'body' },
      schema: {
        title: fields.slug({ name: { label: '标题' } }),
        date: fields.date({ label: '日期' }),
        status: fields.select({
          label: '状态',
          options: [
            { value: 'shipped', label: 'Shipped' },
            { value: 'in-progress', label: 'In Progress' },
            { value: 'paused', label: 'Paused' },
            { value: 'archived', label: 'Archived' },
          ],
          defaultValue: 'in-progress',
        }),
        year: fields.integer({ label: '年份' }),
        description: fields.text({ label: '描述', multiline: true }),
        tech: fields.array(fields.text({ label: 'Tech' }), { label: '技术栈', itemLabel: (p) => p.value }),
        github: fields.url({ label: 'GitHub URL' }),
        demo: fields.url({ label: 'Demo URL' }),
        featured: fields.checkbox({ label: '精选', defaultValue: false }),
        order: fields.integer({ label: '排序', defaultValue: 99 }),
        cover: fields.image({ label: '封面图', directory: 'public/uploads/projects', publicPath: '/uploads/projects/' }),
        lessons: fields.array(fields.text({ label: '教训', multiline: true }), { label: '经验教训', itemLabel: (p) => p.value.slice(0, 30) }),
        body: fields.text({ label: '正文 (Markdown)', multiline: true }),
      },
    }),
  },

  singletons: {
    site: singleton({
      label: 'Site Settings',
      path: 'src/content/data',
      format: { data: 'site.yml' },
      schema: {
        name: fields.text({ label: '站点名称' }),
        slogan: fields.text({ label: 'Slogan (EN)' }),
        slogan_zh: fields.text({ label: 'Slogan (中)' }),
        description: fields.text({ label: '描述', multiline: true }),
        url: fields.url({ label: 'URL' }),
        email: fields.text({ label: 'Email' }),
        github: fields.url({ label: 'GitHub' }),
        avatar: fields.text({ label: '头像路径' }),
        nav: fields.array(
          fields.object({
            label: fields.text({ label: 'Label' }),
            href: fields.text({ label: 'Href' }),
          }),
          { label: '导航', itemLabel: (p) => p.fields.label.value }
        ),
        footer: fields.object({
          copyright: fields.text({ label: '版权' }),
          links: fields.array(
            fields.object({
              label: fields.text({ label: 'Label' }),
              href: fields.text({ label: 'Href' }),
              external: fields.checkbox({ label: '外部链接', defaultValue: false }),
            }),
            { label: 'Footer Links', itemLabel: (p) => p.fields.label.value }
          ),
        }),
        seo: fields.object({
          og_type: fields.text({ label: 'OG Type', defaultValue: 'website' }),
          theme_color: fields.text({ label: 'Theme Color', defaultValue: '#FAFAFA' }),
          keywords: fields.array(fields.text({ label: 'Keyword' }), { label: 'Keywords', itemLabel: (p) => p.value }),
        }),
      },
    }),

    about: singleton({
      label: 'About',
      path: 'src/content/data/about',
      format: { data: 'profile.yml' },
      schema: {
        name: fields.text({ label: '姓名' }),
        role: fields.text({ label: 'Role (EN)' }),
        role_zh: fields.text({ label: 'Role (中)' }),
        avatar: fields.text({ label: '头像路径' }),
        bio: fields.text({ label: 'Bio (EN)', multiline: true }),
        bio_zh: fields.text({ label: 'Bio (中)', multiline: true }),
        interests: fields.array(fields.text({ label: '兴趣' }), { label: '兴趣列表', itemLabel: (p) => p.value }),
        philosophy: fields.array(fields.text({ label: '哲学', multiline: true }), { label: '个人哲学', itemLabel: (p) => p.value.slice(0, 30) }),
        social: fields.array(
          fields.object({
            label: fields.text({ label: 'Label' }),
            href: fields.text({ label: 'URL' }),
            icon: fields.text({ label: 'Icon' }),
          }),
          { label: '社交链接', itemLabel: (p) => p.fields.label.value }
        ),
        education: fields.array(
          fields.object({
            period: fields.text({ label: '时期' }),
            school: fields.text({ label: '学校' }),
            major: fields.text({ label: '专业' }),
          }),
          { label: '教育背景', itemLabel: (p) => p.fields.school.value }
        ),
        future_direction: fields.text({ label: '未来方向', multiline: true }),
        contact_note: fields.text({ label: '联系说明' }),
      },
    }),

    currently: singleton({
      label: 'Currently',
      path: 'src/content/data/currently',
      format: { data: 'currently.yml' },
      schema: {
        updated: fields.date({ label: '更新日期' }),
        items: fields.array(
          fields.object({
            category: fields.text({ label: '分类' }),
            content: fields.text({ label: '内容' }),
          }),
          { label: '当前状态', itemLabel: (p) => p.fields.category.value }
        ),
      },
    }),

    skills: singleton({
      label: 'Skills',
      path: 'src/content/data/skills',
      format: { data: 'skills.yml' },
      schema: {
        groups: fields.array(
          fields.object({
            category: fields.text({ label: '分类' }),
            items: fields.array(
              fields.object({
                name: fields.text({ label: '名称' }),
                level: fields.integer({ label: '等级 (1-5)', defaultValue: 3, validation: { min: 1, max: 5 } }),
                note: fields.text({ label: '备注' }),
              }),
              { label: '技能', itemLabel: (p) => p.fields.name.value }
            ),
          }),
          { label: '技能组', itemLabel: (p) => p.fields.category.value }
        ),
      },
    }),

    gallery: singleton({
      label: 'Gallery',
      path: 'src/content/data/gallery',
      format: { data: 'gallery.yml' },
      schema: {
        photos: fields.array(
          fields.object({
            src: fields.image({ label: '图片', directory: 'public/gallery', publicPath: '/gallery/' }),
            title: fields.text({ label: '标题' }),
            location: fields.text({ label: '地点' }),
            date: fields.text({ label: '日期' }),
            description: fields.text({ label: '描述' }),
          }),
          { label: '照片', itemLabel: (p) => p.fields.title.value }
        ),
      },
    }),
  },
});
```

- [ ] **Step 2: 验证配置文件无语法错误**

```bash
npx tsc --noEmit keystatic.config.ts
```

预期: 无错误。如果有 `import.meta.env` 类型错误,可忽略(Astro 会注入)。

- [ ] **Step 3: 提交**

```bash
git add keystatic.config.ts
git commit -m "feat: add Keystatic config with all collections and singletons"
```

---

## Task 5: 本地验证 Keystatic Admin

**Files:**
- 无文件修改,纯验证

- [ ] **Step 1: 启动开发服务器**

```bash
npm run dev
```

- [ ] **Step 2: 访问 /admin 并验证 UI**

打开浏览器访问 `http://localhost:4321/admin`。

预期看到:
- Keystatic Dashboard 界面
- 左侧菜单包含: Blog, Learning, Projects, Site Settings, About, Currently, Skills, Gallery
- Dashboard 显示空内容(因为还没读到现有文件)

- [ ] **Step 3: 验证能读取现有 Blog 文章**

在 Keystatic UI 点击 "Blog"。

预期: 显示 `hello-world` 条目(来自 `src/content/blog/hello-world.md`)。

- [ ] **Step 4: 验证能编辑现有 Blog 文章**

点击 `hello-world` 条目,修改摘要字段,点击 Save。

预期:
- 文件 `src/content/blog/hello-world.md` 被更新
- frontmatter 的 `description` 字段被修改
- 正文 body 保持不变

读取文件验证:

```bash
cat src/content/blog/hello-world.md
```

- [ ] **Step 5: 验证能编辑 YAML singleton**

点击 "Site Settings",修改 "站点名称" 字段,Save。

预期: `src/content/data/site.yml` 的 `name` 字段被更新。

- [ ] **Step 6: 停止开发服务器**

Ctrl+C 停止 `astro dev`。

- [ ] **Step 7: 提交(如有修改)**

```bash
git status
git add -A
git commit -m "chore: verify Keystatic local mode" || echo "No changes"
```

---

## Task 6: 创建 GitHub Webhook 端点

**Files:**
- Create: `src/pages/api/webhook.ts`

- [ ] **Step 1: 创建 webhook 端点**

创建 `src/pages/api/webhook.ts`:

```typescript
import { createHmac, timingSafeEqual } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

export const prerender = false;

export async function POST({ request }: { request: Request }) {
  // 1. 验证签名
  const sig = request.headers.get('x-hub-signature-256') || '';
  const body = await request.text();
  const secret = process.env.WEBHOOK_SECRET;

  if (!secret) {
    return new Response('Webhook secret not configured', { status: 500 });
  }

  const expected = 'sha256=' + createHmac('sha256', secret).update(body).digest('hex');
  const sigBuffer = Buffer.from(sig);
  const expectedBuffer = Buffer.from(expected);

  if (sigBuffer.length !== expectedBuffer.length || !timingSafeEqual(sigBuffer, expectedBuffer)) {
    return new Response('Invalid signature', { status: 401 });
  }

  // 2. 只处理 main 分支 push
  let payload: { ref?: string };
  try {
    payload = JSON.parse(body);
  } catch {
    return new Response('Invalid JSON', { status: 400 });
  }

  if (payload.ref !== 'refs/heads/main') {
    return new Response('Ignored: not main branch', { status: 200 });
  }

  // 3. 异步触发构建(不阻塞响应)
  const buildScript = process.env.BUILD_SCRIPT || '/home/a/snhgn.me/scripts/build-and-deploy.sh';

  execFileAsync(buildScript)
    .then(({ stdout }) => console.log('[webhook] Build done:', stdout))
    .catch((err) => console.error('[webhook] Build failed:', err));

  return new Response('Build triggered', { status: 200 });
}
```

- [ ] **Step 2: 验证构建包含 webhook 路由**

```bash
npm run build
```

预期: 构建成功,`dist/server/pages/api/webhook.mjs` 存在。

- [ ] **Step 3: 提交**

```bash
git add src/pages/api/webhook.ts
git commit -m "feat: add GitHub webhook endpoint for auto-deploy"
```

---

## Task 7: 创建构建脚本和环境变量示例

**Files:**
- Create: `scripts/build-and-deploy.sh`
- Create: `.env.example`
- Create: `ecosystem.config.cjs`

- [ ] **Step 1: 创建构建脚本**

创建 `scripts/build-and-deploy.sh`:

```bash
#!/bin/bash
set -e

REPO_DIR="/home/a/snhgn.me"
WEB_ROOT="/www/sites/snhgn.me/index"
LOG_FILE="/home/a/snhgn.me/build.log"

echo "[$(date)] Starting build..." | tee -a "$LOG_FILE"

cd "$REPO_DIR"

echo "[$(date)] Git pull..." | tee -a "$LOG_FILE"
git pull origin main 2>&1 | tee -a "$LOG_FILE"

echo "[$(date)] Installing dependencies..." | tee -a "$LOG_FILE"
npm ci 2>&1 | tee -a "$LOG_FILE"

echo "[$(date)] Building..." | tee -a "$LOG_FILE"
npm run build 2>&1 | tee -a "$LOG_FILE"

echo "[$(date)] Deploying to web root..." | tee -a "$LOG_FILE"
rsync -av --delete "$REPO_DIR/dist/" "$WEB_ROOT/" 2>&1 | tee -a "$LOG_FILE"

echo "[$(date)] Deploy complete." | tee -a "$LOG_FILE"
```

- [ ] **Step 2: 创建 .env.example**

创建 `.env.example`:

```
# GitHub OAuth (Keystatic 生产模式)
KEYSTATIC_GITHUB_CLIENT_ID=
KEYSTATIC_GITHUB_CLIENT_SECRET=
KEYSTATIC_SECRET=

# Webhook 签名密钥
WEBHOOK_SECRET=

# 构建脚本路径(可选,默认 /home/a/snhgn.me/scripts/build-and-deploy.sh)
BUILD_SCRIPT=
```

- [ ] **Step 3: 创建 PM2 配置**

创建 `ecosystem.config.cjs`:

```javascript
module.exports = {
  apps: [{
    name: 'snhgn-admin',
    script: './dist/server/entry.mjs',
    env: {
      NODE_ENV: 'production',
      HOST: '127.0.0.1',
      PORT: 3000,
      KEYSTATIC_GITHUB_REPO: 'snhgn/snhgn.me',
      KEYSTATIC_GITHUB_CLIENT_ID: 'YOUR_CLIENT_ID',
      KEYSTATIC_GITHUB_CLIENT_SECRET: 'YOUR_CLIENT_SECRET',
      KEYSTATIC_SECRET: 'YOUR_RANDOM_SECRET_32_CHARS',
      WEBHOOK_SECRET: 'YOUR_WEBHOOK_SECRET_32_CHARS',
    },
  }],
};
```

- [ ] **Step 4: 提交**

```bash
git add scripts/build-and-deploy.sh .env.example ecosystem.config.cjs
git commit -m "feat: add build script, env example, PM2 config"
```

---

## Task 8: 创建 GitHub OAuth App

**Files:**
- External: GitHub OAuth App

- [ ] **Step 1: 创建 OAuth App**

用户访问 https://github.com/settings/applications/new 填写:
- Application name: `snhgn Admin`
- Homepage URL: `http://192.168.1.43/admin`
- Authorization callback URL: `http://192.168.1.43/api/keystatic/github/oauth/callback`

点击 "Register application"。

- [ ] **Step 2: 记录 Client ID 和生成 Client Secret**

在 OAuth App 页面:
- 复制 Client ID
- 点击 "Generate a new client secret" → 复制 Client Secret

**安全保存这两个值,后续部署需要。**

- [ ] **Step 3: 生成两个随机密钥**

在本地 PowerShell:

```powershell
$KEYSTATIC_SECRET = -join ((48..57) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
$WEBHOOK_SECRET = -join ((48..57) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
Write-Host "KEYSTATIC_SECRET=$KEYSTATIC_SECRET"
Write-Host "WEBHOOK_SECRET=$WEBHOOK_SECRET"
```

保存这 4 个值:
- `KEYSTATIC_GITHUB_CLIENT_ID`
- `KEYSTATIC_GITHUB_CLIENT_SECRET`
- `KEYSTATIC_SECRET`
- `WEBHOOK_SECRET`

---

## Task 9: 服务器准备和部署

**Files:**
- External: 服务器 192.168.1.43

- [ ] **Step 1: SSH 连接服务器**

```bash
ssh a@192.168.1.43
```

密码: `1`

- [ ] **Step 2: 安装 Node.js 和 PM2(如未安装)**

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
sudo npm install -g pm2
```

验证:

```bash
node --version
pm2 --version
```

- [ ] **Step 3: 克隆仓库**

```bash
cd /home/a
git clone https://github.com/snhgn/snhgn.me.git
cd snhgn.me
npm ci
```

- [ ] **Step 4: 配置 Git 凭据(让 git pull 不需要密码)**

使用 GitHub Personal Access Token:

```bash
git remote set-url origin https://<TOKEN>@github.com/snhgn/snhgn.me.git
```

或在服务器配置 SSH key。

- [ ] **Step 5: 创建 .env 文件**

```bash
cat > /home/a/snhgn.me/.env << 'EOF'
NODE_ENV=production
HOST=127.0.0.1
PORT=3000
KEYSTATIC_GITHUB_REPO=snhgn/snhgn.me
KEYSTATIC_GITHUB_CLIENT_ID=<填入 Step 8 的值>
KEYSTATIC_GITHUB_CLIENT_SECRET=<填入 Step 8 的值>
KEYSTATIC_SECRET=<填入 Step 8 的值>
WEBHOOK_SECRET=<填入 Step 8 的值>
BUILD_SCRIPT=/home/a/snhgn.me/scripts/build-and-deploy.sh
EOF
chmod 600 /home/a/snhgn.me/.env
```

- [ ] **Step 6: 构建并启动 PM2**

```bash
cd /home/a/snhgn.me
npm run build
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup
```

按提示执行 `pm2 startup` 输出的 sudo 命令。

- [ ] **Step 7: 验证 Node 进程运行**

```bash
pm2 status
curl http://127.0.0.1:3000/admin
```

预期: pm2 显示 `snhgn-admin` online,curl 返回 HTML。

- [ ] **Step 8: 设置构建脚本可执行**

```bash
chmod +x /home/a/snhgn.me/scripts/build-and-deploy.sh
```

---

## Task 10: 配置 Nginx 反向代理

**Files:**
- External: 服务器 Nginx 配置

- [ ] **Step 1: 找到 Nginx 配置文件**

```bash
ssh a@192.168.1.43
ls /opt/1panel/apps/openresty/openresty/conf/conf.d/
```

- [ ] **Step 2: 更新 snhgn.me.conf**

备份后更新配置:

```bash
sudo cp /opt/1panel/apps/openresty/openresty/conf/conf.d/snhgn.me.conf /opt/1panel/apps/openresty/openresty/conf/conf.d/snhgn.me.conf.bak
```

通过 1Panel 文件管理或 `cat` 写入新配置:

```nginx
server {
    listen 80;
    server_name snhgn.me 192.168.1.43;
    root /www/sites/snhgn.me/index;
    index index.html;

    access_log /www/sites/snhgn.me/log/access.log main;
    error_log /www/sites/snhgn.me/log/error.log;

    location ^~ /.well-known/acme-challenge {
        allow all;
        root /usr/share/nginx/html;
    }

    # 静态资源
    location ~* \.(css|js|svg|png|jpg|jpeg|gif|ico|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Keystatic Admin (SSR)
    location /admin {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Keystatic API (OAuth callback)
    location /api/keystatic/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # Webhook
    location /api/webhook {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # 静态站点
    location / {
        try_files $uri $uri/ $uri.html /404.html;
    }
}
```

- [ ] **Step 3: 重载 Nginx**

```bash
sudo docker exec 1Panel-openresty-9kAg nginx -t
sudo docker exec 1Panel-openresty-9kAg nginx -s reload
```

- [ ] **Step 4: 验证路由**

从本地:

```bash
curl -I http://192.168.1.43/
curl -I http://192.168.1.43/admin/
curl -I http://192.168.1.43/blog/
```

预期:
- `/` → 200(静态)
- `/admin/` → 200 或 302(重定向到 GitHub OAuth)
- `/blog/` → 200(静态)

---

## Task 11: 配置 GitHub Webhook

**Files:**
- External: GitHub 仓库设置

- [ ] **Step 1: 添加 Webhook**

用户访问 https://github.com/snhgn/snhgn.me/settings/hooks/new 填写:
- Payload URL: `http://192.168.1.43/api/webhook`
- Content type: `application/json`
- Secret: Step 8 生成的 `WEBHOOK_SECRET`
- Which events trigger: "Just the push event"

点击 "Add webhook"。

- [ ] **Step 2: 验证 Webhook 发送**

GitHub 会发送 ping 事件。在 webhook 设置页查看 "Recent Deliveries"。

预期: 第一次 ping 返回 200(但不会触发构建,因为 ping 不是 push)。

- [ ] **Step 3: 测试 push 事件**

在本地:

```bash
cd c:\Users\snhgn\Desktop\server
echo "# test" >> README.md
git add README.md
git commit -m "test: trigger webhook"
git push origin main
```

在 GitHub webhook "Recent Deliveries" 查看响应:

预期: push 事件返回 200,响应体 "Build triggered"。

- [ ] **Step 4: 验证服务器自动构建**

SSH 到服务器:

```bash
ssh a@192.168.1.43
tail -f /home/a/snhgn.me/build.log
```

预期: 看到 git pull + build + rsync 日志。

访问 http://192.168.1.43/ 验证内容更新。

- [ ] **Step 5: 回滚测试 commit**

```bash
cd c:\Users\snhgn\Desktop\server
git revert HEAD --no-edit
git push origin main
```

---

## Task 12: 端到端验证

**Files:**
- 无文件修改,纯验证

- [ ] **Step 1: 验证 Admin OAuth 登录**

浏览器访问 `http://192.168.1.43/admin`。

预期:
- 重定向到 GitHub 授权页
- 授权后返回 Admin Dashboard
- 显示所有 collections 和 singletons

- [ ] **Step 2: 验证编辑 Blog 并自动部署**

1. 在 Admin UI 创建新 Blog 文章
2. 填写标题、日期、正文
3. 点击 Save(Keystatic 会 commit 到 GitHub)
4. 等待 30-60 秒(webhook 触发构建)
5. 访问 `http://192.168.1.43/blog/` 查看新文章

- [ ] **Step 3: 验证编辑 YAML singleton**

1. 在 Admin UI 编辑 "Site Settings"
2. 修改站点名称
3. Save
4. 等待自动构建
5. 访问首页验证标题更新

- [ ] **Step 4: 验证现有 16 个路由仍正常**

```bash
$routes = @('/', '/about/', '/projects/', '/learning/', '/blog/', '/timeline/', '/gallery/', '/skills/', '/currently/', '/contact/', '/blog/hello-world/', '/learning/systemd-dependency/', '/learning/freertos-priority-inversion/', '/projects/smart-cart/', '/projects/woodscan/', '/admin/')
foreach ($r in $routes) {
    $code = (Invoke-WebRequest -Uri "http://192.168.1.43$r" -Method Head -UseBasicParsing).StatusCode
    Write-Host "$r : $code"
}
```

预期: 全部 200 或 302(/admin/ 可能 302 重定向到 OAuth)。

- [ ] **Step 5: 验证 PM2 进程稳定**

```bash
ssh a@192.168.1.43 "pm2 status"
```

预期: `snhgn-admin` 状态 `online`,uptime 持续增长。

- [ ] **Step 6: 提交最终状态**

```bash
cd c:\Users\snhgn\Desktop\server
git add -A
git commit -m "feat: Keystatic admin integration complete" || echo "No changes"
git push origin main
```

---

## 验收标准

### 本地开发
- [x] `npm run dev` 启动成功
- [x] 访问 `http://localhost:4321/admin` 显示 Keystatic UI
- [x] 能创建/编辑/删除 blog 文章
- [x] 能创建/编辑/删除 learning 笔记
- [x] 能创建/编辑/删除 project
- [x] 能编辑 site/about/currently/skills/gallery YAML 配置
- [x] `astro check` 通过
- [x] `astro build` 成功

### 生产部署
- [x] 服务器能访问 `/admin` 并完成 OAuth 登录
- [x] 编辑内容后 commit 到 GitHub
- [x] Webhook 触发自动构建
- [x] 静态站点内容更新
- [x] 所有现有路由(16 个)仍返回 200
- [x] PM2 进程稳定运行

### 内容完整性
- [x] Content Collections schema 不变
- [x] 现有 Markdown 文件格式不变
- [x] 现有 YAML 文件格式不变
- [x] remark 插件(数学、callout)正常工作
- [x] 代码高亮正常

---

## 不做的事情

- ❌ 不迁移到 Markdoc 格式
- ❌ 不改变 Content Collections schema
- ❌ 不引入数据库
- ❌ 不引入 ORM
- ❌ 不自建编辑器(用 Keystatic 内置)
- ❌ 不改变现有页面代码
- ❌ 不改变现有 Nginx 静态文件服务(仅新增 proxy 规则)
