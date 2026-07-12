# Content-Driven Website Refactor — Design Spec

**Date:** 2026-07-12
**Status:** Approved (pending user spec review)
**Author:** snhgn (via AI pair-programming)

---

## 1. Goal

将现有手写静态 HTML 网站重构为 **Astro Content Collections** 驱动的内容管理系统。重构后,新增项目/博客/学习记录只需新增 Markdown 文件,更新时间轴/技能/相册只需改 YAML,无需触碰页面代码。

### 成功标准

1. 所有 9 个页面(Home/About/Projects/Learning/Blog/Timeline/Skills/Gallery/Contact)由 `src/content/` 驱动
2. 新增内容文件后,`astro build` 通过且页面自动包含新内容
3. 所有 frontmatter 类型由 Zod schema 校验,错误内容编译失败
4. 视觉与当前 `main.css` 完全一致(像素级)
5. WordPress 完全废弃,1 篇文章迁移到 Markdown
6. 服务器上 Nginx 直接服务 `dist/`,PHP server 和 WP 删除
7. 所有路由(含 `/tech-stack/` → `/skills/` 重定向)返回 200

### 非目标(Out of Scope)

- 不重新设计 UI(保留现有视觉)
- 不加 Web CMS 界面(Decap CMS 等过度设计)
- 不加搜索/评论/订阅功能
- 不加 i18n
- 不加 analytics(如有需要后续单独加)

---

## 2. 决策摘要

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 技术栈 | Astro | 内容驱动静态站点生成器,编译成纯 HTML,匹配需求 |
| 内容管理 | Astro Content Collections + Zod | 编译时类型校验,DRY |
| WordPress 处理 | 完全迁移到 Markdown,删除 WP | 统一内容源 |
| 视觉风格 | 完全保留 main.css | 不返工 UI |
| 部署 | 纯静态,Nginx 服务 dist/ | 最简,废弃 PHP |
| Skills 路由 | `/skills/`,`/tech-stack/` 301 重定向 | 与 content/skills/ 一致 |
| 详情页 | Projects/Learning/Blog 独立详情页 | 长内容需要 |
| 图片存放 | Markdown 同名子目录 | Astro 原生支持 |
| 旧文件 | 直接删除不备份 | 用户明确要求 |

---

## 3. 项目结构

```text
server/                          # 项目根
├── astro.config.mjs             # Astro 配置(integrations: mdx, sitemap)
├── package.json
├── tsconfig.json
├── src/
│   ├── content/
│   │   ├── config.ts            # 所有集合的 Zod schema 定义
│   │   ├── site.yml             # 网站全局配置
│   │   ├── about/
│   │   │   └── profile.yml
│   │   ├── currently/
│   │   │   └── currently.yml
│   │   ├── timeline/
│   │   │   └── timeline.yml
│   │   ├── skills/
│   │   │   └── skills.yml
│   │   ├── gallery/
│   │   │   └── gallery.yml
│   │   ├── projects/
│   │   │   ├── smart-cart.md
│   │   │   ├── smart-cart/      # 同名子目录放图片
│   │   │   │   └── cover.jpg
│   │   │   ├── woodscan.md
│   │   │   └── woodscan/
│   │   │       └── cover.jpg
│   │   ├── learning/
│   │   │   ├── 2026-07-12-linux.md
│   │   │   └── 2026-06-28-freertos.md
│   │   └── blog/
│   │       └── hello-world.md
│   ├── layouts/
│   │   └── Base.astro           # <html> + <head> + Nav + Footer + slot
│   ├── components/
│   │   ├── Nav.astro            # 导航(从 site.yml 读导航项)
│   │   ├── Footer.astro         # 页脚(从 site.yml 读 slogan/links)
│   │   ├── ThemeToggle.astro    # 暗色模式切换(保留现有 JS)
│   │   ├── Pill.astro           # 标签胶囊
│   │   ├── ProjectCard.astro    # 项目卡片
│   │   ├── LearningItem.astro   # 学习列表项
│   │   ├── BlogCard.astro       # 博客卡片
│   │   ├── GalleryGrid.astro    # 相册网格
│   │   ├── TimelineItem.astro   # 时间轴项
│   │   ├── SkillGroup.astro     # 技能分组
│   │   ├── CurrentlyCard.astro  # "最近状态"卡片
│   │   └── TOC.astro            # 博客详情页目录
│   ├── pages/
│   │   ├── index.astro          # /
│   │   ├── about.astro          # /about/
│   │   ├── projects/
│   │   │   ├── index.astro      # /projects/
│   │   │   └── [slug].astro     # /projects/{slug}/
│   │   ├── learning/
│   │   │   ├── index.astro      # /learning/
│   │   │   └── [slug].astro     # /learning/{slug}/
│   │   ├── blog/
│   │   │   ├── index.astro      # /blog/
│   │   │   └── [slug].astro     # /blog/{slug}/
│   │   ├── skills.astro         # /skills/
│   │   ├── timeline.astro       # /timeline/
│   │   ├── gallery.astro        # /gallery/
│   │   ├── contact.astro        # /contact/
│   │   └── tech-stack.astro     # /tech-stack/ → 301 /skills/
│   ├── styles/
│   │   └── main.css             # 直接复用现有文件
│   └── lib/
│       └── content.ts           # 读取 YAML 配置的辅助函数
├── public/
│   └── favicon.svg
└── scripts/
    └── migrate-wp.ts            # WP → Markdown 迁移脚本(一次性)
```

