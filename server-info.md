# snhgn.me 服务器开荒记录

记录时间：2026-08-08

## 系统信息

| 项目 | 值 |
|------|-----|
| 发行版 | Ubuntu 22.04.5 LTS |
| 代号 | jammy |
| 架构 | x86_64 |
| 主机名 | snhgn |

## 硬件

| 项目 | 值 |
|------|-----|
| CPU | Intel(R) Core(TM) i5-7200U @ 2.50GHz，4 核 |
| 内存 | 3.7 GiB（Swap 3.7 GiB） |
| 磁盘 | 465.8G SSD（sda），LVM 根分区 454G，已用 7G |

## 网络

| 网卡 | IP | 说明 |
|------|-----|------|
| enp2s0f2（有线） | 192.168.50.2/24 | SSH 管理连接 |
| wlp3s0（无线） | 10.66.36.5/24 | 默认路由，网关 10.66.36.218 |

- 默认路由：`via 10.66.36.218 dev wlp3s0`
- IPv6：240e:404:1e80:185f:...（DHCP）
- 环境为家庭 NAT，无公网 IP → 采用 Cloudflare Tunnel 方案

## SSH 状态

- 服务：ssh.service，active (running)，已启用开机自启
- 监听：0.0.0.0:22 / [::]:22
- 登录用户：snhgn

## 负载

- uptime 1h30m，load average 0.08，空闲良好

---

# 部署记录（2026-08-08 完成）

## 架构总览

```
访客 → https://snhgn.me (Cloudflare CDN/TLS)
        → Cloudflare Tunnel（出站连接，无需公网IP/端口转发）
        → cloudflared 容器 (host网络)
        → Caddy 容器 http://127.0.0.1:8080
        → 静态文件 /opt/website/web/
```

## 已安装软件

| 软件 | 版本 | 说明 |
|------|------|------|
| Docker Engine | 29.7.2 | 容器运行时，开机自启 |
| Docker Compose | v5.4.0 | 容器编排 |
| Caddy | 2.9-alpine | 静态网站服务（容器） |
| cloudflared | 2026.7.3 | Cloudflare Tunnel（容器） |
| curl/wget/git/vim/htop/unzip | - | 基础工具 |

## 目录结构

```
/opt/website/              # 网站项目
├── docker-compose.yml     # Caddy 容器编排
├── Caddyfile              # Caddy 配置（http://snhgn.me → /srv/web）
└── web/                   # 网站文件（静态，可替换）
    └── index.html         # 测试主页

/opt/cloudflared/          # 隧道项目
└── docker-compose.yml     # cloudflared 容器（Token 方式）
```

## 常用命令

### 网站（/opt/website）
```bash
cd /opt/website
docker compose up -d       # 启动
docker compose down        # 停止
docker compose restart     # 重启
docker compose logs -f     # 查看日志
docker compose up -d --build   # 更新网站文件后重载（通常无需）
```

### 隧道（/opt/cloudflared）
```bash
cd /opt/cloudflared
docker compose up -d       # 启动
docker compose down        # 停止
docker compose restart     # 重启
docker compose logs -f     # 查看日志
```

## 更新/替换网站文件

1. 编辑或上传新文件到 `/opt/website/web/`
2. Caddy 自动识别（静态文件无需重启容器）

## 验证结果

- `https://snhgn.me` → HTTP 200 ✓（经 Cloudflare 边缘 + 隧道 + Caddy）
- 隧道 4 条连接（lax/sjc 节点），自动降级 http2（家庭网络 UDP 受限）

---

# 系统配置（2026-08-08）

## 合盖不操作

- 配置文件：`/etc/systemd/logind.conf.d/10-lid-ignore.conf`
- 内容：`HandleLidSwitch=ignore` / `HandleLidSwitchExternalPower=ignore` / `HandleLidSwitchDocked=ignore`
- **补充（2026-08-08 排查）**：合盖后网络中断的根因是 WiFi 省电（`wifi.powersave = 3`）导致网卡休眠断网，而非系统挂起。
  已处理：
  - `iw` 安装 + `iw dev wlp3s0 set power_save off`（当前 off）
  - systemd 服务 `/etc/systemd/system/wifi-powersave.service` 开机自动关闭省电（enabled）
  - NetworkManager 配置 `/etc/NetworkManager/conf.d/wifi-powersave-off.conf`（`wifi.powersave = 2`）
- 无线网卡：Qualcomm Atheros QCA9565（ath9k 驱动）

## 每晚 12 点自动重启

- Timer：`/etc/systemd/system/daily-reboot.timer`（`OnCalendar=*-*-* 00:00:00`）
- Service：`/etc/systemd/system/daily-reboot.service`（执行 `systemctl reboot`）
- 状态：enabled，首次触发 2026-08-09 00:00 CST

## 开机自启清单

| 项目 | 方式 | 状态 |
|------|------|------|
| Docker 服务 | `systemctl enable docker` | enabled |
| Caddy 容器 | `restart: unless-stopped` | ✓ |
| cloudflared 容器 | `restart: unless-stopped` | ✓ |
| ai-service 容器 | `restart: unless-stopped` | ✓ |
| WiFi 网络 | netplan `/etc/netplan/00-installer-config.yaml` | 持久化自动连接 |

## 网站部署（Vue3 前端）

- 源码：`d:\project\snhgn.me`（Vue3 + Vite + TS + Tailwind）
- 服务器文件：`/opt/website/web/`（构建产物 dist）
- Caddyfile 已启用 SPA fallback：`try_files {path} /index.html`
- 构建：`npm run build` → 上传 dist 到 `/opt/website/web/`

## AI 服务层（ai-service）

- 位置：`/opt/ai-service/`（Docker Compose，FastAPI）
- 接口：`POST http://192.168.50.2:8000/api/chat`，请求 `{"message":"..."}`
- 逻辑：默认 GLM（zai-sdk，glm-4.7-flash），失败自动切换 Gemini（官方 HTTP，gemini-flash-latest）
- 密钥：`/opt/ai-service/.env`（权限 600，`GLM_API_KEY` / `GEMINI_API_KEY`）
- 详见本地 `packages/ai-service/README.md`


