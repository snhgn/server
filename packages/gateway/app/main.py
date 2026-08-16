"""API Gateway - 统一入口"""
import asyncio
import contextlib
import logging
import logging.handlers
import os
from pathlib import Path

from fastapi import FastAPI

from . import sessions
from .routers import ai, auth, schedule, scheduler, scripts, status
from .schedule import course_db, db as schedule_db
from .schedule import scheduler as course_scheduler

_LOG_DIR = Path(os.getenv("LOG_DIR", "/app/logs"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            _LOG_DIR / "gateway.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger("gateway")

# 让 uvicorn 访问日志也写入文件，统一格式
_uv_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
for uv_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uv_logger = logging.getLogger(uv_name)
    uv_logger.propagate = False  # 避免重复输出
    for h in [
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            _LOG_DIR / "gateway.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
        ),
    ]:
        h.setFormatter(_uv_fmt)
        uv_logger.addHandler(h)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    # 登录 Session 表（幂等，CREATE IF NOT EXISTS）+ 课表缓存表 + 课程表 + 同步状态表
    sessions.init()
    schedule_db.init_db()
    course_db.init_db()
    # 每日定时同步：启动后延迟到 COURSE_SYNC_HOUR 时刻执行
    task = course_scheduler.start()
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


app = FastAPI(title="API Gateway", version="1.0.0", redirect_slashes=False, lifespan=lifespan)

app.include_router(auth.router)
app.include_router(ai.router)
app.include_router(schedule.router)
app.include_router(scheduler.router)
app.include_router(scripts.router)
app.include_router(status.router)


@app.get("/")
async def root() -> dict:
    return {"service": "gateway", "version": "1.0.0"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "gateway"}