---

## 4. Content Schema 定义

### 4.1 site.yml(全局配置)

```yaml
# src/content/site.yml
name: "snhgn"
slogan: "Stay curious, keep building."
slogan_zh: "保持好奇,持续创造"
description: "A digital garden recording the journey of an aspiring Robotics & AI Engineer."
url: "https://snhgn.me"
email: "hi@snhgn.me"
github: "https://github.com/snhgn"
avatar: "/favicon.svg"
nav:
  - label: "Projects"
    href: "/projects/"
  - label: "Learning"
    href: "/learning/"
  - label: "Skills"
    href: "/skills/"
  - label: "Timeline"
    href: "/timeline/"
  - label: "Blog"
    href: "/blog/"
  - label: "Gallery"
    href: "/gallery/"
  - label: "About"
    href: "/about/"
footer:
  copyright: "© {year} snhgn · Digital garden"
  links:
    - label: "GitHub"
      href: "https://github.com/snhgn"
      external: true
    - label: "Blog"
      href: "/blog/"
    - label: "Gallery"
      href: "/gallery/"
    - label: "Contact"
      href: "/contact/"
seo:
  og_type: "website"
  theme_color: "#FAFAFA"
  keywords:
    - "robotics"
    - "embedded"
    - "AI"
    - "digital garden"
```

### 4.2 about/profile.yml

```yaml
# src/content/about/profile.yml
name: "snhgn"
role: "Aspiring Robotics & AI Engineer"
role_zh: "保持好奇 · 持续创造"
avatar: "/favicon.svg"
bio: |
  Aspiring Robotics & AI Engineer. I enjoy understanding how things work —
  from embedded systems and Linux to robotics and artificial intelligence.
  This is my digital garden: a living record of what I learn, build, and think.
bio_zh: |
  林学专业,业余写代码。主攻嵌入式和 Web,记录学习与折腾。
interests:
  - "Embedded Systems"
  - "Linux & Kernel"
  - "Robotics"
  - "AI / Machine Learning"
  - "Web Engineering"
philosophy:
  - "Stay curious, keep building."
  - "Quality over quantity."
  - "Slow is fast."
  - "Understand the system, don't just glue libraries."
social:
  - label: "GitHub"
    href: "https://github.com/snhgn"
    icon: "github"
  - label: "Email"
    href: "mailto:hi@snhgn.me"
    icon: "mail"
education:
  - period: "2022 — 2026"
    school: "BJFU"
    major: "林学"
future_direction: |
  Exploring the intersection of embedded systems and AI —
  bringing intelligence to physical devices.
contact_note: "Best reached via email. I read everything, reply to most."
```

### 4.3 currently/currently.yml(首页"最近状态")

```yaml
# src/content/currently/currently.yml
updated: 2026-07-12
items:
  - category: "Learning"
    content: "Linux kernel modules & device drivers"
  - category: "Building"
    content: "Digital garden v2 — content-driven architecture"
  - category: "Reading"
    content: "《Linux Device Drivers》3rd edition"
  - category: "Thinking"
    content: "How to bridge embedded and AI workflows"
  - category: "Next Goal"
    content: "Ship a complete robotics project end-to-end"
  - category: "Watching"
    content: "Bilibili 嵌入式系统课程"
  - category: "Playing"
    content: "factorio"
```

