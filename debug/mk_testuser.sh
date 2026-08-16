#!/bin/bash
# 重建公网测试用户(测完由 verify_public_clean.sh 清理)
docker exec gateway python -c "
import sqlite3, bcrypt
conn = sqlite3.connect('/data/gateway.db')
h = bcrypt.hashpw(b's-test-123', bcrypt.gensalt(rounds=4)).decode()
conn.execute(\"INSERT OR REPLACE INTO users (id, username, password_hash, role) VALUES (999, '__s_test__', ?, 'user')\", (h,))
conn.commit(); conn.close(); print('user ready')
"
