# Content-Driven Website Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将静态 HTML 网站重构为 Astro Content Collections 驱动的内容管理系统,实现内容与页面完全分离。

**Architecture:** Astro 静态站点生成器 + Content Collections(Zod schema 校验)+ Markdown/YAML 数据源。编译输出纯静态 HTML,Nginx 直接服务,废弃 PHP server 和 WordPress。

**Tech Stack:** Astro 4.x、TypeScript、Zod、Shiki、remark-math/rehype-katex、rehype-mermaid、自定义 remark-callout 插件

**Spec:** [docs/superpowers/specs/2026-07-12-content-driven-refactor-design.md](file:///c:/Users/snhgn/Desktop/server/docs/superpowers/specs/2026-07-12-content-driven-refactor-design.md)

---

## File Structure

### 新建文件

| 路径 | 职责 |
|------|------|
| `package.json` | 依赖与脚本 |
| `astro.config.mjs` | Astro 配置(integrations + markdown 插件) |
| `tsconfig.json` | TypeScript 配置(继承 astro/tsconfigs/strict) |
| `src/env.d.ts` | Astro 环境类型声明 |
| `src/content/config.ts` | 所有集合的 Zod schema |
| `src/content/site.yml` | 全局配置 |
| `src/content/about/profile.yml` | 个人介绍 |
| `src/content/currently/currently.yml` | 首页"最近状态" |
| `src/content/timeline/timeline.yml` | 时间轴数据 |
| `src/content/skills/skills.yml` | 技术栈数据 |
| `src/content/gallery/gallery.yml` | 相册数据 |
| `src/content/projects/*.md` | 项目 Markdown(至少 2 个种子) |
| `src/content/learning/*.md` | 学习记录 Markdown(至少 2 个种子) |
| `src/content/blog/hello-world.md` | 迁移自 WordPress 的文章 |
| `src/styles/main.css` | 复制自 assets/css/main.css |
| `src/layouts/Base.astro` | 页面骨架(head + Nav + Footer + slot) |
| `src/components/*.astro` | 11 个可复用组件 |
| `src/pages/*.astro` | 13 个路由页面 |
| `src/plugins/remark-callout.mjs` | Callout 自定义插件 |
| `src/lib/content.ts` | YAML 数据读取辅助 |
| `public/favicon.svg` | 站点图标 |
| `scripts/migrate-wp.ts` | WP 迁移脚本(一次性) |

### 删除文件(实施完成后)

- 本地:`index.html`、`about/`、`projects/`、`learning/`、`tech-stack/`、`timeline/`、`gallery/`、`contact/`、`skills/`、`assets/`、`wp-theme/`、`wp.tar.gz`、`sqlite-db.zip`、`deploy-redesign.sh`、`verify-routes.sh`
- 服务器:`/home/a/web/` 下除 `dist/` 外所有文件

---

## Task 1: 初始化 Astro 项目

**Files:**
- Create: `package.json`
- Create: `astro.config.mjs`
- Create: `tsconfig.json`
- Create: `src/env.d.ts`
- Create: `public/favicon.svg`
- Create: `.gitignore`

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "snhgn-digital-garden",
  "type": "module",
  "version": "2.0.0",
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview",
    "check": "astro check"
  },
  "dependencies": {
    "astro": "^4.16.0",
    "@astrojs/mdx": "^3.1.0",
    "@astrojs/sitemap": "^3.2.0",
    "@astrojs/rss": "^4.0.0",
    "remark-math": "^6.0.0",
    "rehype-katex": "^7.0.0",
    "rehype-mermaid": "^3.0.0",
    "katex": "^0.16.0"
  },
  "devDependencies": {
    "@astrojs/check": "^0.9.0",
    "typescript": "^5.6.0"
  }
}
```

- [ ] **Step 2: 创建 astro.config.mjs**

```javascript
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeMermaid from 'rehype-mermaid';
import remarkCallout from './src/plugins/remark-callout.mjs';

export default defineConfig({
  site: 'https://snhgn.me',
  trailingSlash: 'always',
  integrations: [mdx(), sitemap()],
  markdown: {
    syntaxHighlight: 'shiki',
    shikiConfig: { theme: 'github-dark' },
    remarkPlugins: [remarkMath, remarkCallout],
    rehypePlugins: [rehypeKatex, [rehypeMermaid, { strategy: 'inline-svg' }]],
  },
});
```

- [ ] **Step 3: 创建 tsconfig.json**

```json
{
  "extends": "astro/tsconfigs/strict",
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

- [ ] **Step 4: 创建 src/env.d.ts**

```typescript
/// <reference path="../.astro/types.d.ts" />
/// <reference types="astro/client" />
```

- [ ] **Step 5: 创建 public/favicon.svg**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#111827"/>
  <text x="16" y="22" font-family="monospace" font-size="18" font-weight="600" text-anchor="middle" fill="#FAFAFA">s</text>
</svg>
```

- [ ] **Step 6: 创建 .gitignore**

```text
node_modules/
dist/
.astro/
.DS_Store
*.log
.env
.env.production
```

- [ ] **Step 7: 安装依赖**

Run: `npm install`
Expected: 无错误,生成 node_modules/

- [ ] **Step 8: Commit**

```bash
git add package.json astro.config.mjs tsconfig.json src/env.d.ts public/favicon.svg .gitignore
git commit -m "chore: initialize astro project"
```

---

## Task 2: 迁移 main.css

**Files:**
- Create: `src/styles/main.css`(从 `assets/css/main.css` 复制)

- [ ] **Step 1: 复制 main.css**

Run: `Copy-Item -Path "assets\css\main.css" -Destination "src\styles\main.css" -Force`
Expected: 文件存在,内容一致

- [ ] **Step 2: 验证复制成功**

Run: `Test-Path src\styles\main.css`
Expected: True

- [ ] **Step 3: Commit**

```bash
git add src/styles/main.css
git commit -m "chore: migrate main.css to src/styles/"
```

---

## Task 3: 创建 Content Collections Schema

**Files:**
- Create: `src/content/config.ts`

- [ ] **Step 1: 创建 config.ts**

```typescript
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
    reading_time: z.number().optional(),
  }),
});

// === YAML 数据集合(单独 schema 在 lib/content.ts 校验) ===
const data = defineCollection({
  type: 'data',
  schema: z.record(z.any()),
});

export const collections = { projects, learning, blog, data };
```

- [ ] **Step 2: Commit**

```bash
git add src/content/config.ts
git commit -m "feat: add content collections schema"
```

---

## Task 4: 创建 YAML 辅助函数

**Files:**
- Create: `src/lib/content.ts`

- [ ] **Step 1: 创建 content.ts**

```typescript
import { getEntry } from 'astro:content';
import { z } from 'astro:content';

// === 各 YAML 文件的精确 schema ===
const siteSchema = z.object({
  name: z.string(),
  slogan: z.string(),
  slogan_zh: z.string(),
  description: z.string(),
  url: z.string().url(),
  email: z.string().email(),
  github: z.string().url(),
  avatar: z.string(),
  nav: z.array(z.object({
    label: z.string(),
    href: z.string(),
  })),
  footer: z.object({
    copyright: z.string(),
    links: z.array(z.object({
      label: z.string(),
      href: z.string(),
      external: z.boolean().default(false),
    })),
  }),
  seo: z.object({
    og_type: z.string(),
    theme_color: z.string(),
    keywords: z.array(z.string()),
  }),
});

const profileSchema = z.object({
  name: z.string(),
  role: z.string(),
  role_zh: z.string(),
  avatar: z.string(),
  bio: z.string(),
  bio_zh: z.string(),
  interests: z.array(z.string()),
  philosophy: z.array(z.string()),
  social: z.array(z.object({
    label: z.string(),
    href: z.string(),
    icon: z.string(),
  })),
  education: z.array(z.object({
    period: z.string(),
    school: z.string(),
    major: z.string(),
  })),
  future_direction: z.string(),
  contact_note: z.string(),
});

const currentlySchema = z.object({
  updated: z.coerce.date(),
  items: z.array(z.object({
    category: z.string(),
    content: z.string(),
  })),
});

const timelineSchema = z.object({
  events: z.array(z.object({
    date: z.string(),
    title: z.string(),
    category: z.string(),
    description: z.string(),
    tags: z.array(z.string()).default([]),
  })),
});

const skillsSchema = z.object({
  groups: z.array(z.object({
    category: z.string(),
    items: z.array(z.object({
      name: z.string(),
      level: z.number().min(1).max(5),
      note: z.string().optional(),
    })),
  })),
});

const gallerySchema = z.object({
  photos: z.array(z.object({
    src: z.string(),
    title: z.string(),
    location: z.string(),
    date: z.string(),
    description: z.string(),
  })),
});

// === 读取函数 ===
export async function getSiteConfig() {
  const entry = await getEntry('data', 'site');
  return siteSchema.parse(entry.data);
}

export async function getProfile() {
  const entry = await getEntry('data', 'about/profile');
  return profileSchema.parse(entry.data);
}

export async function getCurrently() {
  const entry = await getEntry('data', 'currently/currently');
  return currentlySchema.parse(entry.data);
}

export async function getTimeline() {
  const entry = await getEntry('data', 'timeline/timeline');
  return timelineSchema.parse(entry.data);
}

export async function getSkills() {
  const entry = await getEntry('data', 'skills/skills');
  return skillsSchema.parse(entry.data);
}