### 4.4 timeline/timeline.yml

```yaml
# src/content/timeline/timeline.yml
events:
  - date: "2026-07"
    title: "Digital Garden v2 重构"
    category: "milestone"
    description: "迁移到 Astro Content Collections,内容与页面完全分离。"
    tags: ["astro", "refactor"]
  - date: "2026-07"
    title: "Beijing Engineering Training Competition"
    category: "project"
    description: "智能运输小车参赛,完成 PID + 超声波融合方案。"
    tags: ["stm32", "competition"]
  - date: "2026-06"
    title: "woodscan 模型训练完成"
    category: "project"
    description: "木材识别 CNN,12 类 78% top-1 accuracy。"
    tags: ["pytorch", "cnn"]
  # ... 更多事件
```

### 4.5 skills/skills.yml

```yaml
# src/content/skills/skills.yml
groups:
  - category: "Programming"
    items:
      - name: "C"
        level: 4
        note: "嵌入式主力语言"
      - name: "Python"
        level: 4
        note: "AI/ML、脚本工具"
      - name: "JavaScript / TypeScript"
        level: 3
        note: "前端工程"
      - name: "Shell"
        level: 3
  - category: "Embedded"
    items:
      - name: "STM32 / HAL"
        level: 4
      - name: "FreeRTOS"
        level: 3
      - name: "Raspberry Pi"
        level: 3
  - category: "Linux"
    items:
      - name: "命令行 / Shell"
        level: 4
      - name: "systemd / 网络"
        level: 3
      - name: "Kernel modules"
        level: 2
        note: "学习中"
  - category: "AI"
    items:
      - name: "PyTorch"
        level: 3
      - name: "OpenCV"
        level: 3
      - name: "EfficientNet / CNN"
        level: 3
  - category: "Tools"
    items:
      - name: "Git"
        level: 4
      - name: "Docker"
        level: 2
      - name: "Nginx"
        level: 3
  - category: "Cloud"
    items:
      - name: "1Panel"
        level: 3
      - name: "自建服务器"
        level: 3
# level: 1-5
```

### 4.6 gallery/gallery.yml

```yaml
# src/content/gallery/gallery.yml
photos:
  - src: "./photos/2026-07-bjfu/01.jpg"
    title: "校园清晨"
    location: "BJFU, Beijing"
    date: "2026-07-04"
    description: "晨光下的林荫道。"
  - src: "./photos/2026-06-lab/01.jpg"
    title: "实验室"
    location: "实验室"
    date: "2026-06-15"
    description: "调试小车的现场。"
  # ... 更多照片
```

### 4.7 projects 集合(Markdown + frontmatter)

```yaml
# src/content/projects/smart-cart.md
---
title: "Smart Transport Cart"
slug: "smart-cart"
date: 2026-07-01
status: "shipped"           # shipped | in-progress | paused | archived
year: 2026
cover: "./smart-cart/cover.jpg"
tech:
  - "STM32"
  - "FreeRTOS"
  - "C"
  - "PID"
github: "https://github.com/snhgn/smart-cart"
demo: ""
featured: true
order: 1                    # 列表排序(小在前)
description: "A line-following + obstacle-avoiding cart for the 2026 Beijing Engineering Training Competition."
lessons:
  - "PID 调参先 P 后 I 后 D,大振荡减 P,稳态误差加 I。"
  - "FreeRTOS 任务优先级反转要用优先级继承 mutex。"
  - "超声波传感器多探头交替触发,避免串扰。"
---

## 项目背景

2026 北京市工程训练竞赛智能运输小车项目。

## 技术方案

### 硬件
- STM32F103 主控
- TCRT5000 循迹模块 ×5
- HC-SR04 超声波 ×3

### 软件
```c
// PID 核心循环
void pid_update(PID_t *pid, float error) {
    pid->integral += error;
    pid->derivative = error - pid->prev_error;
    pid->output = pid->kp * error
                + pid->ki * pid->integral
                + pid->kd * pid->derivative;
    pid->prev_error = error;
}
```

## 开发过程

(正文支持代码高亮、Mermaid 图、Callout)

## 总结

详见 frontmatter 的 lessons 字段。
```

### 4.8 learning 集合

