#!/bin/bash
# 收尾清理:测试用户 + 临时文件 + 最终状态检查
bash /tmp/rm_testuser.sh
rm -f /tmp/auth-patch.tar.gz /tmp/web-dist.tar.gz /tmp/deploy_auth_session.sh \
      /tmp/deploy_web_fix.sh /tmp/verify_auth.sh /tmp/mk_testuser.sh \
      /tmp/rm_testuser.sh /tmp/cj_test.txt
rm -rf /tmp/auth-patch /tmp/web-dist
echo "CLEAN-DONE"
echo "--- 最终用户表(不应有 __s_test__) ---"
docker exec gateway python -c "
import sqlite3
c = sqlite3.connect('/data/gateway.db')
print('users:', c.execute('SELECT username, role FROM users').fetchall())
print('session_count:', c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0])
"
echo "--- 容器状态 ---"
docker ps --format '{{.Names}}  {{.Status}}' | grep -E 'gateway|caddy|ai-service|scheduler|cloudflared'
