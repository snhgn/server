#!/usr/bin/env bash
# ============================================================
#  snhgn.me 网络/隧道看门狗
#
#  背景（2026-10-03 实测）
#  ----------------------
#  校园网 bjfu-wifi-office 出口不稳，表现为三层独立的故障：
#    1) 校园 DNS 202.204.112.87/66 完全不可达（已加公共 DNS 兜底缓解）
#    2) DNS 间歇性 i/o timeout —— cloudflared 刷新边缘 IP 失败即断链，
#       且它自己不会重连到可用状态
#    3) 出网 TLS/HTTP 数据传输失败（ICMP 通、TCP 握手通，就是传不了数据）
#
#  Docker 的 unless-stopped 救不了这些：网络不在时重启 100 次也没用。
#  本脚本的职责是在网络恢复后确保服务被拉起来，并在网络持续不通时
#  主动重连 WiFi（激進模式）。
#
#  设计要点
#  --------
#  * flock 互斥：timer 触发重叠时不并发跑
#  * 分级判定：DNS -> 出网 -> 隧道，逐级下探，避免误判
#  * 退避：WiFi 重连与容器重启都有最小间隔，避免把网络打得更烂
#  * 只在"网络正常但隧道死"时重启容器——网络不正常时重启容器毫无意义
#  * 状态跳变时记日志；配置了 WEBHOOK_URL 就推通知
# ============================================================
set -uo pipefail

# ---------- 可调参数 ----------
PING_COUNT="${PING_COUNT:-2}"          # 单次探测重试数
RUN_INTERVAL="${RUN_INTERVAL:-120}"    # 预期调用间隔(秒)，用于算失败时长
WIFI_RETRY_AFTER="${WIFI_RETRY_AFTER:-360}"   # 链路层不通多久后重连 WiFi (秒)
CONTAINER_RETRY_AFTER="${CONTAINER_RETRY_AFTER:-300}" # 隧道死了多久后重启容器 (秒)
STUCK_GRACE="${STUCK_GRACE:-180}"      # 容器刚重启后的宽限期，不动它
ALERT_AFTER="${ALERT_AFTER:-300}"      # 异常持续多久后开始推送通知 (秒)
ALERT_COOLDOWN="${ALERT_COOLDOWN:-1800}"

# 要重连哪个 WiFi 档案。必须显式指定，不能用 `nmcli device connect wlp3s0`
# 让 NetworkManager 自己挑 —— bjfu-wifi-office 与 netplan-wlp3s0-102 两个
# 档案都是 autoconnect=yes 且 priority=0（并列），device connect 会在两者间
# 随机命中，实测已导致网卡来回跳。
#
# 取 102：实测信号 79（-52 dBm，19.5/43.3 Mbps），bjfu-wifi-office 三个 AP
# 只有 34/64/35（-82~-68 dBm）。且 netplan 00-installer-config.yaml 本来
# 声明的就是 102，bjfu-wifi-office 是不在 netplan 里的野生档案。
WIFI_CON_NAME="${WIFI_CON_NAME:-netplan-wlp3s0-102}" # 两次通知之间的最小间隔 (秒)
STATE_DIR="/var/lib/netwatchdog"
LOG_FILE="/opt/snhgn/logs/net_watchdog.log"
WEBHOOK_URL="${WEBHOOK_URL:-}"         # 留空则不推送

mkdir -p "$STATE_DIR" "$(dirname "$LOG_FILE")" 2>/dev/null || true
touch "$LOG_FILE" 2>/dev/null || true

log() { echo "[$(date '+%F %T')] $*" >> "$LOG_FILE"; }

notify() {
  local title="$1" msg="$2"
  log "NOTIFY: $title | $msg"
  [ -z "$WEBHOOK_URL" ] && return 0
  curl -s -m 10 -X POST "$WEBHOOK_URL" \
    -H 'Content-Type: application/json' \
    -d "$(printf '{"title":"%s","message":"%s","host":"%s","time":"%s"}' \
          "$title" "$msg" "$(hostname)" "$(date '+%F %T')")" >/dev/null 2>&1 || true
}