export async function getGallery() {
  const entry = await getEntry('data', 'gallery/gallery');
  return gallerySchema.parse(entry.data);
}
```

- [ ] **Step 2: Commit**

```bash
git add src/lib/content.ts
git commit -m "feat: add yaml content loaders with zod validation"
```

---

## Task 5: 创建 site.yml

**Files:**
- Create: `src/content/site.yml`

- [ ] **Step 1: 创建 site.yml**

```yaml
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

- [ ] **Step 2: Commit**

```bash
git add src/content/site.yml
git commit -m "feat: add site config"
```

---

## Task 6: 创建 about/profile.yml

**Files:**
- Create: `src/content/about/profile.yml`

- [ ] **Step 1: 创建 profile.yml**(内容来自现有 about/index.html)

```yaml
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
  - "Artificial Intelligence"
  - "Embedded Systems"
  - "Linux"
  - "Robotics"
  - "Computer Vision"
  - "Networking"
  - "Web Tooling"
philosophy:
  - "我相信真正的工程能力来源于持续学习与实践。我更喜欢理解事物背后的原理,而不仅仅是会使用工具。每一行代码、每一次调试,都是理解世界运作方式的机会。"
  - "技术不仅是一份职业,也是探索世界的一种方式。 — 它能让我把模糊的想法变成可触碰的东西,把"好像可以"变成"真的可以"。"
  - "我记录下来,不是因为我懂了,而是希望未来的自己(或其他正在学的人)不用再踩同样的坑。"
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
  短期(6-12 个月):把 Linux 内核与驱动吃透,完成一个能跑在真机上的机器人控制栈。

  中期(1-2 年):向 Robotics & AI Engineer 收敛。深入 SLAM、强化学习与嵌入式实时系统。

  长期:不预设。但有一个原则不会变 — Stay curious, keep building.
contact_note: "Best reached via email. I read everything, reply to most."
```

- [ ] **Step 2: Commit**

```bash
git add src/content/about/profile.yml
git commit -m "feat: add about profile"
```

---

## Task 7: 创建 currently/timeline/skills/gallery YAML

**Files:**
- Create: `src/content/currently/currently.yml`
- Create: `src/content/timeline/timeline.yml`
- Create: `src/content/skills/skills.yml`
- Create: `src/content/gallery/gallery.yml`

- [ ] **Step 1: 创建 currently.yml**

```yaml
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

- [ ] **Step 2: 创建 timeline.yml**(内容来自首页 latest-list + 现有 timeline)

```yaml
events:
  - date: "2026-07"
    title: "Digital Garden v2 重构"
    category: "milestone"
    description: "迁移到 Astro Content Collections,内容与页面完全分离。"
    tags: ["astro", "refactor"]
  - date: "2026-07"
    title: "理解 systemd 依赖图与启动顺序"
    category: "learning"
    description: "梳理 systemd 的 Wants/Requires/After/Before 语义。"
    tags: ["linux", "systemd"]
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
  - date: "2026-06"
    title: "FreeRTOS queues & tasks"
    category: "learning"
    description: "优先级反转踩坑,学会用优先级继承 mutex。"
    tags: ["freertos", "rtos"]
  - date: "2026-05"
    title: "Nginx reverse proxy + PHP-FPM 部署本站"
    category: "learning"
    description: "理解反向代理、FastCGI、systemd 服务管理。"
    tags: ["nginx", "devops"]
  - date: "2026-05"
    title: "用 strace 追踪系统调用"
    category: "learning"
    description: "理解用户态→内核态切换。"
    tags: ["linux", "kernel"]
```

- [ ] **Step 3: 创建 skills.yml**

```yaml
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
```

- [ ] **Step 4: 创建 gallery.yml**(用占位数据,后续替换真实照片)

```yaml
photos:
  - src: "/gallery/bjfu-morning.jpg"
    title: "校园清晨"
    location: "BJFU, Beijing"
    date: "2026-07-04"
    description: "晨光下的林荫道。"
  - src: "/gallery/lab-debug.jpg"
    title: "实验室调试"
    location: "实验室"
    date: "2026-06-15"
    description: "调试小车的现场。"
  - src: "/gallery/woodscan-demo.jpg"
    title: "woodscan Demo"
    location: "宿舍"
    date: "2026-06-10"
    description: "木材识别模型 Streamlit 界面。"
```

- [ ] **Step 5: Commit**

```bash
git add src/content/currently/ src/content/timeline/ src/content/skills/ src/content/gallery/
git commit -m "feat: add currently/timeline/skills/gallery data"
```

---

## Task 8: 创建项目 Markdown 种子文件

**Files:**
- Create: `src/content/projects/smart-cart.md`
- Create: `src/content/projects/woodscan.md`

- [ ] **Step 1: 创建 smart-cart.md**(内容来自现有 projects/index.html #01)

```markdown
---
title: "Smart Transport Cart"
slug: "smart-cart"
date: 2026-07-01
status: "shipped"
year: 2026
tech:
  - "STM32"
  - "FreeRTOS"
  - "C"
  - "PID"
github: "https://github.com/snhgn/smart-cart"
demo: ""
featured: true
order: 1
description: "A line-following + obstacle-avoiding cart for the 2026 Beijing Engineering Training Competition."
lessons:
  - "PID 调参先 P 后 I 后 D,大振荡减 P,稳态误差加 I。"
  - "FreeRTOS 任务优先级反转要用优先级继承 mutex。"
  - "超声波传感器多探头交替触发,避免串扰。"
---

## 项目背景

2026 北京市工程训练竞赛智能运输小车项目。要求在指定赛道上完成循迹、避障、定点运输。

## 技术方案

### 硬件

- **主控**:STM32F103C8T6
- **循迹**:TCRT5000 红外模块 ×5(数字量)
- **避障**:HC-SR04 超声波 ×3(前/左/右)
- **驱动**:L298N + TT 电机 ×2
- **电源**:18650 锂电池组 7.4V

### 软件架构

FreeRTOS 三任务模型:

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

:::note
实际调试时发现,积分项需要限幅,否则小车在起步时会因积分饱和而冲出赛道。
:::

## 开发过程

1. 原型搭建(面包板验证传感器)
2. PCB 打样(双层板,手工焊接)
3. 固件开发(FreeRTOS + HAL 库)
4. 现场调试(PID 参数整定)

## 总结

竞赛成绩超出预期。最大的收获不是名次,而是对实时系统的理解 — 任务调度、优先级、临界区,这些概念只有动手实现才真正懂。
```

- [ ] **Step 2: 创建 woodscan.md**

```markdown
---
title: "woodscan"
slug: "woodscan"
date: 2026-06-15
status: "shipped"
year: 2025
tech:
  - "PyTorch"
  - "EfficientNet"
  - "OpenCV"
  - "Streamlit"
github: "https://github.com/snhgn/woodscan"
demo: ""
featured: true
order: 2
description: "A CNN trained to classify Chinese wood species from cross-section photos. 12 species, 78% top-1 accuracy."
lessons:
  - "小数据集用迁移学习,从头训练根本不收敛。"
  - "数据增强比模型结构调整更有效。"
  - "Streamlit 部署比 Flask 快十倍,适合个人项目。"
---

## 项目背景

林学专业出身,想用 AI 识别木材种类。现有方法依赖显微镜和经验,希望能用手机拍照就识别。

## 技术方案

- **数据集**:12 种中国常见木材,每种 80-150 张横截面照片,共约 1200 张
- **模型**:EfficientNet-B0 迁移学习(ImageNet 预训练)
- **训练**:PyTorch,5-fold 交叉验证
- **部署**:Streamlit Web 界面

## 结果

| 指标 | 值 |
|------|-----|
| Top-1 Accuracy | 78% |
| Top-3 Accuracy | 92% |
| 模型大小 | 20MB(量化后) |

## 总结

作为学习项目,达到了预期。78% 的准确率离生产级还有差距,主要瓶颈是数据量。下一步计划用合成数据增强。
```

- [ ] **Step 3: Commit**

```bash
git add src/content/projects/
git commit -m "feat: add project seed content"
```

---

## Task 9: 创建 learning Markdown 种子文件

**Files:**
- Create: `src/content/learning/2026-07-12-systemd.md`
- Create: `src/content/learning/2026-06-28-freertos.md`

- [ ] **Step 1: 创建 systemd 学习记录**

```markdown
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
  - "Wants 和 Requires 的区别模糊。"
solutions:
  - "用 After= 明确顺序,Wants= 表达软依赖。"
  - "Requires= 是硬依赖,被依赖服务失败则本服务也失败。"
next_steps:
  - "学习 systemd timer 替代 cron。"
  - "研究 socket activation 机制。"
---

## 学习内容

systemd 的依赖关系分两层:

1. **依赖关系(Wants/Requires)**:决定"要不要启动"
2. **顺序关系(After/Before)**:决定"什么时候启动"

## 关键概念

- `Wants=`:软依赖,即使被依赖服务失败,本服务仍启动
- `Requires=`:硬依赖,被依赖服务失败则本服务也失败
- `After=`:本服务在被依赖服务之后启动
- `Before=`:本服务在被依赖服务之前启动

:::warning
Requires= 只表达依赖,不表达顺序。如果需要顺序,必须同时写 Requires= 和 After=。
:::

## 实战示例

```ini
[Unit]
Description=My Web App
Requires=network-online.target
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/app/main.py
```

## 总结

systemd 的依赖模型比传统 init 脚本清晰得多,但语义容易混淆。关键是区分"依赖"和"顺序"两个维度。
```

- [ ] **Step 2: 创建 freertos 学习记录**

```markdown
---
title: "FreeRTOS queues & tasks — 优先级反转踩坑"
slug: "freertos-priority-inversion"
date: 2026-06-28
tags:
  - "freertos"
  - "rtos"
  - "embedded"
