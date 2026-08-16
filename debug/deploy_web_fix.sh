#!/bin/bash
# web-dist 修复:assets 为 root 所有,需 sudo 清理后重新复制
set -euo pipefail
echo "== web 目录属主 =="
ls -ld /opt/website/web /opt/website/web/assets || true
echo "== sudo 清理旧 dist =="
echo '1' | sudo -S rm -rf /opt/website/web/* 2>/dev/null
echo "== 复制新 dist =="
cp -r /tmp/web-dist/. /opt/website/web/
echo "== 新文件列表 =="
ls /opt/website/web/
echo "== index.html 引用的入口 js(应为新 hash) =="
grep -o 'assets/index-[A-Za-z0-9_-]*\.\(js\|css\)' /opt/website/web/index.html
echo "== 通过 Caddy 验证(需 Host 头) =="
curl -s -o /dev/null -w 'home: %{http_code}\n' -m 5 -H 'Host: snhgn.me' http://127.0.0.1:8080/
curl -s -m 5 -H 'Host: snhgn.me' http://127.0.0.1:8080/ | grep -o 'assets/index-[A-Za-z0-9_-]*\.\(js\|css\)' | head -2
echo "WEB-FIX-DONE"
