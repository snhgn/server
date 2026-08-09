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
