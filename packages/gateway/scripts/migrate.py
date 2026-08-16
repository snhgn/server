"""Gateway 数据库迁移：创建 users 表

用法:
    python scripts/migrate.py

环境变量:
    GATEWAY_DB_PATH  SQLite 路径（默认 /data/gateway.db）
"""
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("SQLITE_DB_PATH", "/data/gateway.db")


def migrate() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # ---- users 表 ----
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    # ---- schedule_cache 表（只存课表，不存登录凭证）----
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schedule_cache (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL UNIQUE,
            semester      TEXT NOT NULL DEFAULT '',
            schedule_json TEXT NOT NULL,
            updated_time  TEXT NOT NULL
        )
    """)
    # ---- sessions 表（登录 Session，HttpOnly Cookie 对应的服务端存储）----
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            sid         TEXT PRIMARY KEY,
            user_id     INTEGER NOT NULL,
            created_at  TEXT NOT NULL,
            expires_at  TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    print(f"[gateway] users 表就绪，当前用户数: {count}")
    conn.close()


if __name__ == "__main__":
    migrate()
