# snhgn· server

snhgn.me 的后端服务与部署仓库（gateway / ai-service / scheduler / Caddy / cloudflared）。

## 仓库定位

本仓库包含：

- `packages/`：核心后端服务（ai-service、gateway、scheduler、schedule-pipeline、ai-notice-monitor 等）
- `deploy/`：Caddy、Cloudflare Tunnel 等部署编排
- `index.html`：**个人首页落地页设计稿（静态单文件）**，当前线上前端实际部署的是 Vue3 SPA
- `server-info.md`：服务器信息、部署流程与开发记录（含登录凭据，勿公开）
- `robots.txt` / `sitemap.xml`：SEO 文件

## 与前端仓库的关系

| 仓库 | 说明 |
|------|------|
| 本仓库（d:\project\server） | 后端服务源码 + 部署配置；`index.html` + `styles.css` 为线上**落地页**（部署为服务器上的 `landing.html`） |
| d:\project\snhgn.me | Vue3 + Vite + TS + Tailwind 前端，2026-08-25 已部署至 `/opt/website/web/` |

路由分配：`/` 返回静态落地页，其余路径（/login /ai /schedule 等）由 Vue SPA 承接，详见 `server-info.md` 第十五节。

详细部署流程见 `server-info.md` 第八节。
