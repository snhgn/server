# snhgn 服务器统一平台架构

记录时间：2026-08-08

## 目录结构

```
/opt/snhgn/                  # 统一平台根目录（snhgn:snhgn）
├── services/                # 服务编排文件（各服务 docker-compose.yml）
├── data/                    # 服务数据卷（数据库、缓存、上传等持久化数据）
├── logs/                    # 日志目录（容器日志集中存放）
├── backups/                 # 备份目录（配置备份、数据备份）
└── config/                  # 共享配置文件（Caddyfile 等跨服务配置）
```

## Docker 网络

```
snhgn-network (bridge, local)
用途：所有个人服务加入此网络，容器间通过服务名互相访问
```

## 当前服务清单

| 容器 | 镜像 | 端口 | 数据挂载 | 网络 | 说明 |
|------|------|------|----------|------|------|
| caddy | caddy:2.9-alpine | 8080→80 | /opt/website/ | website_default | 静态网站反向代理 |
| cloudflared | cloudflare/cloudflared:latest | host | - | host | Cloudflare 隧道 |
| ai-service | ai-service-ai-service | 8000 | - | ai-service_default | AI 统一服务层 |

## 现有目录（未迁移，保留）

```
/opt/website/       # Caddy 网站（Caddyfile + web/）
/opt/cloudflared/   # cloudflared 隧道
/opt/ai-service/    # AI 服务
/opt/server-info.md # 服务器信息
```

## 迁移规划（分阶段，逐步执行）

### 阶段 1：网络统一（低风险）
将 caddy、ai-service 加入 snhgn-network 共享网络（container 仍保留原网络）。
- 目的：打通容器间服务名互访能力，为后续微服务化做准备
- 影响：无（不中断服务）

### 阶段 2：配置集中（低风险）
将各服务 compose 文件复制到 `/opt/snhgn/services/<name>/`。
- 目的：统一管理编排文件
- 方式：复制不移动，确认后再切换

### 阶段 3：数据挂载规范化（中风险，需停机窗口）
- 网站静态文件：`/opt/website/web/` → `/opt/snhgn/data/website/`
- AI 服务数据：→ `/opt/snhgn/data/ai-service/`
- 方式：rsync 同步 → 修改 compose → 验证 → 删除旧目录（确认无误后）

### 阶段 4：日志集中（低风险）
- 容器日志通过 `docker logs` 收集，或配置 `logging: driver: json-file` 到 `/opt/snhgn/logs/`

### 阶段 5：备份自动化（低风险）
- 配置备份：`/opt/snhgn/config` → backups
- 数据备份：`/opt/snhgn/data` → backups
- 方式：cron/systemd timer + tar 打包，每日执行

## 执行原则

1. 任何迁移先备份原目录
2. 迁移后先验证服务健康（curl /health、访问网站）
3. 确认无误后再清理旧目录
4. 每次只迁移一个服务，降低风险
