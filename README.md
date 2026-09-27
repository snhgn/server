# snhgn · server (Full-stack Monorepo)

snhgn.me 全栈项目仓库（前端 Vue 3 SPA + 后端服务 gateway / ai-service / scheduler + Caddy 部署）。

## 仓库结构

- `web/`：**网站前端工程源码**（Vue 3 + Vite + TypeScript + Tailwind CSS，含课表系统、AI助手、后台控制台等）
- `packages/`：核心后端服务（ai-service、gateway、scheduler、schedule-pipeline、ai-notice-monitor 等）
- `deploy/`：Caddy、Cloudflare Tunnel 等部署编排
- `packages/website-deploy/`：生产环境部署脚本（`deploy-website.ps1`）与静态分发产物
- `server-info.md`：服务器信息、部署流程与开发记录（含运维凭据，勿公开）
- `robots.txt` / `sitemap.xml`：SEO 规范文件

## 快速开发与部署

1. **前端构建**：
   ```bash
   cd web
   npm run build
   ```
2. **生产部署**：
   ```powershell
   # 将 web/dist 静态资源同步至生产服务器并重载 Caddy
   powershell -File packages/website-deploy/deploy-website.ps1
   ```

详细系统架构与路由分配见 `server-info.md`。
