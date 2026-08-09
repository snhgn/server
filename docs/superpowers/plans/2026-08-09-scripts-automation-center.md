# Scripts 自动化中心模块 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 superpowers:executing-plans 按任务逐步实现。步骤用 checkbox（`- [ ]`）跟踪。

**Goal:** 在现有平台中加入 Scripts 自动化脚本管理模块，让 `/scripts`（User 只读展示）与 `/admin/scripts`（Admin 完整管理）统一展示和管理服务器自动化能力，执行权严格限制在 Admin。

**Architecture:** 复用现有 Scheduler 服务（APScheduler + 命令执行器），在其内部新增 scripts 模块（数据库 + 执行器 + 路由）。执行链路：Frontend → Gateway（角色校验）→ Scheduler scripts 模块（注册 APScheduler job）→ Worker（executor 命令执行）→ 脚本文件。执行结果写入 `script_runs` 表 + 独立日志文件。AI 错误分析复用 ai-service `/api/chat`。

**Tech Stack:** Python 3.12 / FastAPI / APScheduler / SQLite / httpx；前端 Vue3 + Vite + TS + Tailwind v4。

---

## 关键决策（已与用户确认）

1. **模块位置**：扩展 Scheduler 服务（新增模块，不改 core.py 核心调度逻辑）。
2. **脚本部署**：挂载 `/opt/snhgn/scripts:/data/scripts` 到 scheduler 容器，Admin 表单填写执行命令（如 `python /data/scripts/notice-monitor/main.py`）。
3. **权限修复**：Gateway `/api/scheduler/*` 代理改为写操作（POST/PUT/DELETE）仅 Admin。

## 文件结构

**后端（scheduler 服务）**
- 新建 `packages/scheduler/app/scripts_db.py` — scripts/script_runs/tasks 三表 + CRUD
- 新建 `packages/scheduler/app/scripts_runner.py` — 执行命令 + 日志写入 + 状态更新
- 新建 `packages/scheduler/app/scripts_core.py` — APScheduler 任务注册/启停 + 手动运行/停止
- 新建 `packages/scheduler/app/routers/scripts.py` — User + Admin API 路由
- 修改 `packages/scheduler/app/main.py` — include scripts 路由 + init_db
- 修改 `packages/scheduler/app/config.py` — 新增 scripts 配置
- 修改 `packages/scheduler/app/executor.py` — 进程注册表（支持停止）
- 修改 `packages/scheduler/.env.example`
- 修改 `packages/scheduler/Dockerfile`（无需改，无新依赖）与根 `docker-compose.yml`（新增卷）

**后端（gateway 服务）**
- 新建 `packages/gateway/app/routers/scripts.py` — `/api/scripts/*`(user) + `/api/admin/scripts/*`(admin) 代理
- 修改 `packages/gateway/app/main.py` — include scripts 路由
- 修改 `packages/gateway/app/routers/scheduler.py` — 写操作仅 Admin

**前端（d:\project\snhgn.me）**
- 修改 `src/data/scripts.ts` — 类型定义（替换 mock）
- 新建 `src/components/Scripts/ScriptStatus.vue`
- 新建 `src/components/Scripts/ScriptCard.vue`
- 新建 `src/components/Scripts/RunHistory.vue`
- 新建 `src/components/Scripts/LogViewer.vue`
- 新建 `src/components/Scripts/AdminScriptForm.vue`
- 修改 `src/views/ScriptsView.vue` — 真实数据展示页
- 新建 `src/views/AdminScriptsView.vue` — 管理页
- 修改 `src/router/index.ts` — 新增 `/admin/scripts`
- 修改 `src/components/Navbar.vue` — admin 增加 Script Management 入口

---

## 任务 1：Scheduler 配置扩展

**Files:**
- Modify: `packages/scheduler/app/config.py`
- Modify: `packages/scheduler/.env.example`

- [ ] **Step 1: config.py 增加 Scripts 配置**

```python
    # ---- Scripts 自动化模块 ----
    SCRIPTS_DB_PATH: str = "/data/sqlite/scripts.db"
    SCRIPTS_LOG_DIR: str = "/app/logs/scripts"
    SCRIPT_TIMEOUT: int = 1800          # 单次脚本执行超时（秒）
    SCRIPT_OUTPUT_LIMIT: int = 10000    # script_runs.output 截断长度
    LOG_TAIL_LINES: int = 200           # 日志接口返回行数

    # ---- AI 错误分析（复用 ai-service）----
    AI_SERVICE_URL: str = "http://ai-service:8000"
    AI_ANALYZE_TIMEOUT: float = 60.0
```

- [ ] **Step 2: .env.example 增加说明**

在 `packages/scheduler/.env.example` 末尾追加：

```
# ---- Scripts 自动化模块（以下有默认值，可留空）----
# SCRIPTS_DB_PATH=/data/sqlite/scripts.db
# SCRIPTS_LOG_DIR=/app/logs/scripts
# SCRIPT_TIMEOUT=1800
# AI_SERVICE_URL=http://ai-service:8000
```

---

## 任务 2：scripts_db.py（三表 + CRUD）

**Files:**
- Create: `packages/scheduler/app/scripts_db.py`

- [ ] **Step 1: 完整实现**

```python
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
                visibility TEXT NOT NULL DEFAULT 'private',
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
```

---

## 任务 3：executor.py 增加进程注册表（支持停止）

**Files:**
- Modify: `packages/scheduler/app/executor.py`

- [ ] **Step 1: 增加 `_running_procs` 注册表**

在 `executor.py` 的 `logger = logging.getLogger("scheduler.executor")` 后增加：

```python
# 运行中子进程注册表（job_id -> Process），用于停止任务
_running_procs: dict[str, "asyncio.subprocess.Process"] = {}
```

- [ ] **Step 2: `execute_command` 增加可选 `job_id` 参数并注册**

将现有 `execute_command` 函数整体替换为：

```python
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
```

（原 `_execute_job` 调用 `execute_command(payload, timeout)` 位置参数不受影响。）

---

## 任务 4：scripts_runner.py（执行 + 日志 + 状态）

**Files:**
- Create: `packages/scheduler/app/scripts_runner.py`

- [ ] **Step 1: 完整实现**

