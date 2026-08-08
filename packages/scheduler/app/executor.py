"""任务执行 + 历史记录"""
import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import time
from datetime import datetime

import httpx

from .config import settings

logger = logging.getLogger("scheduler.executor")

# 历史记录 DB 初始化
_HISTORY_DB = os.path.join(os.path.dirname(settings.SQLITE_DB_PATH), "scheduler_history.db")


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_HISTORY_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            job_name TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_ms INTEGER,
            success INTEGER NOT NULL,
            output TEXT,
            error TEXT
        )
    """)
    conn.commit()
    return conn


def record_history(
    job_id: str,
    job_name: str,
    started_at: datetime,
    finished_at: datetime,
    success: bool,
    output: str = "",
    error: str = "",
) -> None:
    """记录一次任务执行结果"""
    conn = _get_db()
    try:
        # 保留最近的 HISTORY_LIMIT 条
        conn.execute(
            "INSERT INTO run_history (job_id, job_name, started_at, finished_at, duration_ms, success, output, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job_id, job_name,
                started_at.isoformat(), finished_at.isoformat(),
                int((finished_at - started_at).total_seconds() * 1000),
                1 if success else 0,
                output[:5000], error[:5000],
            ),
        )
        conn.execute(
            "DELETE FROM run_history WHERE id NOT IN "
            "(SELECT id FROM run_history ORDER BY id DESC LIMIT ?)",
            (settings.HISTORY_LIMIT,),
        )
        conn.commit()
    finally:
        conn.close()


def get_history(job_id: str | None = None, limit: int = 20) -> list[dict]:
    """查询执行历史"""
    conn = _get_db()
    try:
        if job_id:
            rows = conn.execute(
                "SELECT * FROM run_history WHERE job_id=? ORDER BY id DESC LIMIT ?",
                (job_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM run_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


async def execute_command(command: str, timeout: int) -> tuple[bool, str, str]:
    """执行 shell 命令，返回 (success, stdout, stderr)"""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        success = proc.returncode == 0
        if not success:
            err = f"exit code {proc.returncode}\n{err}"
        return success, out, err
    except asyncio.TimeoutError:
        proc.kill()  # type: ignore
        return False, "", f"Timeout after {timeout}s"
    except Exception as e:
        return False, "", str(e)


async def execute_http(
    url: str, method: str = "GET", headers: dict | None = None,
    body: str | None = None, timeout: int = 30,
) -> tuple[bool, str, str]:
    """执行 HTTP 请求，返回 (success, response_body, error)"""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method, url,
                headers=headers or {},
                json=json.loads(body) if body else None,
            )
            success = 200 <= resp.status_code < 400
            out = f"HTTP {resp.status_code}\n{resp.text[:2000]}"
            err = "" if success else f"HTTP {resp.status_code}"
            return success, out, err
    except Exception as e:
        return False, "", str(e)
