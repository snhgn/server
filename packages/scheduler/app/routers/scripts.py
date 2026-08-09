"""Scripts API：/scripts（User 只读）与 /admin/scripts（Admin）"""
import logging
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .. import scripts_db as db
from ..config import settings
from ..scripts_core import get_next_run, run_script_now, stop_script, sync_task

logger = logging.getLogger("scheduler.scripts")
router = APIRouter(tags=["scripts"])

VALID_TYPES = ("crawler", "ai_task", "service", "automation")
VALID_VISIBILITY = ("public", "private")


def require_admin(x_role: str = Header("", alias="X-Role")) -> None:
    """Admin 校验：由 Gateway 转发时注入 X-Role（直接访问 scheduler 也安全）"""
    if x_role != "admin":
        raise HTTPException(403, "Admin only")


# ---- 请求模型 ----


class ScriptCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    type: str = "automation"
    command: str = Field(..., min_length=1)
    visibility: str = "public"
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


def _build_summary(script_id: int) -> dict:
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


# ---- User 接口（只读，仅公开脚本）----


@router.get("/scripts")
async def list_public_scripts() -> dict:
    rows = [r for r in db.list_scripts(public_only=True)]
    return {"scripts": [_public_script(r) for r in rows]}


@router.get("/scripts/{script_id}/status")
async def script_status(script_id: int) -> dict:
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
async def script_summary(script_id: int) -> dict:
    row = db.get_script(script_id)
    if not row or row["visibility"] != "public" or not row["enabled"]:
        raise HTTPException(404, "Script not found")
    return _build_summary(script_id)


# ---- Admin 接口 ----


@router.get("/admin/scripts")
async def admin_list_scripts(_: None = Depends(require_admin)) -> dict:
    return {"scripts": [_admin_script(r) for r in db.list_scripts()]}


@router.post("/admin/scripts", status_code=201)
async def admin_create_script(req: ScriptCreate,
                              _: None = Depends(require_admin)) -> dict:
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
                              _: None = Depends(require_admin)) -> dict:
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
async def admin_delete_script(script_id: int,
                              _: None = Depends(require_admin)) -> dict:
    if not db.delete_script(script_id):
        raise HTTPException(404, "Script not found")
    # 移除 APScheduler job
    from ..core import get_scheduler
    from ..scripts_core import job_id
    job = get_scheduler().get_job(job_id(script_id))
    if job:
        job.remove()
    return {"deleted": script_id}


@router.post("/admin/scripts/{script_id}/run")
async def admin_run_script(script_id: int,
                           _: None = Depends(require_admin)) -> dict:
    if not db.get_script(script_id):
        raise HTTPException(404, "Script not found")
    try:
        run_id = run_script_now(script_id)
    except ValueError:
        raise HTTPException(404, "Script not found")
    return {"run_id": run_id, "status": "running"}


@router.post("/admin/scripts/{script_id}/stop")
async def admin_stop_script(script_id: int,
                            _: None = Depends(require_admin)) -> dict:
    if not db.get_script(script_id):
        raise HTTPException(404, "Script not found")
    killed = stop_script(script_id)
    return {"stopped": script_id, "killed": killed}


@router.get("/admin/scripts/{script_id}/summary")
async def admin_script_summary(script_id: int,
                               _: None = Depends(require_admin)) -> dict:
    if not db.get_script(script_id):
        raise HTTPException(404, "Script not found")
    return _build_summary(script_id)


@router.get("/admin/scripts/{script_id}/logs")
async def admin_script_logs(script_id: int, date: str | None = None,
                            _: None = Depends(require_admin)) -> dict:
    row = db.get_script(script_id)
    if not row:
        raise HTTPException(404, "Script not found")
    from ..scripts_runner import _log_path
    dt = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now(timezone.utc).astimezone()
    path = _log_path(row["name"], dt)
    lines = []
    try:
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
async def admin_analyze_error(script_id: int,
                              _: None = Depends(require_admin)) -> dict:
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
