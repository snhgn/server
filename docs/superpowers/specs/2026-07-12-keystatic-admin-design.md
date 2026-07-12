# Keystatic Admin 后台设计

**日期**: 2026-07-12
**项目**: snhgn.me (Astro 静态个人网站)
**状态**: 设计完成,待实施

---

## 1. 目标

为 Astro 静态个人网站添加仅供站长使用的 Admin Dashboard。

### 核心原则(不可妥协)

- **Content as Files**: 内容仍是 Markdown/YAML 文件,不引入数据库
- **不改 Content Collections**: `src/content/config.ts` 的 Zod schema 保持不变
- **不生成额外 JSON**: Keystatic 直接写入原 Markdown/YAML 文件
- **保持极简**: 不为后台引入复杂架构

### 方案选择

**Keystatic + GitHub 模式**,理由:
1. Astro 官方推荐,`@keystatic/astro` 一等公民
2. TypeScript 原生,与现有 Zod schema 理念一致
3. Content as Files 不变,内容仍是 Markdown/YAML
4. 图片上传内置,自动存到 `src/assets/`
5. Thinkmill 团队持续维护

**编辑模式**: 纯 Markdown 源码编辑(用 `fields.text({ multiline: true })`),不迁移到 Markdoc。

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│  开发者笔记本 (本地)                                          │
│  ┌─────────────┐    ┌──────────────┐                        │
│  │ astro dev   │    │ Keystatic    │ ← /admin 本地模式       │
│  │ (localhost  │    │ local mode   │   直接读写本地文件      │
│  │  :4321)     │    │              │                        │
│  └─────────────┘    └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                            │
                      git push (可选)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub 仓库 (snhgn/snhgn.me)                                │
│  ┌─────────────────────────────────────────────────┐        │
│  │ src/content/  (Markdown + YAML)                 │        │
│  │ src/          (页面代码)                         │        │
│  └─────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
                            │
                      Webhook (push 事件)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  服务器 192.168.1.43                                         │
