#!/bin/bash
# ============================================================
#  snhgn.me 网站部署 —— 服务器侧
#
#  由 deploy-website.ps1 上传后调用。**本脚本只读暂存、只写线上，
#  绝不删除暂存目录本身**（历史事故：脚本开头 rm -rf 暂存目录，
#  而调用顺序是"先上传再跑脚本"，结果载荷被自己删掉，
#  紧跟其后的 cp 因源不存在而失败，但同一条命令里的
#  `rm -rf /opt/website/web/*` 已经先执行，线上被清空、站点 404）。
#
#  核心设计
#  --------
#  1) 前置断言：暂存载荷不完整就退出，绝不碰线上
#  2) 先备份：任何改动前留一份可回滚副本
#  3) 原地 rsync：--delay-updates + --delete-after 让更新近似原子，
#     且**目录 inode 保持不变** —— Caddy 的 bind mount 因此不会失效
#  4) bind mount 体检：万一历史部署用 mv 换过目录（inode 漂移），
#     自动检测并 --force-recreate 容器，而不是让用户对着 404 猜
#  5) 自动回滚：验证不通过就用刚才的备份还原，不留半成品在线上
# ============================================================
set -uo pipefail

STAGE="${1:?用法: deploy-web.sh <暂存目录> <站点根目录> <备份根目录> <sudo密码>}"
ROOT="${2:?}"
BACKUP_ROOT="${3:?}"
SUDO_PASS="${4:?}"

LIVE="$ROOT/web"
MIN_FILES=50
ENDPOINTS="/ /schedule /landing.html /sw.js /favicon.svg"

log()  { echo "[$(date +%H:%M:%S)] $*"; }
die()  { echo "[$(date +%H:%M:%S)] FATAL: $*" >&2; exit 1; }
sudo_do() { echo "$SUDO_PASS" | sudo -S "$@"; }

# ------------------------------------------------------------
# 1. 前置断言
# ------------------------------------------------------------
log "1/6 前置断言"
[ -d "$STAGE" ] || die "暂存目录不存在: $STAGE（上传失败？不应删除本目录）"
N=$(find "$STAGE" -type f | wc -l)
log "  载荷文件数: $N"
[ "$N" -ge "$MIN_FILES" ] || die "载荷仅 $N 个文件（阈值 $MIN_FILES），疑似上传不完整"
for f in index.html sw.js schedule-app.apk; do
  [ -s "$STAGE/$f" ] || die "载荷缺少或为空: $f"
done
[ -d "$STAGE/assets" ] || die "载荷缺少 assets/ 目录"
log "  断言通过"

# ------------------------------------------------------------
# 2. 备份
# ------------------------------------------------------------
TS=$(date +%Y%m%d-%H%M%S)
BK="$BACKUP_ROOT/website-$TS"
log "2/6 备份现状 -> $BK"
sudo_do mkdir -p "$BK" || die "创建备份目录失败"
sudo_do cp -r "$LIVE" "$BK/web" || die "备份 web 目录失败"
BK_N=$(find "$BK/web" -type f | wc -l)
log "  已备份 $BK_N 个文件"
[ "$BK_N" -gt 0 ] || die "备份为空，拒绝继续"

rollback() {
  log "!!! 验证失败，开始自动回滚 -> $BK"
  if ! echo "$SUDO_PASS" | sudo -S bash -c "
    set -e
    rsync -a --delete --delete-after --delay-updates '$BK/web/' '$LIVE/'
  "; then
    log "回滚动作本身失败（rsync 报错），需人工介入"
    return 2
  fi
  echo "$SUDO_PASS" | sudo -S docker exec caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1
  # 区分「还原失败」与「还原成功但仍不健康」——两者的处置完全不同
  if verify_quiet; then
    log "回滚成功，站点已恢复到部署前状态"
    return 0
  fi
  log "回滚已执行（文件已还原），但复检仍不通过：需人工检查，可能是先前就存在的问题"
  return 1
}