```yaml
# src/content/learning/2026-07-12-linux.md
---
title: "理解 systemd 依赖图与启动顺序"
slug: "systemd-dependency"
date: 2026-07-12
tags:
  - "linux"
  - "systemd"
summary: "梳理 systemd 的 Wants/Requires/After/Before 语义。"
problems:
  - "服务启动顺序不确定,导致依赖服务未就绪。"
solutions:
  - "用 After= 明确顺序,Wants= 表达软依赖。"
next_steps:
  - "学习 systemd timer 替代 cron。"
---

## 学习内容

(systemd unit 文件解析)

## 遇到的问题

...

## 解决方法

...

## 总结

...

## 下一步计划

...
```

### 4.9 blog 集合

```yaml
# src/content/blog/hello-world.md
---
title: "你好,我是snhgn"
slug: "hello-world"
date: 2026-07-11
tags:
  - "meta"
  - "intro"
category: "杂谈"
reading_time: 2
description: "这个博客的定位和开篇。"
draft: false
---

这个博客搭在 [snhgn.me](https://snhgn.me),作为主页的延伸,
用来记录一些零零碎碎的东西 —— 项目笔记、折腾记录、偶尔的杂谈。

本人林学专业,业余写代码,主攻方向大概是嵌入式和 Web 这两块。
GitHub: [@snhgn](https://github.com/snhgn)。欢迎来串门。
```

---

## 5. Zod Schema(config.ts)

```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content';

// === Markdown 集合 ===
const projects = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    date: z.coerce.date(),
    status: z.enum(['shipped', 'in-progress', 'paused', 'archived']),
    year: z.number(),
    cover: z.string().optional(),
    tech: z.array(z.string()).default([]),
    github: z.string().url().or(z.literal('')).default(''),
    demo: z.string().url().or(z.literal('')).default(''),
    featured: z.boolean().default(false),
    order: z.number().default(99),
    description: z.string(),
    lessons: z.array(z.string()).default([]),
  }),
});

const learning = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    date: z.coerce.date(),
    tags: z.array(z.string()).default([]),
    summary: z.string(),
    problems: z.array(z.string()).default([]),
    solutions: z.array(z.string()).default([]),
    next_steps: z.array(z.string()).default([]),
  }),
});

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    date: z.coerce.date(),
    tags: z.array(z.string()).default([]),
    category: z.string().default('未分类'),
    description: z.string(),
    draft: z.boolean().default(false),
    reading_time: z.number().optional(), // 可选,手填;不填则详情页不显示阅读时间
  }),
});

// === YAML 数据集合 ===
const data = defineCollection({
  type: 'data',
  schema: z.record(z.any()), // 各 YAML 文件单独用更精确的 schema
});

export const collections = { projects, learning, blog, data };
```

**说明:** `site.yml`/`profile.yml`/`currently.yml`/`timeline.yml`/`skills.yml`/`gallery.yml` 都走 `data` 集合,在 `src/lib/content.ts` 里用独立 Zod schema 校验(保持类型安全)。

---

## 6. 页面与数据流

### 6.1 路由表

| 路由 | 页面文件 | 数据源 | 备注 |
|------|----------|--------|------|
| `GET /` | `pages/index.astro` | site.yml + currently.yml + projects[featured] + 最新5条(learning∪blog) | Hero + Currently + Featured + Latest |
| `GET /about/` | `pages/about.astro` | profile.yml | 单页 |
| `GET /projects/` | `pages/projects/index.astro` | projects 集合(按 year desc, order asc) | 列表 |
| `GET /projects/{slug}/` | `pages/projects/[slug].astro` | 单个 project md | 详情 |
| `GET /learning/` | `pages/learning/index.astro` | learning 集合(按 date desc) | 列表 |
| `GET /learning/{slug}/` | `pages/learning/[slug].astro` | 单个 learning md | 详情 |
| `GET /blog/` | `pages/blog/index.astro` | blog 集合(draft=false, 按 date desc) | 列表 + 标签筛选 |
| `GET /blog/{slug}/` | `pages/blog/[slug].astro` | 单个 blog md | 详情 + TOC |
| `GET /skills/` | `pages/skills.astro` | skills.yml | 分组展示 |
| `GET /timeline/` | `pages/timeline.astro` | timeline.yml | 按 date desc |
| `GET /gallery/` | `pages/gallery.astro` | gallery.yml | 网格 |
| `GET /contact/` | `pages/contact.astro` | site.yml | 联系方式 |
| `GET /tech-stack/` | `pages/tech-stack.astro` | — | 301 → /skills/ |