summary: "FreeRTOS 任务优先级反转问题与优先级继承 mutex 的使用。"
problems:
  - "高优先级任务被低优先级任务长时间阻塞。"
  - "使用普通 mutex 导致系统响应不稳定。"
solutions:
  - "改用带优先级继承的 mutex(xSemaphoreCreateMutex)。"
  - "临界区尽量短,避免长时间持锁。"
next_steps:
  - "研究 FreeRTOS 任务通知(task notification)替代队列。"
  - "学习时间片轮转与协作式调度的区别。"
---

## 学习内容

在智能运输小车项目中,三个 FreeRTOS 任务:

- **Task A(高)**:PID 控制,1ms 周期
- **Task B(中)**:传感器读取,10ms 周期
- **Task C(低)**:LCD 显示,100ms 周期

## 遇到的问题

Task A 偶发性延迟,导致 PID 控制周期不稳。用逻辑分析仪抓取发现,Task A 会被 Task C 阻塞长达 5ms。

## 原因分析

**优先级反转**:

1. Task C 获取了共享资源(串口)的锁
2. Task A 抢占 Task C,但要获取同一把锁 → 阻塞
3. Task B 抢占 Task C(因为 C 持锁不能释放)
4. 结果:高优先级 A 被低优先级 C 间接阻塞

## 解决方法

```c
// 错误:二值信号量,无优先级继承
SemaphoreHandle_t lock = xSemaphoreCreateBinary();

// 正确:互斥量,带优先级继承
SemaphoreHandle_t lock = xSemaphoreCreateMutex();
```

`xSemaphoreCreateMutex()` 创建的 mutex 会自动执行优先级继承:当高优先级任务等待锁时,持锁的低优先级任务会被临时提升到相同优先级。

## 总结

实时系统的核心不是"跑得快",而是"可预测"。优先级反转是 RTOS 最经典的坑,理解它才能真正理解实时调度。
```

- [ ] **Step 3: Commit**

```bash
git add src/content/learning/
git commit -m "feat: add learning seed content"
```

---

## Task 10: 迁移 WordPress 文章到 Markdown

**Files:**
- Create: `src/content/blog/hello-world.md`

- [ ] **Step 1: 手动转换 WordPress 文章**

WordPress 原文(清理 Gutenberg 块注释后):

```html
<p>这个博客搭在 <a href="https://snhgn.me">snhgn.me</a>,作为主页的延伸,用来记录一些零零碎碎的东西 —— 项目笔记、折腾记录、偶尔的杂谈。</p>
<p>本人林学专业,业余写代码,主攻方向大概是嵌入式和 Web 这两块。GitHub: <a href="https://github.com/snhgn">@snhgn</a>。欢迎来串门。</p>
```

转为 Markdown 后创建 `src/content/blog/hello-world.md`:

```markdown
---
title: "你好,我是snhgn"
slug: "hello-world"
date: 2026-07-11
tags:
  - "meta"
  - "intro"
category: "杂谈"
description: "这个博客的定位和开篇。"
draft: false
---