```python
"""脚本执行：命令运行 + 每日分片日志 + 状态回写"""
import logging
import os
from datetime import datetime, timezone

from . import scripts_db as db
from .config import settings
from .executor import execute_command

logger = logging.getLogger("scheduler.scripts_runner")


def _script_log_dir(name: str) -> str:
    return os.path.join(settings.SCRIPTS_LOG_DIR, name)


def _log_path(name: str, dt: datetime) -> str:
    return os.path.join(_script_log_dir(name), dt.strftime("%Y-%m-%d") + ".log")


def write_log(name: str, line: str) -> None:
    """追加一行到当日日志文件（自动建目录）"""
    try:
        d = datetime.now(timezone.utc).astimezone()
        path = _log_path(name, d)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{d.isoformat(timespec='seconds')}] {line}\n")
    except Exception as exc:
        logger.warning("write_log failed %s: %s", name, exc)


def read_log_tail(name: str, lines: int | None = None) -> list[str]:
    """读取当日日志末尾 N 行"""
    path = _log_path(name, datetime.now(timezone.utc).astimezone())
    if not os.path.exists(path):
        return []
    n = lines or settings.LOG_TAIL_LINES
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().splitlines()[-n:]
    except Exception as exc:
        logger.warning("read_log_tail failed: %s", exc)
        return []


async def execute_script(script_id: int, trigger: str = "scheduled",
                         run_id: int | None = None) -> None:
    """执行脚本：建 run 记录 → 跑命令 → 写结果/日志 → 回写状态。
    run_id 由手动运行预创建时传入；定时任务为 None 时自动创建。"""
    script = db.get_script(script_id)
    if not script:
        return
    # 定时触发且已禁用 → 跳过
    if trigger == "scheduled" and not script["enabled"]:
        return

    run_id = run_id or db.create_run(script_id, trigger)
    db.set_script_status(script_id, "running")

    log_head = f"===== RUN #{run_id} trigger={trigger} start ====="
    write_log(script["name"], log_head)

    success, output, error = False, "", ""
    try:
        success, output, error = await execute_command(
            script["command"], settings.SCRIPT_TIMEOUT, job_id=f"script_{script_id}"
        )
    except Exception as exc:
        error = str(exc)

    db.finish_run(run_id, success, output, error)

    # 状态回写：失败 → failed；成功 → 启用则 waiting / 禁用则 disabled
    if success:
        db.set_script_status(script_id, "disabled" if not script["enabled"] else "waiting")
    else:
        db.set_script_status(script_id, "failed")

    # 日志：输出摘要 + 错误
    out_tail = output.strip().splitlines()[-20:] if output.strip() else []
    for line in out_tail:
        write_log(script["name"], f"[output] {line}")
    if error.strip():
        for line in error.strip().splitlines()[:20]:
            write_log(script["name"], f"[error] {line}")
    write_log(script["name"], f"===== RUN #{run_id} end {'OK' if success else 'FAILED'} =====")

    logger.info("Script %s (%s) trigger=%s -> %s", script["name"], run_id, trigger,
                "OK" if success else "FAILED")
```

---

## 任务 5：scripts_core.py（APScheduler 集成）

**Files:**
- Create: `packages/scheduler/app/scripts_core.py`

- [ ] **Step 1: 完整实现**

```python
"""Scripts 与 APScheduler 集成：任务注册/启停 + 手动运行/停止"""
import asyncio
import logging

from apscheduler.triggers.cron import CronTrigger

from . import scripts_db as db
from .config import settings
from .core import get_scheduler
from .executor import kill_command
from .scripts_runner import execute_script

logger = logging.getLogger("scheduler.scripts_core")

JOB_PREFIX = "script_"


def job_id(script_id: int) -> str:
    return f"{JOB_PREFIX}{script_id}"


def sync_task(script_id: int, cron: str | None, enabled: bool) -> None:
    """同步 APScheduler 任务：无 cron 或禁用则移除；否则注册/替换"""
    sched = get_scheduler()
    jid = job_id(script_id)
    existing = sched.get_job(jid)
    if existing:
        existing.remove()

    db.upsert_task(script_id, cron, enabled)

    if cron and enabled:
        trigger = CronTrigger.from_crontab(cron, timezone=settings.TIMEZONE)
        sched.add_job(
            execute_script, trigger=trigger, id=jid,
            args=[script_id, "scheduled"],
            replace_existing=True,
        )
        logger.info("Script task scheduled: script=%d cron=%s", script_id, cron)
    else:
        logger.info("Script task removed/disabled: script=%d", script_id)


def sync_all_tasks() -> None:
    """启动时恢复所有已启用且带 cron 的任务"""
    for script in db.list_scripts():
        task = db.get_task(script["id"])
        if task and task["cron"] and task["enabled"]:
            sync_task(script["id"], task["cron"], True)


def get_next_run(script_id: int) -> str | None:
    job = get_scheduler().get_job(job_id(script_id))
    if job and job.next_run_time:
        return job.next_run_time.isoformat(timespec="seconds")
    return None


def run_script_now(script_id: int) -> int:
    """手动运行：预建 run 记录，后台异步执行，立即返回 run_id"""
    script = db.get_script(script_id)
    if not script:
        raise ValueError("script not found")
    run_id = db.create_run(script_id, "manual")
    asyncio.get_running_loop().create_task(
        execute_script(script_id, "manual", run_id=run_id)
    )
    return run_id


def stop_script(script_id: int) -> bool:
    """停止：终止运行中进程 + 移除定时任务 + 禁用脚本"""
    jid = job_id(script_id)
    killed = kill_command(jid)
    sched = get_scheduler()
    job = sched.get_job(jid)
    if job:
        job.remove()
    db.set_task_next_run(script_id, None)
    db.delete_task(script_id)
    db.update_script(script_id, enabled=0)
    db.set_script_status(script_id, "disabled")
    logger.info("Script stopped: %d (killed=%s)", script_id, killed)
    return killed
```

---

## 任务 6：scripts.py 路由（User + Admin API）

**Files:**
- Create: `packages/scheduler/app/routers/scripts.py`

- [ ] **Step 1: 完整实现**

