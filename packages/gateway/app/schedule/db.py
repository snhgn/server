# -*- coding: utf-8 -*-
"""schedule_cache 表读写（gateway.db）。

只缓存课表数据（semester + schedule_json），绝不存学号/密码/cookie/session。
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
    updated_time  TEXT NOT NULL
);
"""


def _conn() -> sqlite3.Connection:
    db_dir = os.path.dirname(settings.SQLITE_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(settings.SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute(SCHEMA)


def get_cache(user_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT user_id, semester, schedule_json, updated_time"
            " FROM schedule_cache WHERE user_id=?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def upsert_cache(user_id: int, semester: str, schedule_json: str, updated_time: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO schedule_cache (user_id, semester, schedule_json, updated_time)"
            " VALUES (?,?,?,?)"
            " ON CONFLICT(user_id) DO UPDATE SET"
            " semester=excluded.semester, schedule_json=excluded.schedule_json,"
            " updated_time=excluded.updated_time",
            (user_id, semester, schedule_json, updated_time),
        )


def list_caches() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT user_id, semester, updated_time FROM schedule_cache"
            " ORDER BY updated_time DESC"
        ).fetchall()
    return [dict(r) for r in rows]
