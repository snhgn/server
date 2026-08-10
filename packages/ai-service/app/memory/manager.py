import logging
import uuid
from pathlib import Path

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

    def get_first_exchange(self, user_id: int, session_id: str) -> dict | None:
        """取该会话第一条用户消息 + AI 回复（用于生成标题摘要）"""
        conn = get_connection()
        row = conn.execute(
            """SELECT message, response FROM conversations
               WHERE user_id=? AND session_id=?
               ORDER BY id ASC LIMIT 1""",
            (user_id, session_id),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def list_sessions(self, user_id: int) -> list[dict]:
        """列出用户的所有 session（去重，含 meta：title/summary/keywords）"""
        conn = get_connection()
        rows = conn.execute(
            """SELECT c.session_id,
                      COUNT(*) as msg_count,
                      MAX(c.created_at) as last_at,
                      m.title,
                      m.summary,
                      m.keywords,
                      (SELECT message FROM conversations c2
                        WHERE c2.user_id=? AND c2.session_id=c.session_id
                        ORDER BY c2.id ASC LIMIT 1) as first_msg
               FROM conversations c
               LEFT JOIN conversation_meta m
                      ON m.user_id = c.user_id AND m.session_id = c.session_id
               WHERE c.user_id=?
               GROUP BY c.session_id
               ORDER BY last_at DESC""",
            (user_id, user_id),
        ).fetchall()
        conn.close()
        result: list[dict] = []
        for r in rows:
            d = dict(r)
            # keywords 存储为 JSON 字符串，解析成数组
            if d.get("keywords"):
                import json as _json
                try:
                    d["keywords"] = _json.loads(d["keywords"])
                except Exception:
                    d["keywords"] = []
            else:
                d["keywords"] = []
            # fallback 标题：优先 meta.title，其次 first_msg 前 15 字，最后 "新对话"
            if not d.get("title"):
                first = (d.get("first_msg") or "").strip()
                d["title"] = (first[:15] + "…") if len(first) > 15 else first or "新对话"
            # fallback 摘要
            if not d.get("summary"):
                d["summary"] = ""
            d.pop("first_msg", None)
            result.append(d)
        return result

    # ---------- conversation_meta ----------

    def upsert_meta(
        self,
        user_id: int,
        session_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        keywords: list[str] | None = None,
    ) -> None:
        """写入/更新会话元信息（title/summary/keywords）"""
        conn = get_connection()
        kw_json = None
        if keywords is not None:
            import json as _json
            kw_json = _json.dumps(keywords, ensure_ascii=False)
        conn.execute(
            """INSERT INTO conversation_meta (user_id, session_id, title, summary, keywords)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, session_id) DO UPDATE SET
                   title=COALESCE(excluded.title, conversation_meta.title),
                   summary=COALESCE(excluded.summary, conversation_meta.summary),
                   keywords=COALESCE(excluded.keywords, conversation_meta.keywords),
                   updated_at=datetime('now','localtime')""",
            (user_id, session_id, title, summary, kw_json),
        )
        conn.commit()
        conn.close()

    def get_meta(self, user_id: int, session_id: str) -> dict | None:
        conn = get_connection()
        row = conn.execute(
            """SELECT * FROM conversation_meta WHERE user_id=? AND session_id=?""",
            (user_id, session_id),
        ).fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        if d.get("keywords"):
            import json as _json
            try:
                d["keywords"] = _json.loads(d["keywords"])
            except Exception:
                d["keywords"] = []
        else:
            d["keywords"] = []
        return d


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
        # 默认值：memory_enabled=1，ai_provider=None（自动）
        return {
            "user_id": user_id,
            "memory_enabled": 1,
            "ai_provider": None,
            "updated_at": None,
        }

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

    def set_ai_provider(self, user_id: int, provider: str | None) -> None:
        """设置 AI provider 偏好：None=自动，'glm'/'gemini'=固定首选该 provider"""
        conn = get_connection()
        conn.execute(
            """INSERT INTO user_settings (user_id, ai_provider, updated_at)
               VALUES (?, ?, datetime('now','localtime'))
               ON CONFLICT(user_id) DO UPDATE SET
                   ai_provider=excluded.ai_provider,
                   updated_at=datetime('now','localtime')""",
            (user_id, provider),
        )
        conn.commit()
        conn.close()


# ---- 文件扩展名分类 ----
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
TEXT_EXTS = {".md", ".markdown", ".txt", ".pdf"}
CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h",
    ".go", ".rs", ".rb", ".php", ".sh", ".bash", ".zsh", ".vue", ".css",
    ".scss", ".html", ".xml", ".yaml", ".yml", ".json", ".toml", ".sql",
    ".kt", ".swift", ".r", ".lua", ".pl",
}


def classify_file_type(filename: str) -> str:
    """根据文件名返回类型：image / text / code / unknown"""
    suffix = Path(filename).suffix.lower()
    if suffix in IMAGE_EXTS:
        return "image"
    if suffix in TEXT_EXTS:
        return "text"
    if suffix in CODE_EXTS:
        return "code"
    return "unknown"


class FileManager:
    """用户上传文件管理：临时文件 + 知识库文件，按 user_id 隔离"""

    def __init__(self, storage_root: str) -> None:
        init_db()
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, user_id: int) -> Path:
        d = self.storage_root / f"user_{user_id}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def create(
        self,
        user_id: int,
        filename: str,
        file_type: str,
        file_size: int,
        storage_path: str,
    ) -> str:
        """新增文件记录，返回 file_id"""
        file_id = uuid.uuid4().hex[:16]
        conn = get_connection()
        conn.execute(
            """INSERT INTO user_files
               (id, user_id, filename, file_type, file_size, storage_path, status)
               VALUES (?, ?, ?, ?, ?, ?, 'temp')""",
            (file_id, user_id, filename, file_type, file_size, storage_path),
        )
        conn.commit()
        conn.close()
        return file_id

    def get(self, user_id: int, file_id: str) -> dict | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM user_files WHERE id=? AND user_id=?",
            (file_id, user_id),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def list_by_user(self, user_id: int, status: str | None = None) -> list[dict]:
        conn = get_connection()
        if status:
            rows = conn.execute(
                "SELECT * FROM user_files WHERE user_id=? AND status=? ORDER BY created_at DESC",
                (user_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM user_files WHERE user_id=? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def list_by_ids(self, user_id: int, file_ids: list[str]) -> list[dict]:
        if not file_ids:
            return []
        placeholders = ",".join(["?"] * len(file_ids))
        conn = get_connection()
        rows = conn.execute(
            f"SELECT * FROM user_files WHERE user_id=? AND id IN ({placeholders}) "
            f"AND status != 'deleted'",
            (user_id, *file_ids),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_status(self, user_id: int, file_id: str, status: str) -> bool:
        conn = get_connection()
        cur = conn.execute(
            """UPDATE user_files
               SET status=?, updated_at=datetime('now','localtime')
               WHERE id=? AND user_id=?""",
            (status, file_id, user_id),
        )
        conn.commit()
        conn.close()
        return cur.rowcount > 0

    def delete(self, user_id: int, file_id: str) -> bool:
        """物理删除文件 + 记录"""
        rec = self.get(user_id, file_id)
        if not rec:
            return False
        try:
            p = Path(rec["storage_path"])
            if p.exists():
                p.unlink()
        except Exception as exc:
            logger.warning("delete file failed id=%s: %s", file_id, exc)
        conn = get_connection()
        conn.execute(
            "DELETE FROM user_files WHERE id=? AND user_id=?",
            (file_id, user_id),
        )
        conn.commit()
        conn.close()
        return True