```python
"""Scripts API：/scripts（User 只读）与 /admin/scripts（Admin）"""
import logging

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .. import scripts_db as db
from ..scripts_core import get_next_run, run_script_now, stop_script, sync_task
from ..config import settings

logger = logging.getLogger("scheduler.scripts")
router = APIRouter(tags=["scripts"])

VALID_TYPES = ("crawler", "ai_task", "service", "automation")
VALID_VISIBILITY = ("public", "private")


def _require_admin(x_role: str = Header("", alias="X-Role")) -> None:
    if x_role != "admin":
        raise HTTPException(403, "Admin only")


def _require_user(x_role: str = Header("", alias="X-Role")) -> None:
    if x_role not in ("user", "admin"):
        raise HTTPException(403, "Forbidden")


# ---- 请求模型 ----


class ScriptCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    type: str = "automation"
    command: str = Field(..., min_length=1)
    visibility: str = "private"
    cron: str | None = None
    enabled: bool = True


class ScriptUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    command: str | None = None
    visibility: str | None = None
    cron: str | None = None
    enabled: bool | None = None


# ---- 通用构建函数 ----


def _public_script(row: dict) -> dict:
    """User 可见字段：不含 command / owner 等信息"""
    last = db.latest_run(row["id"])
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "type": row["type"],
        "status": row["status"],
        "visibility": row["visibility"],
        "enabled": bool(row["enabled"]),
        "next_run": get_next_run(row["id"]),
        "last_run": {
            "start_time": last["start_time"],
            "end_time": last["end_time"],
            "status": last["status"],
            "duration_ms": last["duration_ms"],
        } if last else None,
    }


def _admin_script(row: dict) -> dict:
    item = _public_script(row)
    task = db.get_task(row["id"])
    item["command"] = row["command"]
    item["cron"] = task["cron"] if task else None
    item["owner_id"] = row["owner_id"]
    item["created_at"] = row["created_at"]
    return item


# ---- User 接口（只读）----


@router.get("/scripts")
async def list_public_scripts(_: None = None) -> dict:
    rows = [r for r in db.list_scripts(public_only=True)]
    return {"scripts": [_public_script(r) for r in rows]}


@router.get("/scripts/{script_id}/status")
async def script_status(script_id: int, _: None = None) -> dict:
    row = db.get_script(script_id)
    if not row or row["visibility"] != "public" or not row["enabled"]:
        raise HTTPException(404, "Script not found")
    last = db.latest_run(script_id)
    return {
        "id": row["id"],
        "status": row["status"],
        "enabled": bool(row["enabled"]),
        "next_run": get_next_run(script_id),
        "last_run_status": last["status"] if last else None,
        "last_run_time": last["start_time"] if last else None,
    }


@router.get("/scripts/{script_id}/summary")
async def script_summary(script_id: int, _: None = None) -> dict:
    row = db.get_script(script_id)
    if not row or row["visibility"] != "public" or not row["enabled"]:
        raise HTTPException(404, "Script not found")
    runs = db.list_runs(script_id, limit=20)
    total = len(runs)
    success = sum(1 for r in runs if r["status"] == "success")
    failed = sum(1 for r in runs if r["status"] == "failed")
    durations = [r["duration_ms"] for r in runs if r.get("duration_ms")]
    avg = int(sum(durations) / len(durations)) if durations else None
    return {
        "script_id": script_id,
        "total_runs": total,
        "success": success,
        "failed": failed,
        "avg_duration_ms": avg,
        "recent_runs": runs[:10],
    }


# ---- Admin 接口 ----


@router.get("/admin/scripts")
async def admin_list_scripts(_: None = _require_admin()) -> dict:
    return {"scripts": [_admin_script(r) for r in db.list_scripts()]}


@router.post("/admin/scripts", status_code=201)
async def admin_create_script(req: ScriptCreate, _: None = _require_admin()) -> dict:
    if req.type not in VALID_TYPES:
        raise HTTPException(400, f"type must be one of {VALID_TYPES}")
    if req.visibility not in VALID_VISIBILITY:
        raise HTTPException(400, "visibility must be 'public' or 'private'")
    if req.cron:
        from apscheduler.triggers.cron import CronTrigger
        try:
            CronTrigger.from_crontab(req.cron, timezone=settings.TIMEZONE)
        except Exception:
            raise HTTPException(400, "Invalid cron expression")

    script_id = db.create_script(
        req.name, req.description, req.type, req.command, req.visibility, 0
    )
    db.update_script(script_id, enabled=1 if req.enabled else 0)
    sync_task(script_id, req.cron, req.enabled)
    return _admin_script(db.get_script(script_id))


@router.put("/admin/scripts/{script_id}")
async def admin_update_script(script_id: int, req: ScriptUpdate,
                              _: None = _require_admin()) -> dict:
    row = db.get_script(script_id)
    if not row:
        raise HTTPException(404, "Script not found")
    updates: dict = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.description is not None:
        updates["description"] = req.description
    if req.type is not None:
        if req.type not in VALID_TYPES:
            raise HTTPException(400, f"type must be one of {VALID_TYPES}")
        updates["type"] = req.type
    if req.command is not None:
        updates["command"] = req.command
    if req.visibility is not None:
        if req.visibility not in VALID_VISIBILITY:
            raise HTTPException(400, "visibility must be 'public' or 'private'")
        updates["visibility"] = req.visibility
    if req.enabled is not None:
        updates["enabled"] = 1 if req.enabled else 0
    db.update_script(script_id, **updates)

    # 任务同步：cron 字段显式更新时才动调度
    if req.cron is not None or req.enabled is not None:
        task = db.get_task(script_id)
        cron = req.cron if req.cron is not None else (task["cron"] if task else None)
        enabled = req.enabled if req.enabled is not None else bool(row["enabled"])
        sync_task(script_id, cron, enabled)

    return _admin_script(db.get_script(script_id))


@router.delete("/admin/scripts/{script_id}")
async def admin_delete_script(script_id: int, _: None = _require_admin()) -> dict:
    if not db.delete_script(script_id):
        raise HTTPException(404, "Script not found")
    # 移除 APScheduler job
    from ..scripts_core import job_id
    from ..core import get_scheduler
    job = get_scheduler().get_job(job_id(script_id))
    if job:
        job.remove()
    return {"deleted": script_id}


@router.post("/admin/scripts/{script_id}/run")
async def admin_run_script(script_id: int, _: None = _require_admin()) -> dict:
    row = db.get_script(script_id)
    if not row:
        raise HTTPException(404, "Script not found")
    try:
        run_id = run_script_now(script_id)
    except ValueError:
        raise HTTPException(404, "Script not found")
    return {"run_id": run_id, "status": "running"}


@router.post("/admin/scripts/{script_id}/stop")
async def admin_stop_script(script_id: int, _: None = _require_admin()) -> dict:
    if not db.get_script(script_id):
        raise HTTPException(404, "Script not found")
    killed = stop_script(script_id)
    return {"stopped": script_id, "killed": killed}


@router.get("/admin/scripts/{script_id}/logs")
async def admin_script_logs(script_id: int, date: str | None = None,
                            _: None = _require_admin()) -> dict:
    row = db.get_script(script_id)
    if not row:
        raise HTTPException(404, "Script not found")
    from ..scripts_runner import read_log_tail, _log_path
    from datetime import datetime, timezone
    dt = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now(timezone.utc).astimezone()
    path = _log_path(row["name"], dt)
    lines = []
    try:
        import os
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()[-settings.LOG_TAIL_LINES:]
    except Exception as exc:
        logger.warning("read log failed: %s", exc)
    last = db.latest_run(script_id)
    return {
        "date": dt.strftime("%Y-%m-%d"),
        "path": f"logs/scripts/{row['name']}/{dt.strftime('%Y-%m-%d')}.log",
        "lines": lines,
        "latest_run": last,
    }


@router.post("/admin/scripts/{script_id}/analyze-error")
async def admin_analyze_error(script_id: int, _: None = _require_admin()) -> dict:
    row = db.get_script(script_id)
    if not row:
        raise HTTPException(404, "Script not found")
    error = db.latest_failed_error(script_id)
    if not error:
        raise HTTPException(400, "No failed run error available to analyze")

    prompt = (
        f"你是服务器自动化脚本运维专家。以下是脚本「{row['name']}」最近一次执行的错误信息：\n\n"
        f"{error[:3000]}\n\n"
        "请分析可能的原因（可考虑：网站结构变化、网络异常、请求频率限制、配置错误、代码问题等），"
        "并给出可操作的解决建议。请用简洁的中文，分「可能原因」和「解决建议」两部分输出，"
        "不要输出多余内容。"
    )
    try:
        async with httpx.AsyncClient(
            base_url=settings.AI_SERVICE_URL, timeout=settings.AI_ANALYZE_TIMEOUT
        ) as client:
            resp = await client.post(
                "/api/chat",
                json={"message": prompt, "use_rag": True, "use_memory": False},
                headers={
                    "X-User-Id": "0",
                    "X-Username": "admin",
                    "X-Role": "admin",
                },
            )
            data = resp.json()
    except Exception as exc:
        logger.warning("AI analyze error: %s", exc)
        raise HTTPException(502, f"AI service unavailable: {str(exc)[:150]}")
    if not data.get("success"):
        raise HTTPException(502, data.get("error", "AI analysis failed"))
    return {"script_id": script_id, "analysis": data.get("answer", "")}
```

