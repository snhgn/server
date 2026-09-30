# website-deploy — 网站部署与服务器信息包

snhgn.me 网站的部署脚本、服务器配置与完整信息。

## 目录结构

```
website-deploy/
├── deploy-website.ps1     # 一键部署编排（Windows）：构建校验 → 上传 → 调用远端脚本
├── deploy-web.sh          # 服务器侧部署脚本：断言 → 备份 → 原地 rsync → 验证 → 失败自动回滚
├── server-info.md         # 服务器完整信息（系统/硬件/网络/部署记录/系统配置）
└── deploy/
    ├── Caddyfile          # Caddy 配置（静态文件 + SPA fallback）
    ├── docker-compose.yml # Caddy 容器编排（8080 端口）
    └── cloudflared/
        └── docker-compose.yml  # Cloudflare Tunnel 容器（Token 方式）
```

> **部署载荷的唯一事实来源是 `web/dist`**（vite 构建产物，已含 `web/public` 静态资源）。
> 历史上这里放过两份 `deploy/web/` 镜像并提交进 git 共 558 个文件，内容早已与线上脱节 ——
> 用它部署会把线上悄悄退回旧版。现已删除并写入 `.gitignore`。

## 一键部署（Windows）

前置：已安装 npm、PuTTY（含 pscp/plink）。

```powershell
# 部署当前项目 web/dist 静态资源至 192.168.50.2 服务器
powershell -ExecutionPolicy Bypass -File deploy-website.ps1

# 自定义参数
powershell -File deploy-website.ps1 -Server 192.168.50.2
```

脚本流程：
1. `npm run build` 构建前端（`-SkipBuild` 可跳过）
2. **本地载荷自检**：文件数、必需文件非空、APK 存在 —— 不合格就不浪费一次远程部署
3. pscp 上传到唯一暂存目录 `/tmp/webdeploy-<时间戳>/`（外加 `deploy-web.sh`）
4. 服务器执行 `deploy-web.sh`：前置断言 → 自动备份 → 原地 rsync → bind mount 体检 → 重载 Caddy → 验证
5. 验证不通过**自动回滚**到部署前状态，并以非零退出码结束

远端脚本的硬性保证：

| 保障 | 说明 |
|---|---|
| 前置断言 | 载荷不完整时**在碰线上之前**退出 |
| 只读暂存 | 脚本全程不删暂存目录（历史事故：先删暂存再 cp，线上被清空 404） |
| 原地 rsync | `--delete-after --delay-updates`，目录 inode 不变 → Caddy bind mount 不会失效 |
| 自动备份 | 每次部署前存 `/opt/snhgn/backups/website-<时间戳>/` |
| 失败回滚 | 验证不通过即还原，并区分"还原失败"与"还原成功但仍不健康" |
| bind mount 体检 | inode 漂移（历史 `mv` 事故遗留）时自动 `--force-recreate` Caddy |

> 提示：脚本含服务器登录凭据默认值，仅限个人本机使用。若服务器密码已修改，
> 请用 `-Password` 参数传入或在脚本顶部修改。

## 手动部署（不依赖脚本）

```bash
# 本地构建
cd web && npm run build

# 上传到唯一暂存目录
ssh snhgn@192.168.50.2 "rm -rf /tmp/web-manual && mkdir -p /tmp/web-manual"
pscp -r web\dist\* snhgn@192.168.50.2:/tmp/web-manual/

# 服务器替换：优先直接复用带断言/备份/回滚的远端脚本
pscp deploy-web.sh snhgn@192.168.50.2:/tmp/deploy-web.sh
ssh snhgn@192.168.50.2 "bash /tmp/deploy-web.sh /tmp/web-manual /opt/website /opt/snhgn/backups 1"
```

> ⚠️ **不要**用 `sudo rm -rf /opt/website/web/* && sudo cp -r ...`。
> 历史上正是这条命令在 `cp` 失败时留下一个被清空的线上站点（全站 404）：
> `rm` 先执行且不可回滚，`cp` 后执行且没有前置校验。

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
