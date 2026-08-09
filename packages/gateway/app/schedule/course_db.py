# -*- coding: utf-8 -*-
"""课程数据存储（gateway.db）：courses 表 + course_sync_status 表。

- courses            : 规范化后的课程表，按 user_id 隔离（唯一可信来源）
- course_sync_status : 每个用户的同步状态（last_sync_time / sync_status / data_hash）

同步策略：同一用户的课程为全量替换（先删后插），保证与教务系统抓取结果一致。
安全：本模块只存课程信息，绝不存学号/密码/cookie/session。
"""
import logging
import os
import sqlite3

from ..config import settings

logger = logging.getLogger("gateway.schedule.course_db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    course_name    TEXT NOT NULL,
    teacher        TEXT NOT NULL DEFAULT '',
    location       TEXT NOT NULL DEFAULT '',
    weekday        INTEGER NOT NULL,     -- 1-7：周一~周日
    start_section  INTEGER NOT NULL,     -- 开始节次（1 起）
    end_section    INTEGER NOT NULL,     -- 结束节次
    start_week     INTEGER NOT NULL,     -- 开始周（1 起）
    end_week       INTEGER NOT NULL,     -- 结束周
    semester       TEXT NOT NULL,
    update_time    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_courses_user ON courses(user_id, semester);

CREATE TABLE IF NOT EXISTS course_sync_status (
    user_id        INTEGER PRIMARY KEY,
    semester       TEXT NOT NULL DEFAULT '',
    data_hash      TEXT NOT NULL DEFAULT '',
    last_sync_time TEXT NOT NULL DEFAULT '',
    sync_status    TEXT NOT NULL DEFAULT 'pending',  -- pending | success | failed
    last_error     TEXT NOT NULL DEFAULT '',
    sync_type      TEXT NOT NULL DEFAULT 'auto'      -- manual（用户抓取） | auto（定时）
);
"""


def _conn() -> sqlite3.Connection:
    db_dir = os.path.dirname(settings.SQLITE_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(settings.SQLITE_DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(SCHEMA)


# ---------- courses ----------


def replace_courses(user_id: int, semester: str, rows: list[dict]) -> None:
    """全量替换某用户的课程数据。

    rows 元素：{course_name, teacher, location, weekday, start_section,
               end_section, start_week, end_week}
    """
    with _conn() as conn:
        conn.execute("DELETE FROM courses WHERE user_id=?", (user_id,))
        conn.executemany(
            """INSERT INTO courses
               (user_id, course_name, teacher, location, weekday,
                start_section, end_section, start_week, end_week, semester, update_time)
               VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))""",
            [(user_id, r["course_name"], r.get("teacher", ""), r.get("location", ""),
              r["weekday"], r["start_section"], r["end_section"],
              r["start_week"], r["end_week"], semester)
             for r in rows],
        )


def get_courses(user_id: int, semester: str | None = None) -> list[dict]:
    with _conn() as conn:
        if semester:
            rows = conn.execute(
                "SELECT * FROM courses WHERE user_id=? AND semester=? ORDER BY weekday, start_section",
                (user_id, semester),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM courses WHERE user_id=? ORDER BY weekday, start_section",
                (user_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def list_user_ids() -> list[int]:
    """全部有课程数据的 user_id（用于定时同步）。"""
    with _conn() as conn:
        rows = conn.execute("SELECT DISTINCT user_id FROM courses").fetchall()
    return [r["user_id"] for r in rows]


# ---------- course_sync_status ----------


def get_status(user_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM course_sync_status WHERE user_id=?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def upsert_status(user_id: int, *, semester: str, data_hash: str,
                  sync_status: str, last_error: str = "", sync_type: str = "auto") -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO course_sync_status
               (user_id, semester, data_hash, last_sync_time, sync_status, last_error, sync_type)
               VALUES (?,?,?,datetime('now','localtime'),?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                   semester=excluded.semester,
                   data_hash=excluded.data_hash,
                   last_sync_time=excluded.last_sync_time,
                   sync_status=excluded.sync_status,
                   last_error=excluded.last_error,
                   sync_type=excluded.sync_type""",
            (user_id, semester, data_hash, sync_status, last_error, sync_type),
        )


def list_sync_status() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM course_sync_status ORDER BY last_sync_time DESC"
        ).fetchall()
    return [dict(r) for r in rows]