> 注：`_require_admin()` 在 `Depends`/参数默认值处调用，FastAPI 将其识别为依赖（无参数函数返回 None）。`_require_user` 当前未启用（User 接口的可见性过滤在函数内实现，不依赖 header），保留供未来扩展。

---

## 任务 7：scheduler 入口接入

**Files:**
- Modify: `packages/scheduler/app/main.py`

- [ ] **Step 1: 引入 scripts 模块**

```python
from .config import settings
from .core import init_scheduler
from .routers import jobs, scripts
from .scripts_core import sync_all_tasks
from .scripts_db import init_db
```

- [ ] **Step 2: lifespan 中 init_db + sync_all_tasks**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sched = init_scheduler()
    sync_all_tasks()
    logger.info("Scheduler started: %d jobs", len(sched.get_jobs()))
    yield
    sched.shutdown(wait=False)
    logger.info("Scheduler stopped")
```

- [ ] **Step 3: include scripts 路由**

```python
app.include_router(jobs.router)
app.include_router(scripts.router)
```

- [ ] **Step 4: 验证本地语法**

Run: `cd packages/scheduler && python -m py_compile app/scripts_db.py app/scripts_runner.py app/scripts_core.py app/routers/scripts.py app/main.py`
Expected: 无输出（成功）

---

## 任务 8：Gateway 代理路由 + 权限修复

**Files:**
- Create: `packages/gateway/app/routers/scripts.py`
- Modify: `packages/gateway/app/main.py`
- Modify: `packages/gateway/app/routers/scheduler.py`

- [ ] **Step 1: 新建 gateway scripts 代理路由**

```python
"""Scripts 代理路由：/api/scripts/*（user）与 /api/admin/scripts/*（admin）→ scheduler"""
import logging

import httpx
from fastapi import APIRouter, Depends, Request, Response

from ..auth import require_admin, require_user
from ..config import settings

logger = logging.getLogger("gateway.scripts")
router = APIRouter(prefix="/api", tags=["scripts"])

_client = httpx.AsyncClient(
    base_url=settings.SCHEDULER_SERVICE_URL,
    timeout=httpx.Timeout(settings.REQUEST_TIMEOUT),
)


async def _proxy(request: Request, path: str, user: dict) -> Response:
    url = f"/{path}"
    params = dict(request.query_params)
    body = await request.body() if request.method in ("POST", "PUT") else None
    headers = {
        "X-User-Id": str(user["uid"]),
        "X-Username": user["sub"],
        "X-Role": user["role"],
    }
    if body:
        headers["content-type"] = request.headers.get("content-type", "")
    resp = await _client.request(
        request.method, url, params=params, content=body, headers=headers
    )
    logger.info("Scripts proxy %s %s -> %d (user=%s)", request.method, url,
                resp.status_code, user["sub"])
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


@router.api_route("/scripts/{path:path}", methods=["GET"])
async def user_scripts(path: str, request: Request,
                       user: dict = Depends(require_user)) -> Response:
    """User 只读脚本接口"""
    return await _proxy(request, path, user)


@router.api_route("/admin/scripts/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def admin_scripts(path: str, request: Request,
                        user: dict = Depends(require_admin)) -> Response:
    """Admin 管理接口（非 admin 在网关返回 403）"""
    return await _proxy(request, path, user)
```

- [ ] **Step 2: gateway main.py 引入**

```python
from .routers import ai, auth, scheduler, scripts, status
...
app.include_router(scripts.router)
```

- [ ] **Step 3: 修复 scheduler 代理写权限**

将 `packages/gateway/app/routers/scheduler.py` 的依赖改为方法感知：

```python
from fastapi import APIRouter, Depends, HTTPException, Request, Response
...
@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
)
async def proxy_scheduler(path: str, request: Request, user: dict = Depends(require_user)) -> Response:
    """转发请求到 scheduler 服务；写操作仅限 admin"""
    if request.method in ("POST", "PUT", "DELETE") and user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    ...
```

- [ ] **Step 4: 验证语法**

Run: `cd packages/gateway && python -m py_compile app/routers/scripts.py app/main.py app/routers/scheduler.py`
Expected: 无输出（成功）

---

## 任务 9：docker-compose 卷

**Files:**
- Modify: `docker-compose.yml`（根目录）

- [ ] **Step 1: scheduler 服务新增脚本目录卷**

```yaml
  scheduler:
    ...
    volumes:
      - /opt/snhgn/data/sqlite:/data/sqlite
      - /opt/snhgn/logs/scheduler:/app/logs
      - /opt/snhgn/scripts:/data/scripts
```

说明：脚本日志落在 `/app/logs/scripts/<name>/YYYY-MM-DD.log`，宿主对应 `/opt/snhgn/logs/scheduler/scripts/<name>/`。

---

## 任务 10：前端类型定义

**Files:**
- Modify: `d:\project\snhgn.me\src\data\scripts.ts`

- [ ] **Step 1: 用真实类型替换 mock**

```ts
export type ScriptType = 'crawler' | 'ai_task' | 'service' | 'automation'
export type ScriptStatus = 'running' | 'waiting' | 'failed' | 'disabled'
export type ScriptVisibility = 'public' | 'private'

export interface ScriptLastRun {
  start_time: string
  end_time: string | null
  status: string
  duration_ms: number | null
}