### 6.2 数据流示例(首页)

```astro
---
// src/pages/index.astro
import Base from '../layouts/Base.astro';
import ProjectCard from '../components/ProjectCard.astro';
import CurrentlyCard from '../components/CurrentlyCard.astro';
import { getCollection } from 'astro:content';
import { getSiteConfig, getCurrently } from '../lib/content';

const site = await getSiteConfig();
const currently = await getCurrently();
const projects = (await getCollection('projects'))
  .filter(p => p.data.featured)
  .sort((a, b) => a.data.order - b.data.order);
const learning = (await getCollection('learning'))
  .sort((a, b) => b.data.date.getTime() - a.data.date.getTime())
  .slice(0, 3);
const blog = (await getCollection('blog'))
  .filter(b => !b.data.draft)
  .sort((a, b) => b.data.date.getTime() - a.data.date.getTime())
  .slice(0, 3);
const latest = [...learning, ...blog]
  .sort((a, b) => b.data.date.getTime() - a.data.date.getTime())
  .slice(0, 5);
---
<Base site={site} title={site.name + ' · Digital Garden'}>
  <!-- Hero -->
  <!-- Currently -->
  <!-- Featured Projects -->
  <!-- Latest updates -->
</Base>
```

---

## 7. Markdown 增强配置

```javascript
// astro.config.mjs
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeMermaid from 'rehype-mermaid';
import remarkCallout from './src/plugins/remark-callout.mjs';

export default defineConfig({
  site: 'https://snhgn.me',
  integrations: [mdx(), sitemap()],
  markdown: {
    syntaxHighlight: 'shiki',
    shikiConfig: { theme: 'github-dark' },
    remarkPlugins: [remarkMath, remarkCallout],
    rehypePlugins: [rehypeKatex, [rehypeMermaid, { strategy: 'inline-svg' }]],
  },
});
```

**Callout 语法:**
```markdown
:::note
这是一个笔记。
:::

:::warning
这是一个警告。
:::
```

---

## 8. 视觉一致性保障

1. **直接复用 main.css** — 把 `assets/css/main.css` 复制到 `src/styles/main.css`,在 `Base.astro` 里 import
2. **DOM 结构对齐** — 每个 Astro 组件输出的 HTML class 和结构与现有静态页面完全一致(`.nav`/`.hero`/`.featured`/`.latest-list`/`.card`/`.project`/`.pill` 等)
3. **JS 行为保留** — ThemeToggle、NProgress、reveal 滚动动画的 JS 原样迁移到 `Base.astro` 的 `<script>` 标签
4. **字体加载** — 保留 Google Fonts preconnect + Inter/JetBrains Mono

---

## 9. WordPress 迁移

### 迁移对象
- 1 篇文章:"你好,我是snhgn" (2026-07-11, slug: hello, 507 字符)
- 内容格式:Gutenberg 块(`<!-- wp:paragraph --><p>...</p><!-- /wp:paragraph -->`)

### 迁移步骤(一次性脚本)
1. 从 sqlite 读取 `wp_posts.post_content`
2. 清理 `<!-- wp:* -->` 注释
3. 保留 `<p>` 和 `<a>` 标签,转为 Markdown(段落→空行分隔,`<a href="url">text</a>`→`[text](url)`)
4. 加 frontmatter(title/slug/date/tags/category/description)
5. 输出 `src/content/blog/hello-world.md`

### 验证
- `astro build` 通过
- `/blog/hello-world/` 返回 200 且内容与原 WP 文章一致

---

## 10. 部署链路

### 10.1 本地构建

```bash
npm run build    # 输出到 dist/
```

### 10.2 服务器部署

```bash
# 1. 上传 dist/ 到服务器
scp -r dist/* a@192.168.1.43:/home/a/web/dist/

# 2. 修改 Nginx 配置
# /opt/1panel/apps/openresty/openresty/conf/conf.d/snhgn.me.conf
# 把 location / { proxy_pass http://127.0.0.1:8000; }
# 改为 root /home/a/web/dist; location / { try_files $uri $uri/ $uri.html /404.html; }

# 3. 重载 Nginx
ssh a@192.168.1.43 "openresty -s reload"

# 4. 停止 PHP server 和 WP
ssh a@192.168.1.43 "kill <php-pid>; rm -rf /home/a/web/blog /home/a/web/router.php /home/a/web/index.html ..."
```