这个博客搭在 [snhgn.me](https://snhgn.me),作为主页的延伸,用来记录一些零零碎碎的东西 —— 项目笔记、折腾记录、偶尔的杂谈。

本人林学专业,业余写代码,主攻方向大概是嵌入式和 Web 这两块。GitHub: [@snhgn](https://github.com/snhgn)。欢迎来串门。
```

- [ ] **Step 2: Commit**

```bash
git add src/content/blog/hello-world.md
git commit -m "feat: migrate wp hello-world post to markdown"
```

---

## Task 11: 创建 remark-callout 插件

**Files:**
- Create: `src/plugins/remark-callout.mjs`

- [ ] **Step 1: 创建插件**

```javascript
// src/plugins/remark-callout.mjs
// 支持 :::note / :::warning / :::tip / :::danger 容器语法
import { visit } from 'unist-util-visit';

const CALLOUT_TYPES = ['note', 'warning', 'tip', 'danger'];

export default function remarkCallout() {
  return (tree) => {
    visit(tree, 'paragraph', (node, index, parent) => {
      if (!parent || index === null) return;
      const text = node.children?.[0];
      if (text?.type !== 'text') return;

      const match = text.value.match(/^:::(\w+)\s*$/);
      if (!match) return;
      const type = match[1];
      if (!CALLOUT_TYPES.includes(type)) return;

      // 收集后续直到 ::: 的节点
      const siblings = parent.children;
      let endIndex = index + 1;
      const content = [];
      while (endIndex < siblings.length) {
        const next = siblings[endIndex];
        if (
          next.type === 'paragraph' &&
          next.children?.[0]?.type === 'text' &&
          /^:::\s*$/.test(next.children[0].value)
        ) {
          break;
        }
        content.push(next);
        endIndex++;
      }

      // 替换为 div 节点
      siblings.splice(index, endIndex - index + 1, {
        type: 'div',
        data: { hName: 'div', hProperties: { className: ['callout', `callout--${type}`] } },
        children: [
          { type: 'paragraph', children: [{ type: 'text', value: type.toUpperCase() }] },
          ...content,
        ],
      });
    });
  };
}
```

- [ ] **Step 2: 添加 callout 样式到 main.css 末尾**

在 `src/styles/main.css` 末尾追加:

```css
/* -------------------------------------------------------------------------
   Callout (Markdown custom directive)
   ------------------------------------------------------------------------- */
.callout {
  padding: var(--s-4) var(--s-5);
  margin: var(--s-5) 0;
  border-left: 3px solid var(--border-strong);
  border-radius: var(--r-sm);
  background: var(--surface-sunken);
}
.callout > p:first-child {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin: 0 0 var(--s-2) 0;
}
.callout--note { border-left-color: var(--accent); }
.callout--warning { border-left-color: #F59E0B; }
.callout--tip { border-left-color: var(--success); }
.callout--danger { border-left-color: #EF4444; }
.callout--warning > p:first-child { color: #F59E0B; }
.callout--danger > p:first-child { color: #EF4444; }
.callout--tip > p:first-child { color: var(--success); }
```

- [ ] **Step 3: Commit**

```bash
git add src/plugins/remark-callout.mjs src/styles/main.css
git commit -m "feat: add remark-callout plugin and styles"
```

---

## Task 12: 创建 Base 布局

**Files:**
- Create: `src/layouts/Base.astro`

- [ ] **Step 1: 创建 Base.astro**

```astro
---
import '../styles/main.css';
import Nav from '../components/Nav.astro';
import Footer from '../components/Footer.astro';

interface Props {
  title: string;
  description?: string;
  activePath?: string;
}

const { title, description, activePath } = Astro.props;

// 从 site.yml 读取(避免每个页面重复传)
import { getSiteConfig } from '../lib/content';
const site = await getSiteConfig();
const fullTitle = title === site.name ? `${site.name} · Digital Garden` : `${title} · ${site.name}`;
const desc = description || site.description;
const year = new Date().getFullYear();
const copyright = site.footer.copyright.replace('{year}', String(year));
---
<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{fullTitle}</title>
  <meta name="description" content={desc}>
  <meta name="theme-color" content={site.seo.theme_color}>
  <meta property="og:title" content={fullTitle}>
  <meta property="og:description" content={desc}>
  <meta property="og:type" content={site.seo.og_type}>
  <meta name="keywords" content={site.seo.keywords.join(', ')}>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.0/dist/katex.min.css">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
</head>
<body class="fade-in">

  <div id="nprogress"></div>

  <Nav site={site} activePath={activePath} />

  <main>
    <slot />
  </main>

  <Footer site={site} copyright={copyright} />

  <script is:inline>
  // theme toggle
  (function(){
    var saved = localStorage.getItem('theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (saved) document.documentElement.setAttribute('data-theme', saved);
    else if (prefersDark) document.documentElement.setAttribute('data-theme', 'dark');
    var btn = document.getElementById('themeToggle');
    if (btn) btn.addEventListener('click', function(){
      var cur = document.documentElement.getAttribute('data-theme');
      var next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
    });
  })();
  // progress bar
  var bar = document.getElementById('nprogress');
  if (bar) {
    requestAnimationFrame(function(){ bar.classList.add('go'); });
    window.addEventListener('load', function(){
      bar.classList.remove('go');
      bar.classList.add('done');
      setTimeout(function(){ bar.remove(); }, 600);
    });
  }
  // reveal on scroll
  (function(){
    var els = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window)) { els.forEach(function(e){ e.classList.add('in'); }); return; }
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(en, i){
        if (en.isIntersecting) {
          setTimeout(function(){ en.target.classList.add('in'); }, i * 60);
          io.unobserve(en.target);
        }
      });
    }, { rootMargin: '-10% 0px' });
    els.forEach(function(e){ io.observe(e); });
  })();
  </script>

</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add src/layouts/Base.astro
git commit -m "feat: add base layout with nav/footer/scripts"
```

---

## Task 13: 创建 Nav 和 Footer 组件

**Files:**
- Create: `src/components/Nav.astro`
- Create: `src/components/Footer.astro`

- [ ] **Step 1: 创建 Nav.astro**

```astro
---
interface NavItem {
  label: string;
  href: string;
}
interface SiteConfig {
  name: string;
  github: string;
  nav: NavItem[];
}
interface Props {
  site: SiteConfig;
  activePath?: string;
}
const { site, activePath } = Astro.props;
---
<header class="nav">
  <div class="nav__inner">
    <a class="nav__logo" href="/" aria-label="Home">
      <span class="nav__logo-mark">s</span>
      <span>{site.name}</span>
    </a>
    <nav>
      <ul class="nav__links">
        {site.nav.map(item => (
          <li>
            <a class={`nav__link${activePath === item.href ? ' is-active' : ''}`} href={item.href}>
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
    <div class="nav__right">
      <a class="nav__link" href={site.github} target="_blank" rel="noopener" aria-label="GitHub">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .5C5.7.5.5 5.7.5 12c0 5.1 3.3 9.4 7.8 10.9.6.1.8-.2.8-.5v-2c-3.2.7-3.9-1.4-3.9-1.4-.5-1.3-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.7 1.3 3.4 1 .1-.8.4-1.3.8-1.6-2.6-.3-5.3-1.3-5.3-5.7 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2.9-.3 2-.4 3-.4s2 .1 3 .4c2.3-1.6 3.3-1.2 3.3-1.2.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.1 0 4.4-2.7 5.4-5.3 5.7.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.5 4.5-1.5 7.8-5.8 7.8-10.9C23.5 5.7 18.3.5 12 .5z"/></svg>
      </a>
      <button class="theme-toggle" id="themeToggle" aria-label="Toggle theme">
        <svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        <svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>
      </button>
    </div>
  </div>
</header>
```

- [ ] **Step 2: 创建 Footer.astro**

```astro
---
interface SiteConfig {
  slogan: string;
  slogan_zh: string;
  footer: {
    copyright: string;
    links: { label: string; href: string; external?: boolean }[];
  };
}
interface Props {
  site: SiteConfig;
  copyright: string;
}
const { site, copyright } = Astro.props;
---
<footer class="footer">
  <div class="footer__inner">
    <h2 class="footer__tag">Stay curious, <span>keep building.</span></h2>
    <p class="footer__signoff">{site.slogan_zh} — Thanks for visiting.</p>
    <div class="footer__row">
      <span class="mono-text">{copyright}</span>
      <div class="footer__links">
        {site.footer.links.map(link => (
          <a href={link.href} target={link.external ? '_blank' : undefined} rel={link.external ? 'noopener' : undefined}>
            {link.label}
          </a>
        ))}
        <a href={`mailto:${'hi@snhgn.me'}`}>hi@snhgn.me</a>
      </div>
    </div>
  </div>
</footer>
```

- [ ] **Step 3: Commit**

```bash
git add src/components/Nav.astro src/components/Footer.astro
git commit -m "feat: add nav and footer components"
```

---

## Task 14: 创建可复用展示组件

**Files:**
- Create: `src/components/Pill.astro`
- Create: `src/components/ProjectCard.astro`
- Create: `src/components/LearningItem.astro`
- Create: `src/components/BlogCard.astro`
- Create: `src/components/GalleryGrid.astro`
- Create: `src/components/TimelineItem.astro`
- Create: `src/components/SkillGroup.astro`
- Create: `src/components/CurrentlyCard.astro`
- Create: `src/components/TOC.astro`

- [ ] **Step 1: 创建 Pill.astro**

```astro
---
interface Props {
  variant?: 'default' | 'success' | 'warning' | 'danger';
  children: any;
}
const { variant = 'default', children } = Astro.props;
const cls = variant === 'default' ? 'pill' : `pill pill--${variant}`;
---
<span class={cls}>{children}</span>
```

- [ ] **Step 2: 创建 ProjectCard.astro**

```astro
---
import Pill from './Pill.astro';
interface Project {
  slug: string;
  title: string;
  description: string;
  year: number;
  status: string;
  tech: string[];
  cover?: string;
  order: number;
}
interface Props {
  project: Project;
  index: number;
}
const { project, index } = Astro.props;
const statusVariant = project.status === 'shipped' ? 'success' : 'default';
---
<a class="project reveal" href={`/projects/${project.slug}/`}>
  <div class="project__head">
    <div>
      <div class="row" style="gap:10px;margin-bottom:6px">
        <span class="project__index mono">#{String(index).padStart(2, '0')}</span>
        <Pill variant={statusVariant}><span class="dot"></span> {project.status}</Pill>
        <Pill>{project.year}</Pill>
      </div>
      <h2 class="project__title">
        {project.title}
        <span class="pill mono" style="font-size:10px">{project.tech.slice(0, 3).join(' · ')}</span>
      </h2>
      <p class="project__desc">{project.description}</p>
    </div>
  </div>
  <div class="project__meta">
    {project.tech.map(t => <span class="pill">{t}</span>)}
    <span class="project__links" style="margin-left:auto">
      <a href={`/projects/${project.slug}/`}>View details →</a>
    </span>
  </div>
</a>
```

- [ ] **Step 3: 创建 LearningItem.astro**

```astro
---
interface LearningEntry {
  slug: string;
  title: string;
  date: Date;
  tags: string[];
  summary: string;
}
interface Props {
  entry: LearningEntry;
}
const { entry } = Astro.props;
const dateStr = `${entry.date.getFullYear()}.${String(entry.date.getMonth() + 1).padStart(2, '0')}.${String(entry.date.getDate()).padStart(2, '0')}`;
---
<article class="latest-item reveal">
  <span class="latest-item__date">{dateStr}</span>
  <span class="latest-item__tag">Learning</span>
  <a href={`/learning/${entry.slug}/`} class="latest-item__text">{entry.title}</a>
</article>
```

- [ ] **Step 4: 创建 BlogCard.astro**

```astro
---
interface BlogEntry {
  slug: string;
  title: string;
  date: Date;
  tags: string[];
  category: string;
  description: string;
  reading_time?: number;
}
interface Props {
  post: BlogEntry;
}
const { post } = Astro.props;
const dateStr = `${post.date.getFullYear()}.${String(post.date.getMonth() + 1).padStart(2, '0')}.${String(post.date.getDate()).padStart(2, '0')}`;
---
<article class="card reveal">
  <div class="card__body">
    <div class="row" style="gap:8px;margin-bottom:8px">
      <span class="pill">{post.category}</span>
      <span class="muted small mono">{dateStr}</span>
      {post.reading_time && <span class="muted small mono">{post.reading_time} min</span>}
    </div>
    <h3 class="card__title">
      <a href={`/blog/${post.slug}/`}>{post.title}</a>
    </h3>
    <p class="card__desc">{post.description}</p>
    <div class="card__meta">
      {post.tags.map(t => <span class="pill">{t}</span>)}
    </div>
  </div>
</article>
```

- [ ] **Step 5: 创建 GalleryGrid.astro**

```astro
---
interface Photo {
  src: string;
  title: string;
  location: string;
  date: string;
  description: string;
}
interface Props {
  photos: Photo[];
}
const { photos } = Astro.props;
---
<div class="grid grid--3">
  {photos.map(photo => (
    <figure class="gallery__item reveal">
      <div class="gallery__img-wrap">
        <img src={photo.src} alt={photo.title} loading="lazy" />
      </div>
      <figcaption>
        <h3 class="gallery__title">{photo.title}</h3>
        <p class="muted small">{photo.location} · {photo.date}</p>
        <p class="gallery__desc">{photo.description}</p>
      </figcaption>
    </figure>
  ))}
</div>
```

- [ ] **Step 6: 创建 TimelineItem.astro**

```astro
---
interface TimelineEvent {
  date: string;
  title: string;
  category: string;
  description: string;
  tags: string[];
}
interface Props {
  event: TimelineEvent;
}
const { event } = Astro.props;
---
<li class="timeline__item reveal">
  <div class="timeline__dot"></div>
  <div class="timeline__content">
    <span class="timeline__date mono">{event.date}</span>
    <h3 class="timeline__title">{event.title}</h3>
    <span class="pill">{event.category}</span>
    <p class="timeline__desc">{event.description}</p>
    {event.tags.length > 0 && (
      <div class="timeline__tags">
        {event.tags.map(t => <span class="pill">{t}</span>)}
      </div>
    )}
  </div>
</li>
```

- [ ] **Step 7: 创建 SkillGroup.astro**

```astro
---
interface Skill {
  name: string;
  level: number;
  note?: string;
}
interface Props {
  category: string;
  items: Skill[];
}
const { category, items } = Astro.props;
// level 1-5 → 进度条字符
const levelBar = (lvl: number) => '█'.repeat(lvl) + '░'.repeat(5 - lvl);
---
<div class="skill-group">
  <h3 class="skill-group__title">{category}</h3>
  <ul class="skill-list" style="list-style:none;padding:0;margin:0">
    {items.map(skill => (
      <li class="skill">
        <span class="skill__name">{skill.name}</span>
        <span class="skill__level mono">{levelBar(skill.level)} {skill.note || ''}</span>
      </li>
    ))}
  </ul>
</div>
```

- [ ] **Step 8: 创建 CurrentlyCard.astro**

```astro
---
interface CurrentlyItem {
  category: string;
  content: string;
}
interface Props {
  items: CurrentlyItem[];
  updated: Date;
}
const { items, updated } = Astro.props;
const dateStr = `${updated.getFullYear()}.${String(updated.getMonth() + 1).padStart(2, '0')}.${String(updated.getDate()).padStart(2, '0')}`;
---
<div class="currently reveal">
  <div class="currently__head">
    <span class="eyebrow">Currently</span>
    <span class="muted small mono">updated {dateStr}</span>
  </div>
  <div class="currently__grid">
    {items.map(item => (
      <div class="currently__item">
        <span class="currently__cat mono">{item.category}</span>
        <span class="currently__content">{item.content}</span>
      </div>
    ))}
  </div>
</div>
```

- [ ] **Step 9: 创建 TOC.astro**(博客详情页目录)

```astro
---
interface TocItem {
  depth: number;
  slug: string;
  text: string;
}
interface Props {
  headings: TocItem[];
}
const { headings } = Astro.props;
const filtered = headings.filter(h => h.depth >= 2 && h.depth <= 3);
---
{filtered.length > 0 && (
  <nav class="toc" aria-label="Table of contents">
    <span class="eyebrow">Contents</span>
    <ul>
      {filtered.map(h => (
        <li class={`toc__item toc__item--${h.depth}`}>
          <a href={`#${h.slug}`}>{h.text}</a>
        </li>
      ))}
    </ul>
  </nav>
)}
```

- [ ] **Step 10: Commit**

```bash
git add src/components/
git commit -m "feat: add reusable display components"
```

---

## Task 15: 创建首页

**Files:**
- Create: `src/pages/index.astro`

- [ ] **Step 1: 创建首页**

```astro
---
import Base from '../layouts/Base.astro';
import ProjectCard from '../components/ProjectCard.astro';
import CurrentlyCard from '../components/CurrentlyCard.astro';
import { getCollection } from 'astro:content';
import { getSiteConfig, getCurrently } from '../lib/content';

const site = await getSiteConfig();
const currently = await getCurrently();

const allProjects = (await getCollection('projects'))
  .sort((a, b) => a.data.order - b.data.order);
const featured = allProjects.filter(p => p.data.featured).slice(0, 2);

const learning = (await getCollection('learning'))
  .sort((a, b) => b.data.date.getTime() - a.data.date.getTime());
const blog = (await getCollection('blog'))
  .filter(b => !b.data.draft)
  .sort((a, b) => b.data.date.getTime() - a.data.date.getTime());

const latest = [
  ...learning.map(l => ({ type: 'Learning', date: l.data.date, slug: l.data.slug, title: l.data.title, href: `/learning/${l.data.slug}/` })),
  ...blog.map(b => ({ type: 'Blog', date: b.data.date, slug: b.data.slug, title: b.data.title, href: `/blog/${b.data.slug}/` })),
]
  .sort((a, b) => b.date.getTime() - a.date.getTime())
  .slice(0, 5);
---
<Base title={site.name} description={site.description}>

  <!-- HERO -->
  <section class="hero">
    <div class="container">
      <div class="hero__inner">
        <div>
          <div class="hero__greeting">Hi, I'm <span class="ink">{site.name}</span>.</div>
          <h1 class="hero__title">
            Stay curious,<br>
            <em>keep building.</em>
          </h1>
          <div class="hero__role mono">{site.slogan_zh}</div>
          <p class="hero__lead">{site.description}</p>
          <div class="hero__ctas">
            <a class="btn btn--primary btn--lg" href="/projects/">
              View Projects <span class="arrow">→</span>
            </a>
            <a class="btn btn--secondary btn--lg" href="/about/">About me</a>
          </div>
          <div class="hero__meta">
            <span class="hero__meta-item"><span class="hero__meta-dot"></span> {currently.items[0]?.content || 'Currently building'}</span>
            <span class="hero__meta-item mono">BJFU · 林学</span>
          </div>
        </div>
        <div class="hero__avatar" aria-hidden="true">
          <span class="hero__avatar-glyph">s/</span>
          <span class="hero__avatar-tag">v.2026 · digital garden</span>
        </div>
      </div>
    </div>
  </section>

  <!-- CURRENTLY -->
  <section>
    <div class="container container--narrow">
      <CurrentlyCard items={currently.items} updated={currently.updated} />
    </div>
  </section>

  <!-- FEATURED -->
  <section>
    <div class="container">
      <div class="section-head">
        <div>
          <span class="eyebrow">Featured</span>
          <h2 class="section-head__title h2">Selected work</h2>
        </div>
        <a class="section-head__count" href="/projects/">All projects →</a>
      </div>
      <div class="featured">
        {featured.map((p, i) => <ProjectCard project={p.data} index={i + 1} />)}
      </div>
    </div>
  </section>

  <!-- LATEST -->
  <section>
    <div class="container container--narrow">
      <div class="section-head">
        <div>
          <span class="eyebrow">Latest</span>
          <h2 class="section-head__title h2">Recent updates</h2>
        </div>
      </div>
      <ul class="latest-list">
        {latest.map(item => (
          <li class="latest-item reveal">
            <span class="latest-item__date">
              {`${item.date.getFullYear()}.${String(item.date.getMonth() + 1).padStart(2, '0')}.${String(item.date.getDate()).padStart(2, '0')}`}
            </span>
            <span class="latest-item__tag">{item.type}</span>
            <a href={item.href} class="latest-item__text">{item.title}</a>
          </li>
        ))}
      </ul>
    </div>
  </section>

  <!-- PILLARS -->
  <section>
    <div class="container">
      <div class="section-head">
        <div>
          <span class="eyebrow">Explore</span>
          <h2 class="section-head__title h2">Where to start</h2>
        </div>
        <span class="section-head__count">06 sections</span>
      </div>
      <div class="grid grid--3">
        {site.nav.map(item => (
          <a class="card reveal" href={item.href}>
            <h3 class="card__title">{item.label} <span class="arrow">→</span></h3>
          </a>
        ))}
      </div>
    </div>
  </section>

</Base>
```

- [ ] **Step 2: Commit**

```bash
git add src/pages/index.astro
git commit -m "feat: add home page"
```

---

## Task 16: 创建 About 页面

**Files:**
- Create: `src/pages/about.astro`

- [ ] **Step 1: 创建 about.astro**

```astro
---
import Base from '../layouts/Base.astro';
import { getProfile } from '../lib/content';

const profile = await getProfile();
---
<Base title="About" description={`${profile.name} — ${profile.role}`} activePath="/about/">

  <section class="intro">
    <div class="container">
      <span class="eyebrow intro__eyebrow">About</span>
      <h1 class="intro__title">A forestry student, building things that move.</h1>
      <p class="intro__lead">{profile.bio}</p>
    </div>
  </section>

  <section>
    <div class="container container--narrow">
      <span class="eyebrow" style="display:block;margin-bottom:24px">My philosophy</span>
      <div class="philosophy">
        {profile.philosophy.map(p => <p>{p}</p>)}
      </div>
    </div>
  </section>

  <section>
    <div class="container">
      <div class="section-head">
        <div>
          <span class="eyebrow">Interests</span>
          <h2 class="section-head__title h2">What I keep coming back to</h2>
        </div>
        <span class="section-head__count">{String(profile.interests.length).padStart(2, '0')} areas</span>
      </div>
      <div class="skill-group">
        <ul class="skill-list" style="list-style:none;padding:0;margin:0">
          {profile.interests.map(interest => (
            <li class="skill">
              <span class="skill__name">{interest}</span>
              <span class="skill__level mono">███████████ active</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  </section>

  <section>
    <div class="container container--narrow">
      <div class="section-head">
        <div>
          <span class="eyebrow">Future direction</span>
          <h2 class="section-head__title h2">Where I'm heading</h2>
        </div>
        <span class="section-head__count">next 2 years</span>
      </div>
      <div class="philosophy">
        {profile.future_direction.split('\n\n').map(p => <p set:html={p} />)}
      </div>
    </div>
  </section>

  <section>
    <div class="container container--narrow">
      <div class="section-head">
        <div>
          <span class="eyebrow">Get in touch</span>
          <h2 class="section-head__title h2">Find me elsewhere</h2>
        </div>
      </div>
      <ul style="list-style:none;padding:0;margin:0" class="stack">
        {profile.social.map(s => (
          <li class="row row--between" style="padding:16px 0;border-bottom:1px solid var(--border)">
            <span class="ink">{s.label}</span>
            <a class="link" href={s.href} target={s.icon === 'github' ? '_blank' : undefined} rel={s.icon === 'github' ? 'noopener' : undefined}>
              {s.label === 'GitHub' ? '@snhgn →' : s.href.replace('mailto:', '') + ' →'}
            </a>
          </li>
        ))}
        {profile.education.map(edu => (
          <li class="row row--between" style="padding:16px 0;border-bottom:1px solid var(--border)">
            <span class="ink">University</span>
            <span class="muted small">{edu.school} · {edu.major}</span>
          </li>
        ))}
      </ul>
    </div>
  </section>

</Base>
```

- [ ] **Step 2: Commit**

```bash
git add src/pages/about.astro
git commit -m "feat: add about page"
```

---

## Task 17: 创建 Projects 列表与详情页

**Files:**
- Create: `src/pages/projects/index.astro`
- Create: `src/pages/projects/[slug].astro`

- [ ] **Step 1: 创建列表页**

```astro
---
import Base from '../../layouts/Base.astro';
import ProjectCard from '../../components/ProjectCard.astro';
import { getCollection } from 'astro:content';

const projects = (await getCollection('projects'))
  .sort((a, b) => {
    if (b.data.year !== a.data.year) return b.data.year - a.data.year;
    return a.data.order - b.data.order;
  });
---
<Base title="Projects" description="A small, curated list of projects." activePath="/projects/">

  <section class="intro">
    <div class="container">
      <span class="eyebrow intro__eyebrow">Projects</span>
      <h1 class="intro__title">{projects.length} projects, well documented.</h1>
      <p class="intro__lead">
        I prefer to build a few things deeply than a lot of things shallowly.
        Each one below has a development log and a few things I learned the hard way.
      </p>
    </div>
  </section>

  <section>
    <div class="container container--narrow">
      {projects.map((p, i) => <ProjectCard project={p.data} index={i + 1} />)}
    </div>
  </section>

</Base>
```

- [ ] **Step 2: 创建详情页**

```astro
---
import Base from '../../layouts/Base.astro';
import Pill from '../../components/Pill.astro';
import { getCollection } from 'astro:content';

export async function getStaticPaths() {
  const projects = await getCollection('projects');
  return projects.map(p => ({
    params: { slug: p.data.slug },
    props: { project: p },
  }));
}

const { project } = Astro.props;
const { Content } = await project.render();
const statusVariant = project.data.status === 'shipped' ? 'success' : 'default';
---
<Base title={project.data.title} description={project.data.description} activePath="/projects/">

  <section class="intro">
    <div class="container">
      <span class="eyebrow intro__eyebrow">Project</span>
      <h1 class="intro__title">{project.data.title}</h1>
      <p class="intro__lead">{project.data.description}</p>
      <div class="row" style="gap:10px;margin-top:16px">
        <Pill variant={statusVariant}><span class="dot"></span> {project.data.status}</Pill>
        <Pill>{project.data.year}</Pill>
        {project.data.tech.map(t => <Pill>{t}</Pill>)}
      </div>
      <div class="row" style="gap:16px;margin-top:16px">
        {project.data.github && (
          <a class="link" href={project.data.github} target="_blank" rel="noopener">GitHub →</a>
        )}
        {project.data.demo && (
          <a class="link" href={project.data.demo} target="_blank" rel="noopener">Live demo →</a>
        )}
      </div>
    </div>
  </section>

  {project.data.lessons.length > 0 && (
    <section>
      <div class="container container--narrow">
        <div class="section-head">
          <div>
            <span class="eyebrow">Lessons learned</span>
            <h2 class="section-head__title h2">What I took away</h2>
          </div>
        </div>
        <ul class="stack" style="list-style:none;padding:0;margin:0">
          {project.data.lessons.map((lesson, i) => (
            <li class="row" style="gap:12px;padding:12px 0;border-bottom:1px solid var(--border)">
              <span class="mono muted">{String(i + 1).padStart(2, '0')}</span>
              <span>{lesson}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )}

  <section>
    <div class="container container--narrow">
      <div class="prose">
        <Content />
      </div>
    </div>
  </section>

</Base>
```

- [ ] **Step 3: 添加 .prose 样式到 main.css 末尾**

```css
/* -------------------------------------------------------------------------
   Prose (Markdown rendered content)
   ------------------------------------------------------------------------- */
.prose { line-height: 1.7; }
.prose h2 { margin: 2em 0 0.6em; font-size: 1.5em; font-weight: 600; }
.prose h3 { margin: 1.6em 0 0.5em; font-size: 1.2em; font-weight: 600; }
.prose p { margin: 0 0 1em; }
.prose ul, .prose ol { margin: 0 0 1em; padding-left: 1.5em; }
.prose li { margin: 0.4em 0; }
.prose code { font-family: var(--font-mono); font-size: 0.9em; background: var(--surface-sunken); padding: 2px 6px; border-radius: 4px; }
.prose pre { padding: var(--s-4); border-radius: var(--r-md); overflow-x: auto; margin: 0 0 1.2em; }
.prose pre code { background: none; padding: 0; }
.prose blockquote { border-left: 3px solid var(--border-strong); padding-left: var(--s-4); margin: 1em 0; color: var(--muted); }
.prose a { color: var(--accent); text-decoration: none; }
.prose a:hover { text-decoration: underline; }
.prose img { max-width: 100%; border-radius: var(--r-md); margin: 1em 0; }
.prose table { width: 100%; border-collapse: collapse; margin: 1em 0; }
.prose th, .prose td { padding: var(--s-2) var(--s-3); border: 1px solid var(--border); text-align: left; }
.prose th { background: var(--surface-sunken); font-weight: 600; }
```

- [ ] **Step 4: Commit**

```bash
git add src/pages/projects/ src/styles/main.css
git commit -m "feat: add projects list and detail pages"
```

---

## Task 18: 创建 Learning 列表与详情页

**Files:**
- Create: `src/pages/learning/index.astro`
- Create: `src/pages/learning/[slug].astro`

- [ ] **Step 1: 创建列表页**

```astro
---
import Base from '../../layouts/Base.astro';
import { getCollection } from 'astro:content';

const entries = (await getCollection('learning'))
  .sort((a, b) => b.data.date.getTime() - a.data.date.getTime());
---
<Base title="Learning" description="Open learning notebook." activePath="/learning/">

  <section class="intro">
    <div class="container">
      <span class="eyebrow intro__eyebrow">Learning</span>
      <h1 class="intro__title">Open notebook.</h1>
      <p class="intro__lead">What I learned, the pitfalls I hit, and what I want to understand next.</p>
    </div>
  </section>

  <section>
    <div class="container container--narrow">
      <ul class="stack-lg" style="list-style:none;padding:0;margin:0">
        {entries.map(entry => (
          <li class="latest-item reveal" style="display:block;padding:20px 0;border-bottom:1px solid var(--border)">
            <div class="row" style="gap:10px;margin-bottom:6px">
              <span class="mono muted small">
                {`${entry.data.date.getFullYear()}.${String(entry.data.date.getMonth() + 1).padStart(2, '0')}.${String(entry.data.date.getDate()).padStart(2, '0')}`}
              </span>
              {entry.data.tags.map(t => <span class="pill">{t}</span>)}
            </div>
            <h3><a href={`/learning/${entry.data.slug}/`}>{entry.data.title}</a></h3>
            <p class="muted">{entry.data.summary}</p>
          </li>
        ))}
      </ul>
    </div>
  </section>

</Base>
```

- [ ] **Step 2: 创建详情页**

```astro
---
import Base from '../../layouts/Base.astro';
import Pill from '../../components/Pill.astro';
import { getCollection } from 'astro:content';

export async function getStaticPaths() {
  const entries = await getCollection('learning');
  return entries.map(e => ({
    params: { slug: e.data.slug },
    props: { entry: e },
  }));
}

const { entry } = Astro.props;
const { Content } = await entry.render();
---
<Base title={entry.data.title} description={entry.data.summary} activePath="/learning/">

  <section class="intro">
    <div class="container">
      <span class="eyebrow intro__eyebrow">Learning</span>
      <h1 class="intro__title">{entry.data.title}</h1>
      <p class="intro__lead">{entry.data.summary}</p>
      <div class="row" style="gap:10px;margin-top:16px">
        <span class="mono muted small">
          {`${entry.data.date.getFullYear()}.${String(entry.data.date.getMonth() + 1).padStart(2, '0')}.${String(entry.data.date.getDate()).padStart(2, '0')}`}
        </span>
        {entry.data.tags.map(t => <Pill>{t}</Pill>)}
      </div>
    </div>
  </section>

  {entry.data.problems.length > 0 && (
    <section>
      <div class="container container--narrow">
        <span class="eyebrow">Problems</span>
        <ul class="stack" style="list-style:none;padding:0;margin:0">
          {entry.data.problems.map(p => <li style="padding:8px 0;border-bottom:1px solid var(--border)">⚠ {p}</li>)}
        </ul>
      </div>
    </section>
  )}

  <section>
    <div class="container container--narrow">
      <div class="prose"><Content /></div>
    </div>
  </section>

  {entry.data.solutions.length > 0 && (
    <section>
      <div class="container container--narrow">
        <span class="eyebrow">Solutions</span>
        <ul class="stack" style="list-style:none;padding:0;margin:0">
          {entry.data.solutions.map(s => <li style="padding:8px 0;border-bottom:1px solid var(--border)">✓ {s}</li>)}
        </ul>
      </div>
    </section>
  )}

  {entry.data.next_steps.length > 0 && (
    <section>
      <div class="container container--narrow">
        <span class="eyebrow">Next steps</span>
        <ul class="stack" style="list-style:none;padding:0;margin:0">
          {entry.data.next_steps.map(n => <li style="padding:8px 0;border-bottom:1px solid var(--border)">→ {n}</li>)}
        </ul>
      </div>
    </section>
  )}

</Base>
```

- [ ] **Step 3: Commit**

```bash
git add src/pages/learning/
git commit -m "feat: add learning list and detail pages"
```

---

## Task 19: 创建 Blog 列表与详情页

**Files:**
- Create: `src/pages/blog/index.astro`
- Create: `src/pages/blog/[slug].astro`

- [ ] **Step 1: 创建列表页**

```astro
---
import Base from '../../layouts/Base.astro';
import BlogCard from '../../components/BlogCard.astro';
import { getCollection } from 'astro:content';

const posts = (await getCollection('blog'))
  .filter(b => !b.data.draft)
  .sort((a, b) => b.data.date.getTime() - a.data.date.getTime());

// 提取所有标签
const allTags = [...new Set(posts.flatMap(p => p.data.tags))];
---
<Base title="Blog" description="Engineering notes, Linux internals, embedded hacks." activePath="/blog/">

  <section class="intro">
    <div class="container">
      <span class="eyebrow intro__eyebrow">Blog</span>
      <h1 class="intro__title">Notes &amp; essays.</h1>
      <p class="intro__lead">Things I wish I'd read earlier.</p>
    </div>
  </section>

  <section>
    <div class="container">
      {allTags.length > 0 && (
        <div class="row" style="gap:8px;margin-bottom:24px;flex-wrap:wrap">
          {allTags.map(t => <span class="pill">{t}</span>)}
        </div>
      )}
      <div class="grid grid--2">
        {posts.map(post => <BlogCard post={post.data} />)}
      </div>
    </div>
  </section>

</Base>
```

- [ ] **Step 2: 创建详情页**

```astro
---
import Base from '../../layouts/Base.astro';
import Pill from '../../components/Pill.astro';
import TOC from '../../components/TOC.astro';
import { getCollection } from 'astro:content';

export async function getStaticPaths() {
  const posts = await getCollection('blog');
  return posts.map(p => ({
    params: { slug: p.data.slug },
    props: { post: p },
  }));
}

const { post } = Astro.props;
const { Content, headings } = await post.render();
---
<Base title={post.data.title} description={post.data.description} activePath="/blog/">

  <section class="intro">
    <div class="container">
      <span class="eyebrow intro__eyebrow">Blog</span>
      <h1 class="intro__title">{post.data.title}</h1>
      <p class="intro__lead">{post.data.description}</p>
      <div class="row" style="gap:10px;margin-top:16px">
        <span class="mono muted small">
          {`${post.data.date.getFullYear()}.${String(post.data.date.getMonth() + 1).padStart(2, '0')}.${String(post.data.date.getDate()).padStart(2, '0')}`}
        </span>
        {post.data.reading_time && <span class="mono muted small">{post.data.reading_time} min read</span>}
        <Pill>{post.data.category}</Pill>
        {post.data.tags.map(t => <Pill>{t}</Pill>)}
      </div>
    </div>
  </section>

  <section>
    <div class="container">
      <div class="row" style="gap:32px;align-items:flex-start">
        <div class="prose" style="flex:1;min-width:0">
          <Content />
        </div>
        <aside style="flex:0 0 200px;position:sticky;top:80px">
          <TOC headings={headings} />
        </aside>
      </div>
    </div>
  </section>

</Base>
```

- [ ] **Step 3: Commit**

```bash
git add src/pages/blog/
git commit -m "feat: add blog list and detail pages with toc"
```

---

## Task 20: 创建 Skills/Timeline/Gallery/Contact 页面

**Files:**
- Create: `src/pages/skills.astro`
- Create: `src/pages/timeline.astro`
- Create: `src/pages/gallery.astro`
- Create: `src/pages/contact.astro`

- [ ] **Step 1: 创建 skills.astro**

```astro
---
import Base from '../layouts/Base.astro';
import SkillGroup from '../components/SkillGroup.astro';
import { getSkills } from '../lib/content';

const skills = await getSkills();
---
<Base title="Skills" description="Current tech stack and tools." activePath="/skills/">

  <section class="intro">
    <div class="container">
      <span class="eyebrow intro__eyebrow">Skills</span>
      <h1 class="intro__title">Tech I use, and how deep.</h1>
      <p class="intro__lead">Level 1-5. Honest self-assessment.</p>
    </div>
  </section>

  <section>
    <div class="container">
      <div class="grid grid--2">
        {skills.groups.map(g => <SkillGroup category={g.category} items={g.items} />)}
      </div>
    </div>
  </section>

</Base>
```

- [ ] **Step 2: 创建 timeline.astro**

```astro
---
import Base from '../layouts/Base.astro';
import TimelineItem from '../components/TimelineItem.astro';
import { getTimeline } from '../lib/content';

const timeline = await getTimeline();
const events = [...timeline.events].sort((a, b) => b.date.localeCompare(a.date));
---
<Base title="Timeline" description="A timeline of growth." activePath="/timeline/">

  <section class="intro">
    <div class="container">
      <span class="eyebrow intro__eyebrow">Timeline</span>
      <h1 class="intro__title">Years, not résumés.</h1>
      <p class="intro__lead">How I'm becoming a better engineer.</p>
    </div>
  </section>

  <section>
    <div class="container container--narrow">
      <ul class="timeline" style="list-style:none;padding:0;margin:0">
        {events.map(event => <TimelineItem event={event} />)}
      </ul>
    </div>
  </section>

</Base>
```

- [ ] **Step 3: 创建 gallery.astro**

```astro
---
import Base from '../layouts/Base.astro';
import GalleryGrid from '../components/GalleryGrid.astro';
import { getGallery } from '../lib/content';

const gallery = await getGallery();
---
<Base title="Gallery" description="Photography, travel, and life beyond code." activePath="/gallery/">

  <section class="intro">
    <div class="container">
      <span class="eyebrow intro__eyebrow">Gallery</span>
      <h1 class="intro__title">Things that keep me human.</h1>
      <p class="intro__lead">Photography, travel, and side quests.</p>
    </div>
  </section>

  <section>
    <div class="container">
      <GalleryGrid photos={gallery.photos} />
    </div>
  </section>

</Base>
```

- [ ] **Step 4: 创建 contact.astro**

```astro
---
import Base from '../layouts/Base.astro';
import { getSiteConfig, getProfile } from '../lib/content';

const site = await getSiteConfig();
const profile = await getProfile();
---
<Base title="Contact" description="Get in touch." activePath="/contact/">

  <section class="intro">
    <div class="container">
      <span class="eyebrow intro__eyebrow">Contact</span>
      <h1 class="intro__title">Get in touch.</h1>
      <p class="intro__lead">{profile.contact_note}</p>
    </div>
  </section>

  <section>
    <div class="container container--narrow">
      <ul style="list-style:none;padding:0;margin:0" class="stack">
        {profile.social.map(s => (
          <li class="row row--between" style="padding:16px 0;border-bottom:1px solid var(--border)">
            <span class="ink">{s.label}</span>
            <a class="link" href={s.href} target={s.icon === 'github' ? '_blank' : undefined} rel={s.icon === 'github' ? 'noopener' : undefined}>
              {s.href.replace('mailto:', '').replace('https://', '')} →
            </a>
          </li>
        ))}
      </ul>
    </div>
  </section>

</Base>
```

- [ ] **Step 5: Commit**

```bash
git add src/pages/skills.astro src/pages/timeline.astro src/pages/gallery.astro src/pages/contact.astro
git commit -m "feat: add skills/timeline/gallery/contact pages"
```

---

## Task 21: 创建重定向页和 404

**Files:**
- Create: `src/pages/tech-stack.astro`
- Create: `src/pages/404.astro`

- [ ] **Step 1: 创建 tech-stack.astro(301 重定向)**

```astro
---
import { Astro } from 'astro';
return Astro.redirect('/skills/', 301);
---
```

- [ ] **Step 2: 创建 404.astro**

```astro
---
import Base from '../layouts/Base.astro';
---
<Base title="404" description="Page not found.">
  <section style="padding:120px 0;text-align:center">
    <div class="container">
      <h1 style="font-size:64px;margin:0">404</h1>
      <p class="muted" style="margin:16px 0 32px">Not found.</p>
      <a class="btn btn--primary" href="/">← Home</a>
    </div>
  </section>
</Base>
```

- [ ] **Step 3: Commit**

```bash
git add src/pages/tech-stack.astro src/pages/404.astro
git commit -m "feat: add tech-stack redirect and 404 page"
```

---

## Task 22: 添加 Timeline 和 Gallery 样式

**Files:**
- Modify: `src/styles/main.css`(追加样式)

- [ ] **Step 1: 追加 timeline/gallery/currently 样式到 main.css 末尾**

```css
/* -------------------------------------------------------------------------
   Timeline
   ------------------------------------------------------------------------- */
.timeline { position: relative; padding-left: var(--s-6); }
.timeline::before {
  content: ''; position: absolute; left: 8px; top: 0; bottom: 0;
  width: 1px; background: var(--border);
}
.timeline__item { position: relative; padding: var(--s-4) 0; }
.timeline__dot {
  position: absolute; left: calc(-1 * var(--s-6) + 4px); top: 24px;
  width: 9px; height: 9px; border-radius: 50%;
  background: var(--accent); border: 2px solid var(--paper);
}
.timeline__date { font-size: 12px; color: var(--muted); }
.timeline__title { font-size: 1.1em; font-weight: 600; margin: 4px 0 8px; }
.timeline__desc { color: var(--muted); margin: 8px 0; }
.timeline__tags { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }

/* -------------------------------------------------------------------------
   Gallery
   ------------------------------------------------------------------------- */
.gallery__item { margin: 0; }
.gallery__img-wrap {
  aspect-ratio: 4/3; overflow: hidden; border-radius: var(--r-md);
  background: var(--surface-sunken); margin-bottom: var(--s-3);
}
.gallery__img-wrap img { width: 100%; height: 100%; object-fit: cover; transition: transform var(--t-base); }
.gallery__item:hover .gallery__img-wrap img { transform: scale(1.03); }
.gallery__title { font-size: 1em; font-weight: 600; margin: 0 0 4px; }
.gallery__desc { font-size: 0.9em; color: var(--muted); margin: 4px 0 0; }

/* -------------------------------------------------------------------------
   Currently
   ------------------------------------------------------------------------- */
.currently { padding: var(--s-5); border: 1px solid var(--border); border-radius: var(--r-lg); }
.currently__head { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--s-4); }
.currently__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: var(--s-4); }
.currently__item { display: flex; flex-direction: column; gap: 4px; }
.currently__cat { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: var(--muted); text-transform: uppercase; }
.currently__content { font-size: 0.95em; }

/* -------------------------------------------------------------------------
   TOC
   ------------------------------------------------------------------------- */
.toc { padding: var(--s-4); border: 1px solid var(--border); border-radius: var(--r-md); }
.toc ul { list-style: none; padding: 0; margin: var(--s-2) 0 0; }
.toc__item { padding: 4px 0; font-size: 0.9em; }
.toc__item--3 { padding-left: var(--s-4); font-size: 0.85em; }
.toc__item a { color: var(--muted); text-decoration: none; }
.toc__item a:hover { color: var(--accent); }

/* -------------------------------------------------------------------------
   Skill group
   ------------------------------------------------------------------------- */
.skill-group__title { font-size: 1.1em; font-weight: 600; margin: 0 0 var(--s-3); }
```

- [ ] **Step 2: Commit**

```bash
git add src/styles/main.css
git commit -m "feat: add timeline/gallery/currently/toc styles"
```

---

## Task 23: 本地构建验证

**Files:** 无(验证步骤)

- [ ] **Step 1: 运行 astro check**

Run: `npx astro check`
Expected: 0 errors, 0 warnings

- [ ] **Step 2: 运行 astro build**

Run: `npm run build`
Expected: 构建成功,`dist/` 目录生成所有页面

- [ ] **Step 3: 验证 dist 结构**

Run: `Get-ChildItem dist -Recurse -Directory | Select-Object FullName`
Expected: 包含 `/`, `/about/`, `/projects/`, `/projects/smart-cart/`, `/learning/`, `/blog/`, `/blog/hello-world/`, `/skills/`, `/timeline/`, `/gallery/`, `/contact/` 等目录

- [ ] **Step 4: 本地预览测试**

Run: `npm run preview`(后台运行)
访问 `http://localhost:4321/` 验证:
- 首页 Hero/Currently/Featured/Latest 正常渲染
- 导航跳转正常
- 暗色模式切换正常
- /tech-stack/ 自动跳转到 /skills/
- /projects/smart-cart/ 详情页 Markdown 正常渲染
- /blog/hello-world/ 详情页 TOC 正常(如有标题)

- [ ] **Step 5: 停止预览服务器**

- [ ] **Step 6: Commit(如有修复)**

```bash
git add -A
git commit -m "fix: address build issues"
```

---

## Task 24: 部署到服务器

**Files:** 无(部署步骤)

- [ ] **Step 1: 上传 dist/ 到服务器**

```bash
# 先创建目标目录
ssh a@192.168.1.43 "mkdir -p /home/a/web/dist"
# 上传所有文件
scp -r dist/* a@192.168.1.43:/home/a/web/dist/
```

- [ ] **Step 2: 备份现有 Nginx 配置**

```bash
ssh a@192.168.1.43 "cp /opt/1panel/apps/openresty/openresty/conf/conf.d/snhgn.me.conf /opt/1panel/apps/openresty/openresty/conf/conf.d/snhgn.me.conf.bak"
```

- [ ] **Step 3: 写入新 Nginx 配置**

创建本地临时文件 `snhgn.me.conf`:

```nginx
server {
    listen 80;
    server_name snhgn.me;
    root /home/a/web/dist;
    index index.html;

    access_log /www/sites/snhgn.me/log/access.log main;
    error_log  /www/sites/snhgn.me/log/error.log;

    location ^~ /.well-known/acme-challenge {
        allow all;
        root /usr/share/nginx/html;
    }

    location ~* \.(css|js|jpg|jpeg|png|gif|svg|woff2?|ttf)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        try_files $uri $uri/ $uri.html /404.html;
    }
}
```

上传并替换:

```bash
scp snhgn.me.conf a@192.168.1.43:/opt/1panel/apps/openresty/openresty/conf/conf.d/snhgn.me.conf
```

- [ ] **Step 4: 测试 Nginx 配置并重载**

```bash
ssh a@192.168.1.43 "openresty -t && openresty -s reload"
```
Expected: `syntax is ok` + `test is successful`

- [ ] **Step 5: 停止 PHP server**

```bash
ssh a@192.168.1.43 "pkill -f 'php -S 0.0.0.0:8000'"
```

- [ ] **Step 6: 删除旧服务器文件**

```bash
ssh a@192.168.1.43 "cd /home/a/web && rm -rf index.html about projects learning tech-stack timeline gallery contact skills assets router.php blog wp-theme 2>/dev/null; ls -la"
```
Expected: 只剩 `dist/` 目录(和 log 目录如有)

- [ ] **Step 7: 删除本地临时文件**

删除本地 `snhgn.me.conf` 临时文件。

---

## Task 25: 线上路由验证

**Files:**
- Create: `verify-deploy.sh`(临时验证脚本)

- [ ] **Step 1: 创建验证脚本**

```bash
#!/bin/bash
for p in / /about/ /projects/ /projects/smart-cart/ /learning/ /learning/systemd-dependency/ /skills/ /timeline/ /blog/ /blog/hello-world/ /gallery/ /contact/ /tech-stack/ /nonexistent/; do
  c=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: snhgn.me" -L "http://127.0.0.1$p")
  echo "$c  $p"
done
```

- [ ] **Step 2: 上传并执行**

```bash
scp verify-deploy.sh a@192.168.1.43:/tmp/verify-deploy.sh
ssh a@192.168.1.43 "bash /tmp/verify-deploy.sh"
```
Expected: 除 `/nonexistent/` 返回 404 外,全部 200(/tech-stack/ 因 -L 跟随 301 也为 200)

- [ ] **Step 3: 清理服务器临时文件**

```bash
ssh a@192.168.1.43 "rm /tmp/verify-deploy.sh"
```

- [ ] **Step 4: 删除本地验证脚本和旧文件**

删除:
- `verify-deploy.sh`
- `verify-routes.sh`
- `deploy-redesign.sh`
- `index.html` 及所有旧 HTML 目录(about/projects/learning/tech-stack/timeline/gallery/contact/skills/assets)
- `wp-theme/`
- `wp.tar.gz`
- `sqlite-db.zip`

- [ ] **Step 5: 最终 Commit**

```bash
git add -A
git commit -m "chore: remove legacy static files and deployment scripts"
```

---

## Task 26: 视觉一致性验证

**Files:** 无(验证步骤)

- [ ] **Step 1: 浏览器访问关键页面**

在浏览器中访问 `http://snhgn.me/`(或 `http://192.168.1.43/`),验证:

1. **首页**
   - Hero 区域显示 "Stay curious, keep building."
   - Currently 卡片显示 7 项最近状态
   - Featured 区域显示 2 个精选项目
   - Latest 区域显示 5 条最新动态
   - 导航栏 7 项(Projects/Learning/Skills/Timeline/Blog/Gallery/About)

2. **About 页面**
   - Philosophy 段落正常显示
   - Interests 列表 7 项
   - Future direction 段落
   - Get in touch 联系方式

3. **Projects 列表**
   - 显示 2 个项目卡片(smart-cart, woodscan)
   - 点击进入详情页,Markdown 正确渲染
   - Lessons learned 列表显示
   - 代码块语法高亮(github-dark 主题)

4. **Blog 详情页**
   - hello-world 文章正常显示
   - 标签和日期显示
   - 如有标题,TOC 侧边栏显示

5. **Skills 页面**
   - 6 个分类分组
   - 每个技能显示进度条

6. **暗色模式**
   - 点击右上角月亮/太阳图标切换
   - 配色与原站一致(背景 #0A0A0A,文字 #F3F4F6)

- [ ] **Step 2: 移动端验证**

DevTools 切换到移动端视图(375px 宽度),验证:
- 导航栏不溢出(可能需要 hamburger 菜单,但原站也没有,保持一致)
- 网格布局变为单列
- 字体大小可读

- [ ] **Step 3: 修复发现的问题(如有)**

如发现样式不一致,调整 `src/styles/main.css` 或对应组件,重新构建部署:

```bash
npm run build
scp -r dist/* a@192.168.1.43:/home/a/web/dist/
```

---

## Self-Review Checklist

### Spec coverage
- [x] Home 页面 — Task 15
- [x] About — Task 16
- [x] Projects 列表+详情 — Task 17
- [x] Learning 列表+详情 — Task 18
- [x] Blog 列表+详情(含 TOC) — Task 19
- [x] Timeline — Task 20
- [x] Skills(/skills/ 路由) — Task 20
- [x] Gallery — Task 20
- [x] Contact — Task 20
- [x] Currently 模块(首页) — Task 15
- [x] /tech-stack/ → /skills/ 重定向 — Task 21
- [x] site.yml 全局配置 — Task 5
- [x] Content Collections + Zod — Task 3, 4
- [x] Markdown 增强(Shiki/KaTeX/Mermaid/Callout) — Task 1(config), 11(callout)
- [x] WordPress 迁移 — Task 10
- [x] 纯静态部署 — Task 24
- [x] 旧文件清理 — Task 24, 25
- [x] 路由验证 — Task 25
- [x] 视觉一致性 — Task 26

### Placeholder scan
无 "TBD"/"TODO"/"fill in" 等占位符。所有步骤都有具体代码。

### Type consistency
- `getSiteConfig()` / `getProfile()` / `getCurrently()` / `getTimeline()` / `getSkills()` / `getGallery()` 在 Task 4 定义,后续 Task 均按此调用 ✓
- Project schema 字段(slug/title/date/status/year/tech/featured/order/description/lessons)在 Task 3 定义,Task 8/14/17 使用一致 ✓
- Learning schema 字段(slug/title/date/tags/summary/problems/solutions/next_steps)在 Task 3 定义,Task 9/18 使用一致 ✓
- Blog schema 字段(slug/title/date/tags/category/description/draft/reading_time)在 Task 3 定义,Task 10/19 使用一致 ✓

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-12-content-driven-refactor.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?