# ---------- 互斥 ----------
exec 9>/run/netwatchdog.lock
if ! flock -n 9; then
  log "SKIP: 上一次运行未结束，本次跳过"
  exit 0
fi

read_state() { cat "$STATE_DIR/$1" 2>/dev/null || echo 0; }
write_state() { echo "$2" > "$STATE_DIR/$1" 2>/dev/null || true; }

# ---------- 分级健康探测 ----------
check_dns() {
  local i out
  for ((i = 0; i < PING_COUNT; i++)); do
    out=$(timeout 8 dig +time=4 +tries=1 +short A region1.v2.argotunnel.com @1.1.1.1 2>/dev/null | grep -E '^[0-9]+\.' | head -1)
    [ -n "$out" ] && return 0
    sleep 2
  done
  return 1
}

EGRESS_VIA=""
check_egress() {
  # 必须真正取到数据：只看 TCP 握手会被 SYN-ACK 骗过去（实测 /dev/tcp 连通
  # 8/8 但 TLS 握手照样超时，两者不能混为一谈）。
  #
  # 多个探测点任一成功即通过。早期版本只打 speed.cloudflare.com 一个点，
  # 结果它自身不通就误判"整条出网断了"，把仍然活着的隧道判成死的。
  #
  # 刻意不使用 https://snhgn.me 自测：cloudflared 不支持 hairpin，服务器自己
  # curl 公网域名恒为 000，那是结构性假阴性，不是故障。
  # 探针目标统一用 baidu.com（用户指定）。2026-10-03 实测依据：
  #   http://www.baidu.com/    200 / 2381B / 102ms   ← 实测最快的可用目标
  #   https://www.baidu.com/   200 / 2443B / 291ms   ← 顺带验证 TLS 可用
  #   https 连测 10 次成功 10/10
  #   页面 title 为「百度一下，你就知道」，
  #   wappass / portal / drcom 关键字均 0 命中 —— 无门户劫持误判风险。
  #
  # 已剔除的地址（此网络下恒为 000，是地址本身不通而非网络故障，放着只会
  # 每轮白等超时并掩盖真实故障）：1.1.1.1 / www.google.com / neverssl.com。
  # 剔除后单轮耗时从 ~54s 降到 4~5s。
  #
  # 两个目标都刻意取真实页面（2381B / 2443B）而非 204 空包：本故障的特征正是
  # "握手能通、数据传不了"，只回空包的探针无法证伪。
  #
  # 顺序按实测耗时排（http 102ms 远快于 https 291ms），代价是单点故障时要等
  # 满超时才轮询到下一个：实测单点黑洞耗时 14.9s，双点全黑约 24s。在 2 分钟
  # 周期 + TimeoutStartSec=180 下有余量 —— 这是为健康时判定更快付的代价。
  #
  # 排查时踩过的坑：https://1.1.1.1/ 在此网络恒为 000，我一度把它当「出网坏了」
  # 的证据写进复盘，实际同一时刻 speed.cloudflare.com 返回 200。
  # **探测目标自己不通 != 网络不通**，别把两者混为一谈。
  local url code
  for url in \
      "http://www.baidu.com/" \
      "https://www.baidu.com/" ; do
    code=$(timeout 16 curl -s -o /dev/null -w '%{http_code}' --max-time 12 "$url" 2>/dev/null)
    if [ -n "$code" ] && [ "$code" != "000" ]; then
      EGRESS_VIA="$url"
      return 0
    fi
  done
  return 1
}

