#!/bin/bash
# ===== Cloudflare Error 1033 只读诊断(不修改任何配置)=====
R() { echo; echo "----- $1 -----"; }

echo "########## 1. 网络 ##########"
R "ip addr"; ip addr 2>&1
R "ip route"; ip route 2>&1
R "nmcli device status"; nmcli device status 2>&1 || echo "(nmcli 不可用)"
R "nmcli connection show --active"; nmcli connection show --active 2>&1 || true
R "ping -c 4 1.1.1.1"; ping -c 4 -W 2 1.1.1.1 2>&1
R "ping -c 4 223.5.5.5"; ping -c 4 -W 2 223.5.5.5 2>&1
R "curl -I https://www.cloudflare.com (IPv4 直连)"; curl -4 -sI --max-time 10 https://www.cloudflare.com 2>&1 | head -6
R "DNS 解析 snhgn.me"; getent hosts snhgn.me || nslookup snhgn.me 2>&1 | head -8
R "cloudflared 边缘 TCP:7844 连通性"
for h in region1.v2.argotunnel.com region2.v2.argotunnel.com; do
  ip_=$(getent hosts $h | head -1 | awk '{print $1}')
  timeout 4 bash -c "cat < /dev/null > /dev/tcp/$h/7844" 2>/dev/null && echo "  $h ($ip_) TCP:7844 OK" || echo "  $h ($ip_) TCP:7844 FAIL"
done

echo
echo "########## 2. cloudflared ##########"
R "ps aux (已脱敏)"
ps aux | grep '[c]loudflared' | sed -E 's/(--token[= ])[^ ]+/\1<TOKEN_REDACTED>/g'
R "ss -ntp 过滤 cloudflared(需 sudo)"
echo '1' | sudo -S ss -ntp 2>/dev/null | grep -iE 'cloudflared|:20241' || echo "(无匹配连接或 sudo 失败)"
R "cloudflared --version(宿主机 CLI)"
cloudflared --version 2>&1 || echo "(宿主机无 cloudflared CLI)"
PID=$(pgrep -f 'tunnel run' | head -1)
R "进程详情 PID=$PID"
if [ -n "$PID" ]; then
  echo '1' | sudo -S tr '\0' ' ' < /proc/$PID/cmdline 2>/dev/null | sed -E 's/--token [^ ]+/--token <TOKEN_REDACTED>/'; echo
  echo '1' | sudo -S ls -l /proc/$PID/exe 2>/dev/null
  echo '1' | sudo -S readlink /proc/$PID/cwd 2>/dev/null
fi
R "metrics :20241 健康度(/ready + ha_connections)"
curl -s --max-time 5 -o /dev/null -w '  /ready -> HTTP:%{http_code}\n' http://127.0.0.1:20241/ready
curl -s --max-time 5 http://127.0.0.1:20241/metrics 2>/dev/null | grep -E '^cloudflared_tunnel_(ha_connections|active_streams|total_unrecoverable_errors|server_locations)' | head -20

echo
echo "########## 3. Docker ##########"
R "docker ps"
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
R "cloudflared 容器日志尾部(已脱敏)"
docker logs --tail 80 cloudflared 2>&1 | sed -E 's/(token[=: ]+)[A-Za-z0-9_\-]+/\1<TOKEN_REDACTED>/gi' | tail -50

echo
echo "########## 4. 本地网站 ##########"
R "curl -I http://127.0.0.1:8080"
curl -sI --max-time 8 http://127.0.0.1:8080 | head -6
R "curl -I http://172.25.252.42:8080"
curl -sI --max-time 8 http://172.25.252.42:8080 | head -6
R "curl Host:snhgn.me(模拟隧道真实流量)"
curl -s -o /dev/null -w '  HTTP:%{http_code} size:%{size_download}B\n' --max-time 8 -H 'Host: snhgn.me' http://127.0.0.1:8080/

echo
echo "########## 5. Tunnel CLI 只读检查 ##########"
R "cloudflared tunnel info(token 模式预期受限)"
cloudflared tunnel info 2>&1 | head -10
echo
echo "===== 诊断脚本执行完毕(未做任何修改)====="
