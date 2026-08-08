"""AI-service 数据库迁移：多用户数据隔离

变更内容:
    1. memories 表：新增 user_id 列（现有数据归 user_id=1，即 admin）
    2. 新增 conversations 表：用户对话记录
    3. 新增 user_settings 表：用户偏好（memory_enabled 开关）

用法:
    python scripts/migrate.py

环境变量:
    AI_SERVICE_DB_PATH  SQLite 路径（默认 /data/memory.db）

迁移策略:
    - ALTER TABLE ADD COLUMN 保留现有数据
    - memories 唯一约束从 UNIQUE(category, key) 变为 UNIQUE(user_id, category, key)
      SQLite 不支持就地修改约束，采用「建新表 → 拷数据 → 删旧表 → 重命名」
    - 幂等：可重复执行，已迁移的步骤自动跳过
"""
import os
import sqlite3
import sys
from pathlib import Path

DB_PATH = os.getenv("SQLITE_DB_PATH", "/data/memory.db")


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """检查表是否已有某列"""
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c[1] == column for c in cols)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def migrate_memories(conn: sqlite3.Connection) -> None:
    """迁移 memories 表：增加 user_id 列，修改唯一约束"""
    if not _table_exists(conn, "memories"):
        # 全新部署：直接创建带 user_id 的表
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
        conn.commit()
        print("[ai-service] memories 表已创建（含 user_id）")
        return

    # 已有表：检查是否已迁移
    if _column_exists(conn, "memories", "user_id"):
        print("[ai-service] memories 表已含 user_id，跳过")
        return

    # 迁移：建新表 → 拷数据 → 删旧表 → 重命名
    print("[ai-service] 开始迁移 memories 表（新增 user_id 列）...")
    conn.execute("""
        CREATE TABLE memories_new (
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
    conn.execute("""
        INSERT INTO memories_new (id, user_id, category, key, value, created_at, updated_at)
        SELECT id, 1, category, key, value, created_at, updated_at FROM memories
    """)
    conn.execute("DROP TABLE memories")
    conn.execute("ALTER TABLE memories_new RENAME TO memories")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mem_user ON memories(user_id, category)"
    )
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    print(f"[ai-service] memories 迁移完成，现有 {count} 条记录，全部归 user_id=1")


def migrate_conversations(conn: sqlite3.Connection) -> None:
    """创建 conversations 表"""
    if _table_exists(conn, "conversations"):
        print("[ai-service] conversations 表已存在，跳过")
        return

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
    conn.commit()
    print("[ai-service] conversations 表已创建")


def migrate_user_settings(conn: sqlite3.Connection) -> None:
    """创建 user_settings 表"""
    if _table_exists(conn, "user_settings"):
        print("[ai-service] user_settings 表已存在，跳过")
        return

    conn.execute("""
        CREATE TABLE user_settings (
            user_id INTEGER PRIMARY KEY,
            memory_enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.commit()
    print("[ai-service] user_settings 表已创建")


def migrate() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    print(f"[ai-service] 数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        migrate_memories(conn)
        migrate_conversations(conn)
        migrate_user_settings(conn)
        print("[ai-service] 迁移全部完成")
    except Exception as e:
        print(f"[ai-service] 迁移失败: {e}", file=sys.stderr)
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
