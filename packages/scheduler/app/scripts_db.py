"""Scripts 模块数据库：scripts / script_runs / tasks 三表"""
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .config import settings

logger = logging.getLogger("scheduler.scripts_db")

_DB_PATH = settings.SCRIPTS_DB_PATH


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL DEFAULT 'automation',
                command TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'waiting',
                visibility TEXT NOT NULL DEFAULT 'public',
                enabled INTEGER NOT NULL DEFAULT 1,
                owner_id INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS script_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_id INTEGER NOT NULL,
                trigger TEXT NOT NULL DEFAULT 'scheduled',
                start_time TEXT NOT NULL,
                end_time TEXT,
                status TEXT NOT NULL,
                output TEXT,
                error TEXT,
                duration_ms INTEGER
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_id INTEGER NOT NULL UNIQUE,
                cron TEXT,
                next_run TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_runs_script ON script_runs(script_id, id);
            """
        )
        conn.commit()
    finally:
        conn.close()
    logger.info("Scripts DB ready: %s", _DB_PATH)


# ---- scripts ----


def create_script(name: str, description: str, stype: str, command: str,
                  visibility: str, owner_id: int) -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO scripts (name, description, type, command, visibility, owner_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, description, stype, command, visibility, owner_id, _now(), _now()),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def update_script(script_id: int, **fields: Any) -> bool:
    """安全白名单更新；返回是否存在"""
    allowed = {"name", "description", "type", "command", "visibility", "enabled"}
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return get_script(script_id) is not None
    conn = get_conn()
    try:
        data["updated_at"] = _now()
        sets = ", ".join(f"{k}=?" for k in data)
        cur = conn.execute(
            f"UPDATE scripts SET {sets} WHERE id=?", (*data.values(), script_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_script(script_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM scripts WHERE id=?", (script_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_scripts(public_only: bool = False) -> list[dict]:
    conn = get_conn()
    try:
        sql = "SELECT * FROM scripts"
        params: tuple = ()
        if public_only:
            sql += " WHERE visibility='public' AND enabled=1"
        sql += " ORDER BY id DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def delete_script(script_id: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM scripts WHERE id=?", (script_id,))
        conn.execute("DELETE FROM script_runs WHERE script_id=?", (script_id,))
        conn.execute("DELETE FROM tasks WHERE script_id=?", (script_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def set_script_status(script_id: int, status: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE scripts SET status=?, updated_at=? WHERE id=?",
            (status, _now(), script_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---- script_runs ----


def create_run(script_id: int, trigger: str = "scheduled") -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO script_runs (script_id, trigger, start_time, status) VALUES (?, ?, ?, 'running')",
            (script_id, trigger, _now()),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def finish_run(run_id: int, success: bool, output: str, error: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE script_runs SET end_time=?, status=?, output=?, error=?, "
            "duration_ms=CAST((julianday(?) - julianday(start_time)) * 86400000 AS INTEGER) "
            "WHERE id=?",
            (_now(), "success" if success else "failed", output[: settings.SCRIPT_OUTPUT_LIMIT],
             error[: settings.SCRIPT_OUTPUT_LIMIT], _now(), run_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_runs(script_id: int, limit: int = 20) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, script_id, trigger, start_time, end_time, status, duration_ms "
            "FROM script_runs WHERE script_id=? ORDER BY id DESC LIMIT ?",
            (script_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def latest_run(script_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, trigger, start_time, end_time, status, duration_ms "
            "FROM script_runs WHERE script_id=? ORDER BY id DESC LIMIT 1",
            (script_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def latest_failed_error(script_id: int) -> str:
    """最近一次失败运行的 error，用于 AI 分析"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT error FROM script_runs WHERE script_id=? AND status='failed' "
            "AND error IS NOT NULL AND error!='' ORDER BY id DESC LIMIT 1",
            (script_id,),
        ).fetchone()
        return (row["error"] if row else "") or ""
    finally:
        conn.close()


# ---- tasks ----


def upsert_task(script_id: int, cron: str | None, enabled: bool) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO tasks (script_id, cron, enabled, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(script_id) DO UPDATE SET cron=excluded.cron, enabled=excluded.enabled",
            (script_id, cron, 1 if enabled else 0, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_task(script_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE script_id=?", (script_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_task_next_run(script_id: int, next_run: str | None) -> None:
    conn = get_conn()
    try:
        conn.execute("UPDATE tasks SET next_run=? WHERE script_id=?", (next_run, script_id))
        conn.commit()
    finally:
        conn.close()


def delete_task(script_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM tasks WHERE script_id=?", (script_id,))
        conn.commit()
    finally:
        conn.close()
