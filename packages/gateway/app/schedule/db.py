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
