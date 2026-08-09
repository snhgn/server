import sqlite3
from pathlib import Path

from ..config import settings


def get_connection() -> sqlite3.Connection:
    """创建 SQLite 连接。

    高并发注意：
    - WAL 模式：读写并行，避免读阻塞写
    - busy_timeout=10s：写锁竞争时排队等待而不是立即报 database is locked
    - check_same_thread=False：允许后台任务（to_thread 线程）使用连接
    """
    conn = sqlite3.connect(
        settings.SQLITE_DB_PATH,
        timeout=10.0,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
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

    # ---- conversation_meta 表（会话维度的标题/摘要/关键词）----
    if not _table_exists(conn, "conversation_meta"):
        conn.execute("""
            CREATE TABLE conversation_meta (
                user_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                title TEXT,
                summary TEXT,
                keywords TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                PRIMARY KEY (user_id, session_id)
            )
        """)

    # ---- user_settings 表 ----
    if not _table_exists(conn, "user_settings"):
        conn.execute("""
            CREATE TABLE user_settings (
                user_id INTEGER PRIMARY KEY,
                memory_enabled INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

    # ---- user_files 表（用户上传的临时/知识库文件）----
    if not _table_exists(conn, "user_files"):
        conn.execute("""
            CREATE TABLE user_files (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                storage_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'temp',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_user ON user_files(user_id, status)"
        )

    conn.commit()
    # WAL 模式（持久化到库文件）：读写并行，降低高并发写锁竞争
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    conn.close()
