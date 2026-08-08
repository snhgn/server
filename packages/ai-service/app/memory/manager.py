import logging

from .database import get_connection, init_db

logger = logging.getLogger("ai-service.memory")


class MemoryManager:
    """长期记忆管理：基于 SQLite，存储用户信息、偏好、项目信息等"""

    def __init__(self) -> None:
        init_db()
        logger.info("MemoryManager initialized, db=%s", get_connection().execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def add(self, category: str, key: str, value: str) -> None:
        conn = get_connection()
        conn.execute(
            """INSERT INTO memories (category, key, value)
               VALUES (?, ?, ?)
               ON CONFLICT(category, key) DO UPDATE SET
                   value=excluded.value,
                   updated_at=datetime('now','localtime')""",
            (category, key, value),
        )
        conn.commit()
        conn.close()

    def get_all(self) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM memories ORDER BY category, key").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_by_category(self, category: str) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM memories WHERE category=? ORDER BY key", (category,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_context(self) -> str:
        """获取所有记忆，格式化为 prompt 上下文"""
        memories = self.get_all()
        if not memories:
            return ""
        lines = [f"- [{m['category']}] {m['key']}: {m['value']}" for m in memories]
        return "\n".join(lines)
