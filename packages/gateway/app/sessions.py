"""Server-side Session 存储（SQLite，复用 gateway.db）

表结构：
    sessions(sid PK, user_id, created_at, expires_at, last_seen_at)

设计要点：
- sid 使用 secrets.token_urlsafe(32)（256-bit 随机，不可预测）
- 过期采用固定窗口（SESSION_EXPIRE_DAYS），不做滑动续期（简单可预期）
- 惰性清理：create 时顺带删除已过期行，避免额外定时任务
- 全部函数为同步 SQLite 调用，调用方（async 路由）需经 asyncio.to_thread
"""
import logging
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from .config import settings

logger = logging.getLogger("gateway.sessions")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    sid         TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    """幂等建表（应用启动时调用）"""
    conn = _get_conn()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def create_session(user_id: int) -> tuple[str, datetime]:
    """创建新 Session，返回 (sid, expires_at)。顺带清理过期行。"""
    sid = secrets.token_urlsafe(32)
    now = _now()
    expires = now + timedelta(days=settings.SESSION_EXPIRE_DAYS)
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_fmt(now),))
        conn.execute(
            "INSERT INTO sessions (sid, user_id, created_at, expires_at, last_seen_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (sid, user_id, _fmt(now), _fmt(expires), _fmt(now)),
        )
        conn.commit()
    finally:
        conn.close()
    return sid, expires


def get_session_user_id(sid: str) -> int | None:
    """按 sid 查询有效 Session 对应的 user_id；不存在/过期返回 None。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT user_id, expires_at FROM sessions WHERE sid=?", (sid,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    if _parse(row["expires_at"]) <= _now():
        return None
    return int(row["user_id"])


def touch_session(sid: str) -> None:
    """更新最后活跃时间（仅观测用途，best-effort，失败忽略）"""
    try:
        conn = _get_conn()
        try:
            conn.execute(
                "UPDATE sessions SET last_seen_at=? WHERE sid=?", (_fmt(_now()), sid)
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:  # pragma: no cover
        logger.debug("touch_session failed: %s", e)


def delete_session(sid: str) -> None:
    """删除单个 Session（logout / 旋转时调用）"""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM sessions WHERE sid=?", (sid,))
        conn.commit()
    finally:
        conn.close()


def delete_user_sessions(user_id: int) -> None:
    """删除某用户全部 Session（改密/封禁时踢下线）"""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()
