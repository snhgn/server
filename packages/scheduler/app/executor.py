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

# 运行中子进程注册表（job_id -> Process），用于停止任务
_running_procs: dict[str, "asyncio.subprocess.Process"] = {}

# 历史记录 DB 初始化
_HISTORY_DB = os.path.join(os.path.dirname(settings.SQLITE_DB_PATH), "scheduler_history.db")

_db_initialized = False
_insert_count = 0
_TRIM_EVERY = 50  # 每 N 次插入截断一次旧记录，避免每次执行都全表 DELETE


def _init_db() -> None:
    """建表仅执行一次（原先每次查询/写入都 CREATE TABLE IF NOT EXISTS）"""
    global _db_initialized
    if _db_initialized:
        return
    conn = sqlite3.connect(_HISTORY_DB)
    try:
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
    finally:
        conn.close()
    _db_initialized = True


def _get_db() -> sqlite3.Connection:
    _init_db()
    conn = sqlite3.connect(_HISTORY_DB)
    conn.row_factory = sqlite3.Row
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
    global _insert_count
    conn = _get_db()
    try:
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
        # 每 _TRIM_EVERY 次插入截断一次（保留最近 HISTORY_LIMIT 条）
        _insert_count += 1
        if _insert_count % _TRIM_EVERY == 0:
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


async def execute_command(
    command: str, timeout: int, job_id: str | None = None
) -> tuple[bool, str, str]:
    """执行 shell 命令，返回 (success, stdout, stderr)"""
    proc = None
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if job_id:
            _running_procs[job_id] = proc
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        success = proc.returncode == 0
        if not success:
            err = f"exit code {proc.returncode}\n{err}"
        return success, out, err
    except asyncio.TimeoutError:
        if proc is not None and proc.returncode is None:
            proc.kill()
        return False, "", f"Timeout after {timeout}s"
    except Exception as e:
        return False, "", str(e)
    finally:
        if job_id:
            _running_procs.pop(job_id, None)


def kill_command(job_id: str) -> bool:
    """终止正在运行的任务进程；无运行中进程时返回 False"""
    proc = _running_procs.get(job_id)
    if proc is not None and proc.returncode is None:
        try:
            proc.kill()
        except Exception:
            pass
        return True
    return False


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
