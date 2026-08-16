"""APScheduler 任务管理"""
import asyncio
import logging
import os
from datetime import datetime

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .executor import execute_command, execute_http, record_history

logger = logging.getLogger("scheduler.core")

os.makedirs(os.path.dirname(settings.SQLITE_DB_PATH), exist_ok=True)

scheduler: AsyncIOScheduler | None = None


async def _execute_job(job_id: str, name: str, job_type: str, payload: str, timeout: int):
    """模块级任务执行函数（APScheduler 要求可序列化）"""
    started = datetime.now()
    success = False
    output, error = "", ""
    try:
        if job_type == "command":
            success, output, error = await execute_command(payload, timeout)
        elif job_type == "http":
            import json
            cfg = json.loads(payload)
            success, output, error = await execute_http(
                cfg.get("url", ""),
                cfg.get("method", "GET"),
                cfg.get("headers"),
                cfg.get("body"),
                timeout,
            )
        else:
            error = f"Unknown job type: {job_type}"
    except Exception as e:
        error = str(e)
    finally:
        finished = datetime.now()
        # SQLite 写入走线程池，不阻塞调度器事件循环
        await asyncio.to_thread(
            record_history, job_id, name, started, finished, success, output, error
        )
        status = "OK" if success else "FAIL"
        logger.info("Job '%s' (%s) finished: %s", name, job_id, status)
        if error:
            logger.warning("Job '%s' error: %s", name, error[:200])


def init_scheduler() -> AsyncIOScheduler:
    global scheduler
    if scheduler is not None:
        return scheduler

    jobstore = SQLAlchemyJobStore(url=f"sqlite:///{settings.SQLITE_DB_PATH}")
    scheduler = AsyncIOScheduler(
        jobstores={"default": jobstore},
        timezone=settings.TIMEZONE,
        job_defaults={"coalesce": True, "max_instances": 1},
    )
    scheduler.start()
    logger.info("Scheduler initialized, timezone=%s", settings.TIMEZONE)
    return scheduler


def get_scheduler() -> AsyncIOScheduler:
    if scheduler is None:
        return init_scheduler()
    return scheduler


def add_job(job_id: str, name: str, job_type: str, payload: str, cron: str, timeout: int = 300) -> dict:
    sched = get_scheduler()
    trigger = CronTrigger.from_crontab(cron, timezone=settings.TIMEZONE)

    existing = sched.get_job(job_id)
    if existing:
        sched.remove_job(job_id)

    sched.add_job(
        _execute_job,
        trigger=trigger,
        id=job_id,
        name=name,
        args=[job_id, name, job_type, payload, timeout],
        replace_existing=True,
    )
    logger.info("Added job: %s (%s) cron=%s", name, job_id, cron)
    return {"id": job_id, "name": name, "type": job_type, "cron": cron}


def remove_job(job_id: str) -> bool:
    sched = get_scheduler()
    job = sched.get_job(job_id)
    if not job:
        return False
    sched.remove_job(job_id)
    logger.info("Removed job: %s", job_id)
    return True


def pause_job(job_id: str) -> bool:
    sched = get_scheduler()
    if not sched.get_job(job_id):
        return False
    sched.pause_job(job_id)
    return True


def resume_job(job_id: str) -> bool:
    sched = get_scheduler()
    if not sched.get_job(job_id):
        return False
    sched.resume_job(job_id)
    return True


async def trigger_job(job_id: str) -> bool:
    sched = get_scheduler()
    job = sched.get_job(job_id)
    if not job:
        return False
    await _execute_job(*job.args)
    return True


def list_jobs() -> list[dict]:
    sched = get_scheduler()
    jobs = []
    for job in sched.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "trigger": str(job.trigger),
            "next_run": next_run.isoformat() if next_run else None,
            "pending": next_run is not None,
        })
    return jobs


def get_job(job_id: str) -> dict | None:
    sched = get_scheduler()
    job = sched.get_job(job_id)
    if not job:
        return None
    next_run = job.next_run_time
    return {
        "id": job.id,
        "name": job.name,
        "trigger": str(job.trigger),
        "next_run": next_run.isoformat() if next_run else None,
        "pending": next_run is not None,
    }