export interface ScriptListItem {
  id: number
  name: string
  description: string
  type: ScriptType
  status: ScriptStatus
  visibility: ScriptVisibility
  enabled: boolean
  /** Admin 字段 */
  command?: string
  cron?: string | null
  owner_id?: number
  created_at?: string
  next_run?: string | null
  last_run?: ScriptLastRun | null
}

export interface ScriptRunRecord {
  id: number
  script_id: number
  trigger: string
  start_time: string
  end_time: string | null
  status: 'running' | 'success' | 'failed'
  duration_ms: number | null
}

export interface ScriptSummary {
  script_id: number
  total_runs: number
  success: number
  failed: number
  avg_duration_ms: number | null
  recent_runs: ScriptRunRecord[]
}

export interface ScriptLogResult {
  date: string
  path: string
  lines: string[]
  latest_run: {
    id: number
    status: string
    start_time: string
    end_time: string | null
    duration_ms: number | null
    output?: string
    error?: string
  } | null
}

export const TYPE_LABELS: Record<ScriptType, string> = {
  crawler: 'Crawler',
  ai_task: 'AI Task',
  service: 'Service',
  automation: 'Automation',
}

export const STATUS_LABELS: Record<ScriptStatus, string> = {
  running: 'Running',
  waiting: 'Waiting',
  failed: 'Failed',
  disabled: 'Disabled',
}
```

---

## 任务 11：前端脚本 API 封装

**Files:**
- Create: `d:\project\snhgn.me\src\api\scripts.ts`

- [ ] **Step 1: 完整实现**

```ts
import { api } from '@/api'
import type { ScriptListItem, ScriptLogResult, ScriptSummary } from '@/data/scripts'

/** User：公开脚本列表 */
export const fetchScripts = () => api.get<{ scripts: ScriptListItem[] }>('/api/scripts')

/** User：脚本状态 */
export const fetchScriptStatus = (id: number) =>
  api.get<{ id: number; status: string; enabled: boolean; next_run: string | null; last_run_status: string | null; last_run_time: string | null }>(
    `/api/scripts/${id}/status`,
  )

/** User：运行摘要 */
export const fetchScriptSummary = (id: number) =>
  api.get<ScriptSummary>(`/api/scripts/${id}/summary`)

/** Admin：完整列表 */
export const fetchAdminScripts = () => api.get<{ scripts: ScriptListItem[] }>('/api/admin/scripts')

/** Admin：创建 */
export const createScript = (body: {
  name: string; description: string; type: string; command: string;
  visibility: string; cron?: string | null; enabled: boolean
}) => api.post<ScriptListItem>('/api/admin/scripts', body)

/** Admin：更新 */
export const updateScript = (id: number, body: Partial<ScriptListItem>) =>
  api.put<ScriptListItem>(`/api/admin/scripts/${id}`, body)

/** Admin：删除 */
export const deleteScript = (id: number) => api.delete<{ deleted: number }>(`/api/admin/scripts/${id}`)

/** Admin：手动运行 */
export const runScript = (id: number) => api.post<{ run_id: number; status: string }>(`/api/admin/scripts/${id}/run`)

/** Admin：停止 */
export const stopScript = (id: number) => api.post<{ stopped: number; killed: boolean }>(`/api/admin/scripts/${id}/stop`)

/** Admin：日志 */
export const fetchScriptLogs = (id: number, date?: string) =>
  api.get<ScriptLogResult>(`/api/admin/scripts/${id}/logs${date ? `?date=${date}` : ''}`)

/** Admin：AI 错误分析 */
export const analyzeScriptError = (id: number) =>
  api.post<{ script_id: number; analysis: string }>(`/api/admin/scripts/${id}/analyze-error`)
```

---

## 任务 12：前端组件

**Files:**
- Create: `d:\project\snhgn.me\src\components\Scripts\ScriptStatus.vue`
- Create: `d:\project\snhgn.me\src\components\Scripts\ScriptCard.vue`

- [ ] **Step 1: ScriptStatus.vue（状态徽章）**

```vue
<script setup lang="ts">
import type { ScriptStatus } from '@/data/scripts'

defineProps<{ status: ScriptStatus }>()

const dot: Record<ScriptStatus, string> = {
  running: 'bg-emerald-500',
  waiting: 'bg-sky-500',
  failed: 'bg-red-500',
  disabled: 'bg-neutral-300',
}
const text: Record<ScriptStatus, string> = {
  running: 'text-emerald-600 bg-emerald-50',
  waiting: 'text-sky-600 bg-sky-50',
  failed: 'text-red-600 bg-red-50',
  disabled: 'text-neutral-500 bg-neutral-100',
}
const label: Record<ScriptStatus, string> = {
  running: 'Running',
  waiting: 'Waiting',
  failed: 'Failed',
  disabled: 'Disabled',
}
</script>

<template>
  <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium" :class="text[status]">
    <span class="h-1.5 w-1.5 rounded-full" :class="dot[status]" />
    {{ label[status] }}
  </span>
</template>
```

- [ ] **Step 2: ScriptCard.vue（User 展示卡）**

```vue
<script setup lang="ts">
import type { ScriptListItem } from '@/data/scripts'
import { TYPE_LABELS } from '@/data/scripts'
import ScriptStatus from './ScriptStatus.vue'

defineProps<{ script: ScriptListItem }>()

function fmt(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-')
}
</script>

<template>
  <div class="rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
    <div class="flex items-start justify-between gap-3">
      <h3 class="text-base font-semibold">{{ script.name }}</h3>
      <ScriptStatus :status="script.status" />
    </div>
    <p class="mt-2 text-sm leading-relaxed text-neutral-500">{{ script.description || '—' }}</p>

    <div class="mt-5 grid grid-cols-3 gap-3 border-t border-neutral-100 pt-4 font-mono text-xs">
      <div>
        <p class="text-neutral-400">Type</p>
        <p class="mt-1 font-medium text-neutral-700">{{ TYPE_LABELS[script.type] }}</p>
      </div>
      <div>
        <p class="text-neutral-400">Last run</p>
        <p class="mt-1 font-medium text-neutral-700">{{ fmt(script.last_run?.start_time) }}</p>
      </div>
      <div>
        <p class="text-neutral-400">Next run</p>
        <p class="mt-1 font-medium text-neutral-700">{{ fmt(script.next_run) }}</p>
      </div>
    </div>
  </div>
</template>
```

---

## 任务 13：前端管理组件

**Files:**
- Create: `d:\project\snhgn.me\src\components\Scripts\RunHistory.vue`
- Create: `d:\project\snhgn.me\src\components\Scripts\LogViewer.vue`
- Create: `d:\project\snhgn.me\src\components\Scripts\AdminScriptForm.vue`

- [ ] **Step 1: RunHistory.vue（运行历史抽屉）**

```vue
<script setup lang="ts">
import type { ScriptRunRecord } from '@/data/scripts'

