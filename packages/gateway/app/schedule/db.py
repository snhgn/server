# -*- coding: utf-8 -*-
"""schedule_cache 表读写（gateway.db）。

只缓存课表数据（semester + schedule_json），绝不存密码/cookie/session。
"""
import logging
import os
import sqlite3

from ..config import settings

logger = logging.getLogger("gateway.schedule.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS schedule_cache (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL UNIQUE,
    semester      TEXT NOT NULL DEFAULT '',
    schedule_json TEXT NOT NULL,
    updated_time  TEXT NOT NULL,
    student_id    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_schedule_student ON schedule_cache(student_id);

CREATE TABLE IF NOT EXISTS schedule_shares (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    code          TEXT NOT NULL UNIQUE,
    student_id    TEXT NOT NULL,
    owner_name    TEXT NOT NULL DEFAULT '',
    schedule_json TEXT NOT NULL DEFAULT '',
    semester      TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_share_code ON schedule_shares(code);
CREATE INDEX IF NOT EXISTS idx_share_student ON schedule_shares(student_id);

CREATE TABLE IF NOT EXISTS grade_monitors (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_grade_monitor_student ON grade_monitors(student_id);
"""


def _conn() -> sqlite3.Connection:
    db_dir = os.path.dirname(settings.SQLITE_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(settings.SQLITE_DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(SCHEMA)
        # 兼容旧表升级：增补 student_id 列
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(schedule_cache)").fetchall()]
        if "student_id" not in cols:
            try:
                conn.execute("ALTER TABLE schedule_cache ADD COLUMN student_id TEXT NOT NULL DEFAULT ''")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_schedule_student ON schedule_cache(student_id)")
            except Exception as e:
                logger.warning("Failed to alter schedule_cache: %s", e)


def get_cache(user_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT user_id, semester, schedule_json, updated_time, student_id"
            " FROM schedule_cache WHERE user_id=?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def get_cache_by_student(student_id: str) -> dict | None:
    sid = student_id.strip()
    if not sid:
        return None
    with _conn() as conn:
        row = conn.execute(
            "SELECT user_id, semester, schedule_json, updated_time, student_id"
            " FROM schedule_cache WHERE student_id=? ORDER BY updated_time DESC LIMIT 1",
            (sid,),
        ).fetchone()
    return dict(row) if row else None


def upsert_cache(user_id: int, semester: str, schedule_json: str, updated_time: str, student_id: str = "") -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO schedule_cache (user_id, semester, schedule_json, updated_time, student_id)"
            " VALUES (?,?,?,?,?)"
            " ON CONFLICT(user_id) DO UPDATE SET"
            " semester=excluded.semester, schedule_json=excluded.schedule_json,"
            " updated_time=excluded.updated_time,"
            " student_id=CASE WHEN excluded.student_id != '' THEN excluded.student_id ELSE schedule_cache.student_id END",
            (user_id, semester, schedule_json, updated_time, student_id),
        )


def list_caches() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT user_id, semester, updated_time, student_id FROM schedule_cache"
            " ORDER BY updated_time DESC"
        ).fetchall()
    return [dict(r) for r in rows]


SHARE_CODE_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 32 个易读字符（去除 0, O, 1, I 防混淆）


def generate_unique_share_code() -> str:
    import secrets
    with _conn() as conn:
        for _ in range(200):
            code = "".join(secrets.choice(SHARE_CODE_CHARS) for _ in range(4))
            row = conn.execute("SELECT 1 FROM schedule_shares WHERE code=?", (code,)).fetchone()
            if not row:
                return code
    raise RuntimeError("无法生成唯一的4位邀请码")


def get_share_by_code(code: str) -> dict | None:
    c = code.strip().upper()
    if not c:
        return None
    with _conn() as conn:
        row = conn.execute(
            "SELECT code, student_id, owner_name, schedule_json, semester, created_at, updated_at"
            " FROM schedule_shares WHERE code=?",
            (c,),
        ).fetchone()
    return dict(row) if row else None


def get_share_by_student(student_id: str) -> dict | None:
    sid = student_id.strip()
    if not sid:
        return None
    with _conn() as conn:
        row = conn.execute(
            "SELECT code, student_id, owner_name, schedule_json, semester, created_at, updated_at"
            " FROM schedule_shares WHERE student_id=? ORDER BY updated_at DESC LIMIT 1",
            (sid,),
        ).fetchone()
    return dict(row) if row else None


def create_or_update_share(student_id: str, owner_name: str, schedule_json: str, semester: str, regenerate: bool = False) -> str:
    """为指定学号创建或更新4位邀请码。
    如已有且 regenerate=False，保留原码并刷新课表快照与备注名；
    如 regenerate=True，删除旧码生成全新4位码。
    """
    sid = student_id.strip()
    from datetime import datetime, timezone
    now_str = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    existing = get_share_by_student(sid)
    if existing and not regenerate:
        code = existing["code"]
        name = owner_name.strip() or existing["owner_name"]
        with _conn() as conn:
            conn.execute(
                "UPDATE schedule_shares SET owner_name=?, schedule_json=?, semester=?, updated_at=?"
                " WHERE code=?",
                (name, schedule_json, semester, now_str, code),
            )
        return code

    # 需要生成新码
    with _conn() as conn:
        if existing:
            conn.execute("DELETE FROM schedule_shares WHERE student_id=?", (sid,))
        code = generate_unique_share_code()
        name = owner_name.strip()
        conn.execute(
            "INSERT INTO schedule_shares (code, student_id, owner_name, schedule_json, semester, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (code, sid, name, schedule_json, semester, now_str, now_str),
        )
        return code


def get_grade_monitor(student_id: str) -> dict | None:
    """获取指定学号的成绩监控配置。"""
    sid = student_id.strip()
    if not sid:
        return None
    with _conn() as conn:
        row = conn.execute(
            "SELECT student_id, email, enabled, created_at, updated_at FROM grade_monitors WHERE student_id = ?",
            (sid,),
        ).fetchone()
        if not row:
            return None
        return dict(row)


def save_grade_monitor(student_id: str, email: str, enabled: bool = True) -> dict:
    """保存或更新指定学号的成绩出分监控配置。"""
    sid = student_id.strip()
    em = email.strip()
    enabled_int = 1 if enabled else 0
    from datetime import datetime, timezone
    now_str = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO grade_monitors (student_id, email, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                email = excluded.email,
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (sid, em, enabled_int, now_str, now_str),
        )
    return {
        "student_id": sid,
        "email": em,
        "enabled": bool(enabled_int),
        "updated_at": now_str,
    }

