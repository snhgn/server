# website-deploy — 网站部署与服务器信息包

snhgn.me 网站的部署脚本、服务器配置与完整信息。

## 目录结构

```
website-deploy/
├── deploy-website.ps1     # 一键部署脚本（Windows）
├── server-info.md         # 服务器完整信息（系统/硬件/网络/部署记录/系统配置）
└── deploy/
    ├── Caddyfile          # Caddy 配置（静态文件 + SPA fallback）
    ├── docker-compose.yml # Caddy 容器编排（8080 端口）
    ├── cloudflared/
    │   └── docker-compose.yml  # Cloudflare Tunnel 容器（Token 方式）
    └── web/               # 网站文件（dist 构建产物，示例 index.html）
```

## 一键部署（Windows）

前置：已安装 npm、PuTTY（含 pscp/plink）。

```powershell
# 部署当前项目 web/dist 静态资源至 192.168.50.2 服务器
powershell -ExecutionPolicy Bypass -File deploy-website.ps1

# 自定义参数
powershell -File deploy-website.ps1 -Server 192.168.50.2
```

脚本流程：
1. 检查准备 `deploy/web/` 静态资源
2. pscp 上传静态资产到服务器 `/tmp/web/`
3. 服务器替换 `/opt/website/web/*` 并热重载 Caddy
4. curl 验证服务状态（HTTP 200）

> 提示：脚本含服务器登录凭据默认值，仅限个人本机使用。若服务器密码已修改，
> 请用 `-Password` 参数传入或在脚本顶部修改。

## 手动部署（不依赖脚本）

```bash
# 本地构建
cd web && npm run build

# 上传
pscp -r web\dist\* snhgn@192.168.50.2:/tmp/web/

# 服务器替换（静态文件上传即生效，无需重启 Caddy）
ssh snhgn@192.168.50.2 "sudo rm -rf /opt/website/web/* && sudo cp -r /tmp/web/* /opt/website/web/"
```

## 相关命令速查

| 操作 | 命令（服务器上） |
|---|---|
| 启动网站 | `cd /opt/website && docker compose up -d` |
| 停止网站 | `cd /opt/website && docker compose down` |
| 查看日志 | `cd /opt/website && docker compose logs -f` |
| 启动隧道 | `cd /opt/cloudflared && docker compose up -d` |
| 隧道日志 | `cd /opt/cloudflared && docker compose logs -f` |

## 架构

```
访客 → https://snhgn.me (Cloudflare TLS)
        → Cloudflare Tunnel
        → cloudflared 容器 (host网络)
        → Caddy 容器 :8080 → /opt/website/web/
```

详见 `server-info.md`。