defineProps<{
  runs: ScriptRunRecord[]
  loading?: boolean
}>()
defineEmits<{ close: [] }>()

function fmt(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-') : '—'
}
</script>

<template>
  <div class="fixed inset-0 z-40 bg-black/30" @click.self="$emit('close')">
    <div class="absolute right-0 top-0 flex h-full w-full max-w-md flex-col bg-white shadow-xl">
      <div class="flex items-center justify-between border-b border-neutral-200 px-6 py-4">
        <h2 class="text-lg font-semibold">Run History</h2>
        <button class="rounded-md px-2 py-1 text-neutral-500 hover:bg-neutral-100" @click="$emit('close')">✕</button>
      </div>
      <div class="flex-1 overflow-y-auto px-6 py-4">
        <p v-if="loading" class="text-sm text-neutral-400">Loading…</p>
        <p v-else-if="!runs.length" class="text-sm text-neutral-400">No runs yet.</p>
        <table v-else class="w-full text-left text-sm">
          <thead class="border-b border-neutral-200 text-xs text-neutral-400">
            <tr>
              <th class="py-2 font-medium">Time</th>
              <th class="py-2 font-medium">Trigger</th>
              <th class="py-2 font-medium">Status</th>
              <th class="py-2 font-medium">Duration</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in runs" :key="r.id" class="border-b border-neutral-100">
              <td class="py-2 font-mono text-xs">{{ fmt(r.start_time) }}</td>
              <td class="py-2 text-xs">{{ r.trigger }}</td>
              <td class="py-2">
                <span class="text-xs font-medium" :class="{
                  'text-emerald-600': r.status === 'success',
                  'text-red-600': r.status === 'failed',
                  'text-sky-600': r.status === 'running',
                }">{{ r.status }}</span>
              </td>
              <td class="py-2 font-mono text-xs">{{ r.duration_ms != null ? `${(r.duration_ms / 1000).toFixed(1)}s` : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: LogViewer.vue（日志 + AI 分析）**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import type { ScriptLogResult } from '@/data/scripts'
import { analyzeScriptError } from '@/api/scripts'

const props = defineProps<{ scriptId: number }>()
defineEmits<{ close: [] }>()

const log = ref<ScriptLogResult | null>(null)
const loading = ref(false)
const analyzing = ref(false)
const analysis = ref('')

async function load(date?: string) {
  loading.value = true
  try {
    const { fetchScriptLogs } = await import('@/api/scripts')
    log.value = await fetchScriptLogs(props.scriptId, date)
  } finally {
    loading.value = false
  }
}

async function analyze() {
  analyzing.value = true
  analysis.value = ''
  try {
    const res = await analyzeScriptError(props.scriptId)
    analysis.value = res.analysis
  } catch (e: any) {
    analysis.value = `分析失败：${e.message}`
  } finally {
    analyzing.value = false
  }
}

load()
</script>

<template>
  <div class="fixed inset-0 z-40 bg-black/30" @click.self="$emit('close')">
    <div class="absolute right-0 top-0 flex h-full w-full max-w-2xl flex-col bg-white shadow-xl">
      <div class="flex items-center justify-between border-b border-neutral-200 px-6 py-4">
        <h2 class="text-lg font-semibold">Script Logs</h2>
        <button class="rounded-md px-2 py-1 text-neutral-500 hover:bg-neutral-100" @click="$emit('close')">✕</button>
      </div>

      <div class="flex items-center gap-3 border-b border-neutral-100 px-6 py-3">
        <button
          class="rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-700"
          :disabled="analyzing"
          @click="analyze"
        >
          {{ analyzing ? '分析中…' : 'AI 分析错误' }}
        </button>
        <span v-if="log" class="font-mono text-xs text-neutral-400">{{ log.path }}</span>
      </div>

      <div v-if="analysis" class="border-b border-neutral-100 bg-amber-50/60 px-6 py-4">
        <p class="text-sm font-semibold text-neutral-700">AI 分析</p>
        <pre class="mt-2 whitespace-pre-wrap font-sans text-sm leading-relaxed text-neutral-700">{{ analysis }}</pre>
      </div>

      <div class="flex-1 overflow-y-auto bg-neutral-950 px-6 py-4">
        <p v-if="loading" class="font-mono text-sm text-neutral-400">Loading…</p>
        <p v-else-if="!log?.lines.length" class="font-mono text-sm text-neutral-400">No log entries for today.</p>
        <div v-else class="font-mono text-xs leading-6 text-neutral-300">
          <p v-for="(line, i) in log.lines" :key="i">{{ line }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: AdminScriptForm.vue（新增/编辑表单）**

```vue
<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { ScriptListItem, ScriptType, ScriptVisibility } from '@/data/scripts'

const props = defineProps<{
  script?: ScriptListItem | null
}>()
const emit = defineEmits<{ close: []; submit: [payload: Record<string, any>] }>()

const form = reactive({
  name: '',
  description: '',
  type: 'automation' as ScriptType,
  command: '',
  visibility: 'private' as ScriptVisibility,
  cron: '',
  enabled: true,
})

watch(
  () => props.script,
  (s) => {
    form.name = s?.name ?? ''
    form.description = s?.description ?? ''
    form.type = (s?.type as ScriptType) ?? 'automation'
    form.command = s?.command ?? ''
    form.visibility = (s?.visibility as ScriptVisibility) ?? 'private'
    form.cron = s?.cron ?? ''
    form.enabled = s?.enabled ?? true
  },
  { immediate: true },
)

function submit() {
  emit('submit', {
    ...form,
    cron: form.cron.trim() || null,
  })
}
</script>

<template>
  <div class="fixed inset-0 z-40 flex items-center justify-center bg-black/30 p-4" @click.self="$emit('close')">
    <div class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
      <h2 class="text-lg font-semibold">{{ script ? 'Edit Script' : 'New Script' }}</h2>

      <div class="mt-5 space-y-4">
        <div>
          <label class="text-xs font-medium text-neutral-500">Name *</label>
          <input v-model="form.name" class="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm focus:border-neutral-400 focus:outline-none" />
        </div>
        <div>
          <label class="text-xs font-medium text-neutral-500">Description</label>
          <textarea v-model="form.description" rows="2" class="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm focus:border-neutral-400 focus:outline-none" />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-xs font-medium text-neutral-500">Type</label>
            <select v-model="form.type" class="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm">
              <option value="crawler">Crawler</option>
              <option value="ai_task">AI Task</option>
              <option value="service">Service</option>
              <option value="automation">Automation</option>
            </select>
          </div>
          <div>
            <label class="text-xs font-medium text-neutral-500">Visibility</label>
            <select v-model="form.visibility" class="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm">
              <option value="private">Private</option>
              <option value="public">Public</option>
            </select>
          </div>
        </div>
        <div>
          <label class="text-xs font-medium text-neutral-500">Command *</label>
          <input v-model="form.command" placeholder="python /data/scripts/notice-monitor/main.py"
            class="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 font-mono text-xs focus:border-neutral-400 focus:outline-none" />
        </div>
        <div>
          <label class="text-xs font-medium text-neutral-500">Cron（留空则不定时）</label>
          <input v-model="form.cron" placeholder="0 9 * * *"
            class="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 font-mono text-xs focus:border-neutral-400 focus:outline-none" />
        </div>
        <label class="flex items-center gap-2 text-sm text-neutral-600">
          <input v-model="form.enabled" type="checkbox" class="h-4 w-4 rounded border-neutral-300" />
          Enabled
        </label>
      </div>

      <div class="mt-6 flex justify-end gap-2">
        <button class="rounded-md px-4 py-2 text-sm text-neutral-500 hover:bg-neutral-100" @click="$emit('close')">Cancel</button>
        <button class="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700" @click="submit">Save</button>
      </div>
    </div>
  </div>
</template>
```

---

## 任务 14：ScriptsView.vue（User 展示页）

**Files:**
- Modify: `d:\project\snhgn.me\src\views\ScriptsView.vue`

- [ ] **Step 1: 完整重写**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchScripts } from '@/api/scripts'
import type { ScriptListItem } from '@/data/scripts'
import ScriptCard from '@/components/Scripts/ScriptCard.vue'

const scripts = ref<ScriptListItem[]>([])
const loading = ref(true)
const error = ref('')

const counts = {
  running: () => scripts.value.filter((s) => s.status === 'running').length,
  waiting: () => scripts.value.filter((s) => s.status === 'waiting').length,
  failed: () => scripts.value.filter((s) => s.status === 'failed').length,
}

onMounted(async () => {
  try {
    const res = await fetchScripts()
    scripts.value = res.scripts
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="py-12 md:py-16">
    <header class="mb-10">
      <h1 class="text-3xl font-bold tracking-tight md:text-4xl">Scripts</h1>
      <p class="mt-2 font-mono text-sm text-neutral-400">Server automation overview</p>
    </header>

    <!-- 状态概览 -->
    <div class="mb-8 grid grid-cols-3 gap-4">
      <div class="rounded-xl border border-emerald-200 bg-white px-5 py-4">
        <p class="font-mono text-2xl font-bold text-emerald-600">{{ counts.running() }}</p>
        <p class="mt-1 text-xs text-neutral-500">Running</p>
      </div>
      <div class="rounded-xl border border-sky-200 bg-white px-5 py-4">
        <p class="font-mono text-2xl font-bold text-sky-600">{{ counts.waiting() }}</p>
        <p class="mt-1 text-xs text-neutral-500">Waiting</p>
      </div>
      <div class="rounded-xl border border-red-200 bg-white px-5 py-4">
        <p class="font-mono text-2xl font-bold text-red-600">{{ counts.failed() }}</p>
        <p class="mt-1 text-xs text-neutral-500">Failed</p>
      </div>
    </div>

    <p v-if="loading" class="text-sm text-neutral-400">Loading…</p>
    <p v-else-if="error" class="text-sm text-red-500">{{ error }}</p>
    <p v-else-if="!scripts.length" class="text-sm text-neutral-400">No public scripts yet.</p>

    <div v-else class="grid gap-4 md:grid-cols-2">
      <ScriptCard v-for="s in scripts" :key="s.id" :script="s" />
    </div>
  </div>
</template>
```

---

## 任务 15：AdminScriptsView.vue（管理页）

**Files:**
- Create: `d:\project\snhgn.me\src\views\AdminScriptsView.vue`

- [ ] **Step 1: 完整实现**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  createScript, deleteScript, fetchAdminScripts, fetchScriptSummary, runScript, stopScript, updateScript,
} from '@/api/scripts'
import type { ScriptListItem, ScriptRunRecord } from '@/data/scripts'
import { TYPE_LABELS } from '@/data/scripts'
import ScriptStatus from '@/components/Scripts/ScriptStatus.vue'
import RunHistory from '@/components/Scripts/RunHistory.vue'
import LogViewer from '@/components/Scripts/LogViewer.vue'
import AdminScriptForm from '@/components/Scripts/AdminScriptForm.vue'

const scripts = ref<ScriptListItem[]>([])
const loading = ref(true)
const error = ref('')

const showForm = ref(false)
const editing = ref<ScriptListItem | null>(null)
const historyScript = ref<ScriptListItem | null>(null)
const historyRuns = ref<ScriptRunRecord[]>([])
const historyLoading = ref(false)
const logScriptId = ref<number | null>(null)
const busyId = ref<number | null>(null)

async function load() {
  loading.value = true
  try {
    const res = await fetchAdminScripts()
    scripts.value = res.scripts
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

function openCreate() {
  editing.value = null
  showForm.value = true
}

function openEdit(s: ScriptListItem) {
  editing.value = s
  showForm.value = true
}

async function onSubmit(payload: Record<string, any>) {
  try {
    if (editing.value) {
      await updateScript(editing.value.id, payload)
    } else {
      await createScript(payload as any)
    }
    showForm.value = false
    await load()
  } catch (e: any) {
    alert(e.message)
  }
}

async function onRun(s: ScriptListItem) {
  busyId.value = s.id
  try {
    await runScript(s.id)
    setTimeout(load, 1500)
  } catch (e: any) {
    alert(e.message)
  } finally {
    busyId.value = null
  }
}

async function onStop(s: ScriptListItem) {
  if (!confirm(`Stop script "${s.name}"?`)) return
  try {
    await stopScript(s.id)
    await load()
  } catch (e: any) {
    alert(e.message)
  }
}

async function onDelete(s: ScriptListItem) {
  if (!confirm(`Delete script "${s.name}"? This cannot be undone.`)) return
  try {
    await deleteScript(s.id)
    await load()
  } catch (e: any) {
    alert(e.message)
  }
}

async function openHistory(s: ScriptListItem) {
  historyScript.value = s
  historyRuns.value = []
  historyLoading.value = true
  try {
    const res = await fetchScriptSummary(s.id)
    historyRuns.value = res.recent_runs
  } catch (e: any) {
    alert(e.message)
  } finally {
    historyLoading.value = false
  }
}

function fmt(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-') : '—'
}
</script>

<template>
  <div class="py-12 md:py-16">
    <header class="mb-10 flex items-end justify-between">
      <div>
        <h1 class="text-3xl font-bold tracking-tight md:text-4xl">Script Management</h1>
        <p class="mt-2 font-mono text-sm text-neutral-400">Admin control center</p>
      </div>
      <button class="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700" @click="openCreate">
        + New Script
      </button>
    </header>

    <p v-if="loading" class="text-sm text-neutral-400">Loading…</p>
    <p v-else-if="error" class="text-sm text-red-500">{{ error }}</p>
    <p v-else-if="!scripts.length" class="text-sm text-neutral-400">No scripts yet. Create one.</p>

    <div v-else class="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
      <table class="w-full text-left text-sm">
        <thead class="border-b border-neutral-200 bg-neutral-50 text-xs text-neutral-400">
          <tr>
            <th class="px-5 py-3 font-medium">Name</th>
            <th class="px-5 py-3 font-medium">Type</th>
            <th class="px-5 py-3 font-medium">Status</th>
            <th class="px-5 py-3 font-medium">Last run</th>
            <th class="px-5 py-3 font-medium">Next run</th>
            <th class="px-5 py-3 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in scripts" :key="s.id" class="border-b border-neutral-100 last:border-0 hover:bg-neutral-50/60">
            <td class="px-5 py-4">
              <p class="font-medium">{{ s.name }}</p>
              <p class="mt-0.5 text-xs text-neutral-400">{{ s.description || '—' }}</p>
            </td>
            <td class="px-5 py-4 text-xs text-neutral-500">{{ TYPE_LABELS[s.type] }}</td>
            <td class="px-5 py-4"><ScriptStatus :status="s.status" /></td>
            <td class="px-5 py-4 font-mono text-xs text-neutral-500">{{ fmt(s.last_run?.start_time) }}</td>
            <td class="px-5 py-4 font-mono text-xs text-neutral-500">{{ fmt(s.next_run) }}</td>
            <td class="px-5 py-4">
              <div class="flex items-center justify-end gap-1 text-xs">
                <button class="rounded-md px-2 py-1 text-neutral-600 hover:bg-neutral-100" :disabled="busyId === s.id" @click="onRun(s)">Run</button>
                <button class="rounded-md px-2 py-1 text-neutral-600 hover:bg-neutral-100" @click="onStop(s)">Stop</button>
                <button class="rounded-md px-2 py-1 text-neutral-600 hover:bg-neutral-100" @click="openEdit(s)">Edit</button>
                <button class="rounded-md px-2 py-1 text-red-500 hover:bg-red-50" @click="onDelete(s)">Delete</button>
                <button class="rounded-md px-2 py-1 text-neutral-600 hover:bg-neutral-100" @click="openHistory(s)">History</button>
                <button class="rounded-md px-2 py-1 text-neutral-600 hover:bg-neutral-100" @click="logScriptId = s.id">Logs</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增/编辑弹窗 -->
    <AdminScriptForm v-if="showForm" :script="editing" @close="showForm = false" @submit="onSubmit" />

    <!-- 运行历史抽屉 -->
    <RunHistory
      v-if="historyScript"
      :runs="historyRuns"
      :loading="historyLoading"
      @close="historyScript = null"
    />

    <!-- 日志抽屉 -->
    <LogViewer v-if="logScriptId !== null" :script-id="logScriptId" @close="logScriptId = null" />
  </div>
</template>
```

---

## 任务 16：路由 + 导航

**Files:**
- Modify: `d:\project\snhgn.me\src\router\index.ts`
- Modify: `d:\project\snhgn.me\src\components\Navbar.vue`

- [ ] **Step 1: 新增 `/admin/scripts` 路由**

在 `src/router/index.ts` 的 Admin 页面区块（`/server` 之后）添加：

```ts
    {
      path: '/admin/scripts',
      name: 'admin-scripts',
      component: () => import('@/views/AdminScriptsView.vue'),
      meta: { requiresAuth: true, role: 'admin' },
    },
```

- [ ] **Step 2: Navbar 增加管理入口**

在 `src/components/Navbar.vue` 的 Admin 分支（`/server` 之后）添加：

```ts
      { to: '/admin/scripts', label: 'Script Mgmt' },
```

---

## 任务 17：验证与部署

- [ ] **Step 1: 后端构建**

Run: `docker compose build scheduler gateway`
Expected: 构建成功（无新增依赖）

- [ ] **Step 2: 启动 + 全链路验证**

```bash
mkdir -p /opt/snhgn/scripts
docker compose up -d scheduler gateway
# 管理员登录
curl -s -X POST http://127.0.0.1:8001/api/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```

用返回 token 验证：
- `POST /api/admin/scripts` 创建测试脚本（command=`echo hello scripts`）→ 201
- `POST /api/admin/scripts/{id}/run` → 返回 run_id；稍后 `GET /api/admin/scripts` 显示 status、last_run、日志文件生成
- `GET /api/admin/scripts/{id}/logs` → 包含 output 行
- 普通用户 token：`GET /api/scripts` 只返回 public 脚本；`GET /api/admin/scripts` → **403**
- `GET /api/admin/scripts/{id}/summary` → 运行摘要
- 修复验证：user token `POST /api/scheduler/jobs` → **403**

- [ ] **Step 3: 前端构建**

Run: `cd d:\project\snhgn.me && npm run build`
Expected: `vue-tsc --noEmit` 无类型错误，vite build 成功

- [ ] **Step 4: 部署前端 + 浏览器验证**

将 `dist/` 上传到 `/opt/website/web/`，浏览器验证：
- `/scripts`（user）：状态概览 + 脚本卡片，无执行按钮
- `/admin/scripts`（admin）：New/Run/Stop/Edit/Delete/History/Logs + AI 分析错误

---

## 自查（Spec 覆盖核对）

- ✅ 权限：User 只读（网关 `require_user` + 服务端 public 过滤）、Admin 全量（网关 `require_admin` + 服务端 `X-Role` 校验）、Guest 无路由
- ✅ 页面：`/scripts` 状态概览 + 卡片；`/admin/scripts` 管理后台
- ✅ 数据库：scripts / script_runs / tasks 三表
- ✅ 执行架构：Gateway → Scheduler(scripts 模块) → APScheduler Worker → 命令执行
- ✅ API：User 3 个 + Admin 9 个，全部 JWT + role
- ✅ 日志：`logs/scripts/<name>/YYYY-MM-DD.log` 每日分片，含开始/结束/输出/错误
- ✅ AI 错误分析：复用 ai-service `/api/chat`（RAG 辅助）
- ✅ Scheduler 复用：不改 core.py 核心调度，仅加模块 + executor 进程注册表（小增量）
- ✅ 性能：零新增容器、复用 SQLite、异步执行、日志分片
- ✅ 安全：不暴露 command/owner/错误详情给 User；AI 分析不注入 API Key

## 后续扩展（不在本次范围）

1. 脚本文件经平台上传/编辑（文件管理器 + 语法校验）
2. 手动运行的可选超时/参数传参
3. 运行历史分页 + 按日期读取日志
4. 通知监控容器化后自动注册为 Scripts 种子数据
5. 脚本间依赖编排（简单 DAG）