check_tunnel() {
  # 判据不能是"最近 N 秒内有没有 Registered 日志"。
  # 实测反例：隧道稳定运行超过 60s 后，--since 60s 就抓不到任何注册行，
  # 但此时隧道完全健康 —— 用滑动窗口会把健康隧道误判成死的，然后每 3 分钟
  # 重启一次健康容器。
  #
  # 正确判据是比较时间戳先后：最后一次成功注册 晚于 最后一次致命事件
  # （连接全部断开并退出 / DNS 刷新失败），且容器仍在运行。
  local last_reg last_bad reg_ts bad_ts running
  running=$(docker inspect -f '{{.State.Running}}' cloudflared 2>/dev/null)
  [ "$running" = "true" ] || return 1

  last_reg=$(docker logs --tail 400 cloudflared 2>&1 \
             | grep 'Registered tunnel connection' | tail -1 \
             | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z' || true)
  [ -n "$last_reg" ] || return 1

  # 只认"隧道级"致命事件，不认单连接重试。
  # 'Unable to establish connection with Cloudflare edge' 是某一条连接的瞬时
  # 重试失败，其余连接仍可能在正常服务；若把它算作致命，会在正常抖动期间
  # 反复误判为死并重启容器。真正的隧道级失败是"全部连接断开并退出"和
  # "DNS 刷新失败"——后者正是本次故障的先兆。
  last_bad=$(docker logs --tail 400 cloudflared 2>&1 \
             | grep -E 'no more connections active and exiting|Failed to refresh DNS' \
             | tail -1 | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z' || true)

  if [ -z "$last_bad" ]; then return 0; fi

  # 统一成可字典比较的整数时间戳
  reg_ts=$(date -d "$last_reg" +%s 2>/dev/null) || return 1
  bad_ts=$(date -d "$last_bad" +%s 2>/dev/null) || return 0
  [ "$reg_ts" -gt "$bad_ts" ]
}

check_ipv4() {
  # 旧 wifi-watchdog 的职责：网卡没有 IPv4 就立刻重连，不走任何阈值。
  # 这里保留该快速路径，然后旧服务即可停用。
  ip -4 addr show wlp3s0 2>/dev/null | grep -q 'inet '
}

check_link() {
  # 链路层（L2/L3 到网关）是否真的断了。
  #
  # 这个判定是「要不要动 WiFi」的唯一依据，理由是实测教训：
  # 2026-10-03 那次故障全程 WiFi 关联正常、到网关 0% 丢包、ICMP 通，
  # 断掉的是校园网 Dr.COM 门户认证 —— 未认证时校园网直接把数据面黑洞，
  # 对外表现为 DNS 超时 + TLS 握手超时 + 502/530/1033，但链路毫无问题。
  # 对这类故障重连 WiFi 是错的药方，而且会打断 bjfu-login 的认证流程
  # （它需要网络去加载 http://10.1.1.10 并驱动无头浏览器填表）。
  # 实测 21:00 那次认证失败就发生在本脚本重连 WiFi 之后 2 分钟内。
  #
  # 网关偶发丢包是常态（实测出现过 33%），所以只要求有回复，不要求 100%。
  local gw
  ip -4 addr show wlp3s0 2>/dev/null | grep -q 'inet ' || return 1
  gw=$(ip route 2>/dev/null | awk '/^default/ && /wlp3s0/ {print $3; exit}')
  [ -n "$gw" ] || return 1
  [ "$(ping -c 3 -W 2 "$gw" 2>/dev/null | grep -c 'bytes from')" -ge 1 ]
}

container_age() {
  local started now
  started=$(docker inspect -f '{{.State.StartedAt}}' cloudflared 2>/dev/null) || { echo 99999; return; }
  # StartedAt 形如 2026-10-03T09:42:58.123456789Z
  local ep
  ep=$(date -d "$started" +%s 2>/dev/null) || { echo 99999; return; }
  echo $(( $(date +%s) - ep ))
}

# ---------- 主流程 ----------
# 快速路径 1：网卡连 IPv4 都没有 —— 无条件立即重连，不等任何阈值。
# （吸收旧 wifi-watchdog 的职责，装了本脚本后即可停用那个服务。）
if ! check_ipv4; then
  last_wifi=$(read_state last_wifi_retry)
  now0=$(date +%s)
  if [ $(( now0 - last_wifi )) -ge 120 ]; then
    log "ACT: wlp3s0 无 IPv4 地址，立即重连 WiFi"
    notify "网卡无 IP" "wlp3s0 丢失 IPv4 地址，已触发 WiFi 重连"
    nmcli device disconnect wlp3s0 >/dev/null 2>&1 || true
    sleep 5
    nmcli con up "$WIFI_CON_NAME" >/dev/null 2>&1 || nmcli device connect wlp3s0 >/dev/null 2>&1 || true
    write_state last_wifi_retry "$now0"
  fi
  write_state fail_since "$(date +%s)"
  exit 0
fi

dns_ok=0; egress_ok=0; tunnel_ok=0; link_ok=0
check_link && link_ok=1
check_dns && dns_ok=1
check_egress && egress_ok=1
# 隧道独立判定，不挂在 egress 之后 —— 否则探测点自身故障会连累隧道判定，
# 出现"隧道明明有 4 条活跃连接却被判死"的假阴性。
check_tunnel && tunnel_ok=1
# 反向修正：cloudflared 能注册连接，说明到边缘 7844 的 TLS 握手已经跑通，
# 这是"出网正常"最贴近真实需求的证据，比任何第三方探测点都可信。
[ "$tunnel_ok" = 1 ] && egress_ok=1

fail_since=$(read_state fail_since)
now=$(date +%s)

if [ "$link_ok" = 1 ] && [ "$dns_ok" = 1 ] && [ "$egress_ok" = 1 ] && [ "$tunnel_ok" = 1 ]; then
  # ---- 全绿 ----
  if [ "$fail_since" != "0" ] && [ "$fail_since" != "" ]; then
    down_for=$(( now - fail_since ))
    log "RECOVERED: 全部健康，中断时长 ${down_for}s (出网探测点 ${EGRESS_VIA:-n/a})"
    # 恢复通知不再受 ALERT_COOLDOWN 限制：坏消息已发过，好消息就该立刻到。
    notify "站点已恢复" "中断 ${down_for}s 后恢复正常"
  else
    log "OK: 链路/DNS/egress/tunnel 正常 (出网探测点 ${EGRESS_VIA:-n/a})"
  fi
  write_state fail_since 0
  write_state last_state up
  exit 0
fi

# ---- 有问题 ----
if [ "$fail_since" = "0" ] || [ -z "$fail_since" ]; then
  fail_since=$now
  write_state fail_since "$fail_since"
  log "DOWN: 首次检测到异常 dns=$dns_ok egress=$egress_ok tunnel=$tunnel_ok"
else
  write_state fail_since "$fail_since"
fi
down_for=$(( now - fail_since ))

reason=""
[ "$link_ok" = 0 ] && reason="链路层不可达"
[ "$dns_ok" = 0 ] && reason="${reason:+$reason + }DNS解析失败"
[ "$egress_ok" = 0 ] && reason="${reason:+$reason + }出网数据传输失败"
[ "$tunnel_ok" = 0 ] && reason="${reason:+$reason + }隧道无活跃连接"

last_alert=$(read_state last_alert)

# ---------- 分级处置：先分清故障属于哪一层，再决定谁来修 ----------
#
# 归属划分（刻意与 bjfu-login 错开，避免打架也避免治错层）：
#
#   链路层（无 IPv4 / 到网关不通）
#       -> 本脚本重连 WiFi。bjfu-login 对此无能为力。
#
#   认证层（链路通，但 DNS 与出网数据面不通）
#       -> Dr.COM 门户会话失效，校园网把未认证流量的数据面黑洞掉。
#          由 bjfu-login 重新认证来修，它需要网络去加载门户页并驱动浏览器填表。
#          本脚本**绝对不能**在这里重连 WiFi —— 那会打断它唯一的修复手段。
#          同样也不重启容器：实测会造成与 bjfu-login 的双重重启
#          （21:01:31 bjfu-login 重启、21:06:33 本脚本又重启一次，纯属多余）。
#          本脚本在此层只做一件事：告警。这才是真正缺失的能力。
#
#   隧道进程（DNS 通、出网通，但隧道没连接）
#       -> 本脚本重启 cloudflared。bjfu-login 只在它自己观察到
#          「离线 -> 在线」跳变时才重启容器；若它全程认为在线，
#          隧道假死就没人管 —— 这是本脚本唯一不与它重复的职责。

# 情况一：链路层真的断了 —— 只有这种情况才值得动 WiFi
if [ "$link_ok" = 0 ]; then
  last_wifi=$(read_state last_wifi_retry)
  if [ "$down_for" -lt "$WIFI_RETRY_AFTER" ]; then
    log "WAIT: 链路不通 ${down_for}s (< ${WIFI_RETRY_AFTER}s)，暂不动作 | $reason"
    exit 0
  fi
  if [ $(( now - last_wifi )) -ge "$WIFI_RETRY_AFTER" ]; then
    log "ACT: 链路层确认不通 ${down_for}s，重连 WiFi | $reason"
    nmcli device disconnect wlp3s0 >/dev/null 2>&1 || true
    sleep 5
    nmcli con up "$WIFI_CON_NAME" >/dev/null 2>&1 || nmcli device connect wlp3s0 >/dev/null 2>&1 || true
    write_state last_wifi_retry "$now"
    log "ACT: WiFi 重连指令已发出"
    if [ $(( now - last_alert )) -ge "$ALERT_COOLDOWN" ]; then
      notify "链路断开" "wlp3s0 到网关不可达 ${down_for}s，已触发 WiFi 重连"
      write_state last_alert "$now"
    fi
    exit 0
  fi
  log "WAIT: 距上次 WiFi 重连不足 ${WIFI_RETRY_AFTER}s，继续观察 | $reason"
  exit 0
fi

# 情况二：链路通，但认证层失效 —— 只告警，不干预
if [ "$dns_ok" = 0 ] || [ "$egress_ok" = 0 ]; then
  log "HOLD: 链路通但 ${reason} —— 判定为校园网认证层故障，由 bjfu-login 重新认证，本脚本不干预"
  if [ "$down_for" -ge "$ALERT_AFTER" ] && [ $(( now - last_alert )) -ge "$ALERT_COOLDOWN" ]; then
    notify "站点不可用" "链路正常但 ${reason}，持续 ${down_for}s。已交由 bjfu-login 重新认证校园网，本脚本未干预以免打断认证。"
    write_state last_alert "$now"
  fi
  exit 0
fi

# 情况三：网络正常但隧道死了 —— 本脚本独占的职责
age=$(container_age)
if [ "$age" -lt "$STUCK_GRACE" ]; then
  log "WAIT: 容器仅运行 ${age}s (< ${STUCK_GRACE}s 宽限期)，不重启"
  exit 0
fi
last_ct=$(read_state last_ct_restart)
if [ $(( now - last_ct )) -lt "$CONTAINER_RETRY_AFTER" ]; then
  log "WAIT: 距上次容器重启不足 ${CONTAINER_RETRY_AFTER}s | $reason"
  exit 0
fi

log "ACT: 链路/网络正常但隧道无连接 ${down_for}s，重启 cloudflared | $reason"
if [ $(( now - last_alert )) -ge "$ALERT_COOLDOWN" ]; then
  notify "隧道假死" "链路与出网均正常但 cloudflared 无活跃连接 ${down_for}s，已自动重启（原因：$reason）"
  write_state last_alert "$now"
fi
docker restart cloudflared >/dev/null 2>&1 && log "ACT: cloudflared 重启完成" || log "ACT: 重启失败"
write_state last_ct_restart "$now"
write_state fail_since 0