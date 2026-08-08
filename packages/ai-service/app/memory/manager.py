import logging

from .database import get_connection, init_db

logger = logging.getLogger("ai-service.memory")


class MemoryManager:
    """长期记忆管理：基于 SQLite，按 user_id 隔离"""

    def __init__(self) -> None:
        init_db()
        count = get_connection().execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        logger.info("MemoryManager initialized, memories=%d", count)

    def add(self, user_id: int, category: str, key: str, value: str) -> None:
        conn = get_connection()
        conn.execute(
            """INSERT INTO memories (user_id, category, key, value)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, category, key) DO UPDATE SET
                   value=excluded.value,
                   updated_at=datetime('now','localtime')""",
            (user_id, category, key, value),
        )
        conn.commit()
        conn.close()

    def get_all(self, user_id: int) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM memories WHERE user_id=? ORDER BY category, key",
            (user_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_by_category(self, user_id: int, category: str) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM memories WHERE user_id=? AND category=? ORDER BY key",
            (user_id, category),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_context(self, user_id: int) -> str:
        """获取该用户的所有记忆，格式化为 prompt 上下文"""
        memories = self.get_all(user_id)
        if not memories:
            return ""
        lines = [f"- [{m['category']}] {m['key']}: {m['value']}" for m in memories]
        return "\n".join(lines)

    def delete(self, user_id: int, category: str, key: str) -> bool:
        """删除一条记忆，返回是否删除成功"""
        conn = get_connection()
        cur = conn.execute(
            "DELETE FROM memories WHERE user_id=? AND category=? AND key=?",
            (user_id, category, key),
        )
        conn.commit()
        conn.close()
        return cur.rowcount > 0


class ConversationStore:
    """对话历史存储：按 user_id + session_id 隔离"""

    def __init__(self) -> None:
        init_db()

    def add(self, user_id: int, session_id: str, message: str, response: str) -> None:
        conn = get_connection()
        conn.execute(
            """INSERT INTO conversations (user_id, session_id, message, response)
               VALUES (?, ?, ?, ?)""",
            (user_id, session_id, message, response),
        )
        conn.commit()
        conn.close()

    def get_history(self, user_id: int, session_id: str, limit: int = 20) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            """SELECT * FROM conversations
               WHERE user_id=? AND session_id=?
               ORDER BY id DESC LIMIT ?""",
            (user_id, session_id, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in reversed(rows)]

    def list_sessions(self, user_id: int) -> list[dict]:
        """列出用户的所有 session（去重，含最后对话时间）"""
        conn = get_connection()
        rows = conn.execute(
            """SELECT session_id, COUNT(*) as msg_count,
                      MAX(created_at) as last_at
               FROM conversations WHERE user_id=?
               GROUP BY session_id ORDER BY last_at DESC""",
            (user_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


class UserSettingsManager:
    """用户设置管理：memory_enabled 开关等"""

    def __init__(self) -> None:
        init_db()

    def get(self, user_id: int) -> dict:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM user_settings WHERE user_id=?", (user_id,)
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        # 默认值：memory_enabled=1
        return {"user_id": user_id, "memory_enabled": 1, "updated_at": None}

    def set_memory_enabled(self, user_id: int, enabled: bool) -> None:
        conn = get_connection()
        conn.execute(
            """INSERT INTO user_settings (user_id, memory_enabled, updated_at)
               VALUES (?, ?, datetime('now','localtime'))
               ON CONFLICT(user_id) DO UPDATE SET
                   memory_enabled=excluded.memory_enabled,
                   updated_at=datetime('now','localtime')""",
            (user_id, 1 if enabled else 0),
        )
        conn.commit()
        conn.close()
