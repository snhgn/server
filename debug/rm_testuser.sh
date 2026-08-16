#!/bin/bash
# 清理公网测试用户与其全部 session
docker exec gateway python -c "
import sqlite3
conn = sqlite3.connect('/data/gateway.db')
conn.execute('DELETE FROM users WHERE id=999')
conn.execute('DELETE FROM sessions WHERE user_id=999')
conn.commit(); conn.close(); print('cleaned')
"