### 10.3 Nginx 配置(新)

```nginx
server {
    listen 80;
    server_name snhgn.me;
    root /home/a/web/dist;
    index index.html;

    access_log /www/sites/snhgn.me/log/access.log main;
    error_log  /www/sites/snhgn.me/log/error.log;

    # 静态资源长缓存
    location ~* \.(css|js|jpg|jpeg|png|gif|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Astro 默认输出 /projects/smart-cart/ → /projects/smart-cart/index.html
    # Nginx try_files 自动处理目录→index.html
    location / {
        try_files $uri $uri/ $uri.html /404.html;
    }

    # 旧 /skills/ 已经是新路由,无需重定向
    # 旧 /tech-stack/ → /skills/ (Astro 页面里用 301)
}
```

### 10.4 旧文件清理

服务器 `/home/a/web/` 下删除:
- `index.html`, `about/`, `projects/`, `learning/`, `tech-stack/`, `timeline/`, `gallery/`, `contact/`, `skills/`, `assets/`
- `router.php`
- `blog/`(整个 WordPress)
- `wp-theme/`(主题,本地保留参考)

本地 `server/` 下删除(仅旧静态文件,保留 Astro 项目和 docs/):
- `index.html`, `about/`, `projects/`, `learning/`, `tech-stack/`, `timeline/`, `gallery/`, `contact/`, `skills/`, `assets/`
- `wp-theme/`, `wp.tar.gz`, `sqlite-db.zip`, `deploy-redesign.sh`, `verify-routes.sh`
- 保留:`docs/`、`src/`、`public/`、`package.json`、`astro.config.mjs` 等 Astro 项目文件

---

## 11. 错误处理与边界

1. **frontmatter 缺失字段** — Zod schema 用 `.default()` 提供合理默认值,缺失不报错
2. **frontmatter 类型错误** — `astro build` 编译失败,显示具体文件和字段
3. **内容文件不存在** — `getCollection` 返回空数组,列表页显示"暂无内容"占位
4. **图片路径错误** — Astro 构建时找不到文件会报错
5. **404 页面** — `src/pages/404.astro` 自定义 404,与现有 404 样式一致
6. **草稿博客** — `draft: true` 的文章不出现在列表,但可通过直接 URL 访问(Astro 默认行为)

---

## 12. 测试策略

### 12.1 构建时验证
- `astro build` 成功无警告
- `astro check` TypeScript 类型检查通过

### 12.2 路由验证(部署后)
脚本验证所有路由返回 200:
```bash
for p in / /about/ /projects/ /learning/ /skills/ /timeline/ /blog/ /gallery/ /contact/ /blog/hello-world/ /tech-stack/; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: snhgn.me" "http://127.0.0.1$p")
  echo "$code  $p"
done
```
预期:全部 200(/tech-stack/ 也可 200,因为 301 后 curl 跟随)

### 12.3 视觉验证
- 首页 Hero / Featured / Latest 与现有页面像素级一致
- 暗色模式切换正常
- 移动端响应式正常

### 12.4 内容验证
- 新增一个 test project md → 构建后出现在 /projects/
- 修改 currently.yml → 首页"最近状态"更新
- 删除 test project md → 构建后从 /projects/ 消失

---

## 13. 实施阶段划分

本 spec 涵盖一个完整实施周期,建议按以下阶段推进(具体步骤由后续 writing-plans 细化):

1. **Astro 项目初始化** — package.json/astro.config/tsconfig,main.css 迁移
2. **内容 schema 与种子内容** — config.ts + 所有 YAML/MD 文件(用现有页面内容填充)
3. **布局与组件** — Base.astro + 所有 components
4. **页面实现** — 9 个页面 + 详情页 + 重定向页
5. **WordPress 迁移** — 1 篇文章转 Markdown
6. **本地构建验证** — astro build + astro check
7. **服务器部署** — 上传 dist/,改 Nginx,清旧文件
8. **线上验证** — 路由 200 + 视觉一致性

---

## 14. 未来扩展(非本次范围)

- RSS 订阅(`@astrojs/rss`)
- 搜索(Pagefind,纯静态)
- 站点地图(已含 `@astrojs/sitemap`)
- Open Graph 图片自动生成(`astro-og-canvas`)
- 分析(Plausible 自建或 Umami)
- 评论(Giscus,基于 GitHub Discussions)

这些可在本次重构完成后按需添加,不影响当前架构。
