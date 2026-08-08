import sqlite3
from pathlib import Path

from ..config import settings


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c[1] == column for c in cols)


def init_db() -> None:
    """初始化数据库：memories（含 user_id）+ conversations + user_settings

    全新部署直接创建新 schema；已有库自动补齐缺失的表/列。
    复杂迁移（旧 memories 表改约束）由 scripts/migrate.py 负责。
    """
    Path(settings.SQLITE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()

    # ---- memories 表 ----
    if not _table_exists(conn, "memories"):
        conn.execute("""
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                UNIQUE(user_id, category, key)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mem_user ON memories(user_id, category)"
        )
    elif not _column_exists(conn, "memories", "user_id"):
        # 旧表无 user_id 列：补列（唯一约束变更需走 migrate.py）
        conn.execute(
            "ALTER TABLE memories ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mem_user ON memories(user_id, category)"
        )

    # ---- conversations 表 ----
    if not _table_exists(conn, "conversations"):
        conn.execute("""
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, session_id)"
        )

    # ---- user_settings 表 ----
    if not _table_exists(conn, "user_settings"):
        conn.execute("""
            CREATE TABLE user_settings (
                user_id INTEGER PRIMARY KEY,
                memory_enabled INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

    conn.commit()
    conn.close()
