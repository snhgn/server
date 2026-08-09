# -*- coding: utf-8 -*-
"""课表数据每日定时同步（gateway 进程内 asyncio 后台任务）。

说明：
- 系统安全约束为不存学号/密码，因此无法在后台"重新登录教务系统"抓最新课表；
  本任务改为：每天对已有 schedule_cache 的用户执行 缓存 → courses → AI 数据目录 同步，
  并做 hash 变化检测（无变化不重写文件、不更新状态）。
- 用户主动刷新课表（POST /api/schedule/get）时也会即时同步（见 service.py）。
"""
import asyncio
import logging
from datetime import datetime

from ..config import settings
from . import course_context, course_db

logger = logging.getLogger("gateway.schedule.scheduler")


def _next_run_seconds() -> float:
    """距下一个 COURSE_SYNC_HOUR 时刻的秒数。"""
    now = datetime.now()
    target = now.replace(hour=settings.COURSE_SYNC_HOUR, minute=0, second=0, microsecond=0)
    if target <= now:
        target = target.replace(day=target.day + 1)
    return (target - now).total_seconds()


async def _daily_sync() -> None:
    """每日同步任务主体：对全部有缓存课表的用户同步，记录失败不中断。"""
    try:
        results = await asyncio.to_thread(course_context.sync_all_from_cache)
        ok = sum(1 for r in results if r.get("status") in ("success", "skipped"))
        logger.info(
            "course daily sync done: total=%d ok=%d changed=%d",
            len(results), ok,
            sum(1 for r in results if r.get("changed")),
        )
    except Exception as exc:
        logger.error("course daily sync fatal: %s: %s", type(exc).__name__, str(exc)[:300])


async def run_daily_sync_loop() -> None:
    """循环调度：首次启动延迟到次日时刻，之后每天执行一次。"""
    await asyncio.sleep(_next_run_seconds())
    while True:
        await _daily_sync()
        await asyncio.sleep(86400)


def start() -> asyncio.Task:
    """在 FastAPI lifespan 中调用，返回后台任务句柄（供 shutdown 取消）。"""
    return asyncio.create_task(run_daily_sync_loop(), name="course-daily-sync")