verify_quiet() {
  local bad=0
  # 注意 / 被 Caddyfile 有意 rewrite 到 landing.html（@site_root），
  # 所以 200 + 非空即正常；SPA 路由才是 /schedule
  for ep in $ENDPOINTS; do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8080$ep")
    size=$(curl -s -o /dev/null -w '%{size_download}' "http://127.0.0.1:8080$ep")
    if [ "$code" != "200" ] || [ "$size" -lt 100 ]; then
      log "  验证失败 $ep -> HTTP $code ${size}B"; bad=1
    fi
  done
  # APK 必须真的能下载且非空
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/schedule-app.apk)
  size=$(curl -s -o /dev/null -w '%{size_download}' http://127.0.0.1:8080/schedule-app.apk)
  if [ "$code" != "200" ] || [ "$size" -lt 1000000 ]; then
    log "  验证失败 /schedule-app.apk -> HTTP $code ${size}B"; bad=1
  fi
  # 真正有意义的断言：SPA 的 index.html 所引用的主 chunk 必须能取到。
  # 只查 200 会漏掉「HTML 已换新、但 hashed asset 没同步」这种半部署状态。
  # 注意必须取 /schedule（Caddyfile 把 / rewrite 成 landing.html），
  # 对 / 取会拿到不含 chunk 引用的落地页，断言必然误报。
  main=$(curl -s http://127.0.0.1:8080/schedule | grep -o 'assets/index-[A-Za-z0-9_-]*\.js' | head -1)
  if [ -z "$main" ]; then
    log "  验证失败：/schedule 的 HTML 未引用任何主 chunk"; bad=1
  else
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8080/$main")
    if [ "$code" != "200" ]; then
      log "  验证失败：HTML 引用 $main 但取不到 -> HTTP $code"; bad=1
    else
      log "  线上主 chunk 可取: $main"
    fi
  fi
  return $bad
}

# ------------------------------------------------------------
# 3. 原地应用（目录 inode 不变，bind mount 保持有效）
# ------------------------------------------------------------
log "3/6 原地 rsync（保留目录 inode）"
sudo_do rsync -a --delete --delete-after --delay-updates "$STAGE/" "$LIVE/" \
  || die "rsync 失败（线上未被改动，因为 rsync 失败不会清空目标）"
log "  线上现有 $(find "$LIVE" -type f | wc -l) 个文件"

# ------------------------------------------------------------
# 4. bind mount 体检
#    历史事故：曾用 mv 替换 web 目录，inode 变了，容器仍绑在旧目录，
#    结果文件齐全但全站 404。up -d 认为配置未变而不重建，必须显式重建。
# ------------------------------------------------------------
log "4/6 bind mount 体检"
HOST_INO=$(stat -c '%i' "$LIVE")
CTR_INO=$(echo "$SUDO_PASS" | sudo -S docker exec caddy stat -c '%i' /srv/web 2>/dev/null | tr -d '\r')
if [ "$HOST_INO" != "$CTR_INO" ]; then
  log "  inode 漂移！宿主 $HOST_INO vs 容器 $CTR_INO —— 重建 Caddy"
  sudo_do bash -c "cd '$ROOT' && docker compose up -d --force-recreate" || die "重建 Caddy 失败"
  sleep 4
  CTR_INO=$(echo "$SUDO_PASS" | sudo -S docker exec caddy stat -c '%i' /srv/web 2>/dev/null | tr -d '\r')
  [ "$HOST_INO" = "$CTR_INO" ] && log "  inode 已对齐 ($HOST_INO)" \
    || die "重建后 inode 仍不一致（$HOST_INO vs $CTR_INO）"
else
  log "  inode 一致 ($HOST_INO)，bind mount 正常"
fi

# ------------------------------------------------------------
# 5. 重载 Caddy
# ------------------------------------------------------------
log "5/6 重载 Caddy"
sudo_do docker exec caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1 \
  || log "  (reload 返回非零，通常无害；配置未变时会这样)"

# ------------------------------------------------------------
# 6. 验证
# ------------------------------------------------------------
log "6/6 验证"
if verify_quiet; then
  log "全部通过"
  echo ""
  echo "部署成功。回滚点: $BK"
  exit 0
fi

log "验证未通过"
rollback
rc=$?
case $rc in
  0) echo "已回滚到部署前状态，线上未受影响。备份: $BK"; exit 1 ;;
  1) die "回滚后复检仍不通过，请人工检查。备份: $BK" ;;
  *) die "回滚动作失败，请人工介入。备份: $BK" ;;
esac