│  ┌──────────────────────────────────────────────────┐       │
│  │ Nginx (OpenResty)                                │       │
│  │  ├─ / → 静态文件 (/www/sites/snhgn.me/index/)    │       │
│  │  ├─ /admin → proxy_pass Node :3000              │       │
│  │  ├─ /api/keystatic → proxy_pass Node :3000      │       │
│  │  └─ /api/webhook → proxy_pass Node :3000        │       │
│  └──────────────────────────────────────────────────┘       │
│  ┌──────────────────────────────────────────────────┐       │
│  │ Node 进程 (PM2 管理)                             │       │
│  │  ├─ /admin (Keystatic GitHub 模式)               │       │
│  │  ├─ /api/keystatic/* (OAuth callback)            │       │
│  │  └─ /api/webhook (接收 GitHub push,触发构建)     │       │
│  └──────────────────────────────────────────────────┘       │
│  ┌──────────────────────────────────────────────────┐       │
│  │ 构建脚本 (webhook 触发)                          │       │
│  │  git pull → npm ci → npm run build → rsync       │       │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 关键设计点

- **公开站点**: 纯静态,Nginx 直接服务,性能不变
- **Admin 后台**: Node 进程仅服务 `/admin` 和 API 路由,其余预渲染
- **内容流**: Keystatic → GitHub commit → webhook → 服务器自动构建
- **本地开发**: Keystatic local 模式,直接读写本地文件,无需 GitHub

---

## 3. Keystatic 配置

### `keystatic.config.ts`

```typescript
import { config, fields, collection, singleton } from '@keystatic/core';

const isProd = import.meta.env.PROD;

export default config({
  storage: isProd
    ? { kind: 'github', repo: 'snhgn/snhgn.me' }
    : { kind: 'local' },
  collections: {
    // === Markdown 内容集合 ===
    blog: collection({
      label: 'Blog',
      slugField: 'title',
      path: 'src/content/blog/*',
      format: { contentField: 'body' },
      schema: {
        title: fields.slug({ name: { label: '标题' } }),
        date: fields.date({ label: '发布日期', defaultValue: { date: new Date().toISOString().slice(0,10) } }),
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
        date: fields.date({ label: '日期', defaultValue: { date: new Date().toISOString().slice(0,10) } }),
        summary: fields.text({ label: '摘要', multiline: true }),
        tags: fields.array(fields.text({ label: 'Tag' }), { label: '标签', itemLabel: (p) => p.value }),
        problems: fields.array(fields.text({ label: '问题', multiline: true }), { label: '问题列表', itemLabel: (p) => p.value }),
        solutions: fields.array(fields.text({ label: '解决方案', multiline: true }), { label: '解决方案列表', itemLabel: (p) => p.value }),
        next_steps: fields.array(fields.text({ label: '下一步', multiline: true }), { label: '下一步', itemLabel: (p) => p.value }),
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
        lessons: fields.array(fields.text({ label: '教训', multiline: true }), { label: '经验教训', itemLabel: (p) => p.value }),
        body: fields.text({ label: '正文 (Markdown)', multiline: true }),
      },
    }),

    timeline: collection({
      label: 'Timeline',
      slugField: 'title',
      path: 'src/content/data/timeline/*',
      format: { contentField: 'body' },
      schema: {
        title: fields.slug({ name: { label: '标题' } }),
        date: fields.date({ label: '日期' }),
        body: fields.text({ label: '正文', multiline: true }),
      },
    }),
  },

  singletons: {
    // === YAML 配置文件 ===
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

### 字段类型映射

| Astro Zod | Keystatic Field |
|---|---|
| `z.string()` | `fields.text()` |
| `z.string()` (多行) | `fields.text({ multiline: true })` |
| `z.coerce.date()` | `fields.date()` |
| `z.enum([...])` | `fields.select()` |
| `z.boolean()` | `fields.checkbox()` |
| `z.number()` | `fields.integer()` 或 `fields.number()` |
| `z.array(z.string())` | `fields.array(fields.text())` |
| `z.string().url()` | `fields.url()` |
| 图片字段 | `fields.image()` |

### 关键设计决策

1. **`body` 字段用 `fields.text({ multiline: true })`**,而不是 `fields.markdoc()`
   - 保留纯 Markdown 源码编辑
   - 现有 remark 插件(数学、callout)在前端正常渲染
   - 编辑器是 textarea,Keystatic 自动加文件名

2. **YAML 文件用 `singleton`**
   - 每个配置文件(site/about/currently/skills/gallery)对应一个 singleton
   - 直接读写原文件,不生成额外 JSON

3. **Content Collections schema 不动**
   - `src/content/config.ts` 保持不变
   - Keystatic 写入的文件必须符合现有 Zod schema
   - 双重校验:Keystatic 入库时 + Astro 构建时

4. **图片上传**
   - Keystatic 的 `fields.image()` 内置上传功能
   - 图片存到 `public/uploads/{projects,blog,learning}/`
   - 自动写入 frontmatter 的 `cover` 字段

---

## 4. 部署架构

### Nginx 配置(更新 `snhgn.me.conf`)

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

    # === 静态资源 ===
    location ~* \.(css|js|svg|png|jpg|jpeg|gif|ico|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # === Keystatic Admin (SSR) ===
    location /admin {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # === Keystatic API (OAuth callback, GitHub 代理) ===
    location /api/keystatic/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # === Webhook (GitHub push 触发构建) ===
    location /api/webhook {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # === 静态站点 (其余所有路由) ===
    location / {
        try_files $uri $uri/ $uri.html /404.html;
    }
}
```

### PM2 配置 `ecosystem.config.cjs`

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
      KEYSTATIC_GITHUB_CLIENT_ID: '<待填>',
      KEYSTATIC_GITHUB_CLIENT_SECRET: '<待填>',
      KEYSTATIC_SECRET: '<随机字符串>',
      WEBHOOK_SECRET: '<随机字符串>',
    },
  }],
};
```

### 构建脚本 `scripts/build-and-deploy.sh`

```bash
#!/bin/bash
set -e
cd /home/a/snhgn.me
git pull origin main
npm ci
npm run build
rsync -av --delete dist/ /www/sites/snhgn.me/index/
echo "Deployed at $(date)"
```

---

## 5. 认证与安全

### GitHub OAuth 流程

```
1. 用户访问 /admin
2. Keystatic 检测未登录 → 重定向到 GitHub OAuth 授权页
3. 用户授权 → GitHub callback /api/keystatic/github/oauth/callback
4. Keystatic 用 code 换 access token → 存入加密 cookie
5. 后续所有 GitHub API 调用使用该 token
```

### 安全措施

- 公开页面只读,Admin 走 OAuth
- GitHub OAuth App 限定 repo 权限
- `KEYSTATIC_SECRET` 加密 session cookie
- Webhook 验证 `X-Hub-Signature-256` HMAC 签名
- `/admin` 路径不暴露源码,只渲染 React UI

### GitHub OAuth App 配置

需要在 GitHub 创建 OAuth App:
- Homepage URL: `http://192.168.1.43/admin`
- Authorization callback URL: `http://192.168.1.43/api/keystatic/github/oauth/callback`
- 获取 Client ID 和 Client Secret

---

## 6. Webhook 自动构建

### 流程

```
┌─────────────┐   push    ┌──────────────┐
│ Keystatic   │ ────────► │ GitHub Repo  │
│ (浏览器)    │           └──────────────┘
└─────────────┘                  │
                                 │ webhook (push event)
                                 ▼
                       ┌──────────────────┐
                       │ 服务器 Node 进程  │
                       │ /api/webhook     │
                       └──────────────────┘
                                 │
                                 │ 验证签名 + 触发
                                 ▼
                       ┌──────────────────┐
                       │ 构建脚本(异步)   │
                       │ git pull         │
                       │ npm ci           │
                       │ npm run build    │
                       │ rsync → web root │
                       └──────────────────┘
                                 │
                                 ▼
                       ┌──────────────────┐
                       │ 静态站点更新      │
                       └──────────────────┘
```

### Webhook 端点 `src/pages/api/webhook.ts`

```typescript
import { createHmac, timingSafeEqual } from 'crypto';
import { execFile } from 'child_process';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);

export async function POST({ request }) {
  // 1. 验证签名
  const sig = request.headers.get('x-hub-signature-256') || '';
  const body = await request.text();
  const expected = 'sha256=' + createHmac('sha256', process.env.WEBHOOK_SECRET)
    .update(body).digest('hex');
  if (!timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) {
    return new Response('Invalid signature', { status: 401 });
  }

  // 2. 只处理 main 分支 push
  const payload = JSON.parse(body);
  if (payload.ref !== 'refs/heads/main') {
    return new Response('Ignored', { status: 200 });
  }

  // 3. 异步触发构建(不阻塞响应)
  execFileAsync('/home/a/snhgn.me/scripts/build-and-deploy.sh')
    .then(({ stdout }) => console.log('Build done:', stdout))
    .catch((err) => console.error('Build failed:', err));

  return new Response('Build triggered', { status: 200 });
}
```

---

## 7. Admin UI 结构

### 左侧菜单

```
┌─────────────────────────────────────┐
│  📝 snhgn Admin              [退出]  │
├─────────────────────────────────────┤
│  📊 Dashboard                       │
│  ─────────────                      │
│  📝 Blog                            │
│  📚 Learning                        │
│  🚀 Projects                        │
│  📅 Timeline                        │
│  ─────────────                      │
│  👤 About                           │
│  ⚙️ Site Settings                   │
│  📍 Currently                       │
│  🛠️ Skills                          │
│  🖼️ Gallery                         │
└─────────────────────────────────────┘
```

### Dashboard 首页内容

- **最近修改**: 从 GitHub API 拉取最近 5 次 commit
- **快捷新建**: Blog / Learning / Project / Timeline 按钮
- **统计**: 各集合条目数

### 编辑器视图

```
┌─────────────────────────────────────┐
│  ← Blog Posts / hello-world   [保存] │
├─────────────────────────────────────┤
│  标题:  [hello world            ]    │
│  日期:  [2026-07-11]  草稿: [☐]      │
│  分类:  [未分类    ]                  │
│  标签:  [+ 添加标签]                  │
│  摘要:  ┌──────────────────────┐     │
│         │                      │     │
│         └──────────────────────┘     │
│  ───────────────────────────────     │
│  正文 (Markdown):                    │
│  ┌──────────────────────────────┐    │
│  │ # Hello World               │    │
│  │                             │    │
│  │ 这是正文内容...              │    │
│  │                             │    │
│  │ :::note                     │    │
│  │ 这是一个 callout            │    │
│  │ :::                         │    │
│  │                             │    │
│  │ $$E=mc^2$$                  │    │
│  └──────────────────────────────┘    │
│  (纯文本编辑,保存后前端渲染)         │
└─────────────────────────────────────┘
```

### UI 风格

- 整体 UI 与网站风格一致,极简
- 支持深色模式(继承网站主题)
- Keystatic 默认 UI 已足够,无需自定义

---

## 8. 本地开发 vs 生产

| 模式 | storage | 认证 | 构建 |
|---|---|---|---|
| **本地** (`astro dev`) | `local` | 无 | 无,文件直接写入磁盘 |
| **生产** (服务器) | `github` | GitHub OAuth | webhook 触发 |

环境变量切换通过 `import.meta.env.PROD` 判断。

---

## 9. 实施步骤

1. **GitHub 准备**
   - 创建 `snhgn/snhgn.me` 仓库
   - 创建 GitHub OAuth App
   - 初始化本地 git,推送到 GitHub

2. **安装依赖**
   - `npx astro add react node`
   - `npm install @keystatic/core @keystatic/astro`

3. **创建 `keystatic.config.ts`**
   - 定义所有 collections 和 singletons
   - 字段映射现有 Zod schema

4. **更新 `astro.config.mjs`**
   - 加入 React、Node adapter、Keystatic 集成
   - `output: 'static'`(默认)+ `/admin` 走 SSR

5. **创建 webhook 端点**
   - `src/pages/api/webhook.ts`

6. **创建构建脚本**
   - `scripts/build-and-deploy.sh`

7. **PM2 配置**
   - `ecosystem.config.cjs`

8. **服务器部署**
   - 克隆仓库到 `/home/a/snhgn.me`
   - PM2 启动 Node 进程
   - 更新 Nginx 配置

9. **验证**
   - 本地: `astro dev` → 访问 `/admin` 编辑内容
   - 生产: `/admin` OAuth 登录 → 编辑 → webhook 触发构建

---

## 10. 验收标准

### 本地开发
- [ ] `npm run dev` 启动成功
- [ ] 访问 `http://localhost:4321/admin` 显示 Keystatic UI
- [ ] 能创建/编辑/删除 blog 文章
- [ ] 能创建/编辑/删除 learning 笔记
- [ ] 能创建/编辑/删除 project
- [ ] 能编辑 site/about/currently/skills/gallery YAML 配置
- [ ] 图片上传到 `public/uploads/` 并正确引用
- [ ] `astro check` 通过
- [ ] `astro build` 成功

### 生产部署
- [ ] 服务器能访问 `/admin` 并完成 OAuth 登录
- [ ] 编辑内容后 commit 到 GitHub
- [ ] Webhook 触发自动构建
- [ ] 静态站点内容更新
- [ ] 所有现有路由(16 个)仍返回 200
- [ ] PM2 进程稳定运行

### 内容完整性
- [ ] Content Collections schema 不变
- [ ] 现有 Markdown 文件格式不变
- [ ] 现有 YAML 文件格式不变
- [ ] remark 插件(数学、callout)正常工作
- [ ] 代码高亮正常

---

## 11. 不做的事情

- ❌ 不迁移到 Markdoc 格式
- ❌ 不改变 Content Collections schema
- ❌ 不引入数据库
- ❌ 不引入 ORM
- ❌ 不引入复杂 CMS
- ❌ 不自建编辑器(用 Keystatic 内置)
- ❌ 不改变现有页面代码
- ❌ 不改变现有 Nginx 静态文件服务(仅新增 proxy 规则)

---

## 12. 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| Keystatic 与 Astro 4 兼容性 | `@keystatic/astro` peer 支持 Astro 2-6 |
| GitHub API 限流 | 个人使用不会触发,必要时加缓存 |
| Webhook 构建失败 | 构建脚本 `set -e` 失败即停,日志记录 |
| OAuth 配置错误 | 文档化每一步,验证回调 URL |
| 现有内容格式不兼容 | 用 `fields.text` 保留纯 Markdown,零迁移 |

---

## 参考资料

- [Keystatic 官方文档](https://keystatic.com/docs)
- [Astro + Keystatic 集成指南](https://docs.astro.build/en/guides/cms/keystatic/)
- [Keystatic GitHub 模式](https://keystatic.com/docs/github-mode)
- [GitHub Webhook 签名验证](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
