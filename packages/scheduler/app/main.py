"""Scheduler 服务入口"""
import logging
import logging.handlers
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .config import settings
from .core import init_scheduler
from .routers import jobs, scripts
from .scripts_core import sync_all_tasks
from .scripts_db import init_db

_LOG_DIR = Path(os.getenv("LOG_DIR", "/app/logs"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            _LOG_DIR / "scheduler.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger("scheduler")

# 让 uvicorn 访问日志也写入文件，统一格式
_uv_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
for uv_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uv_logger = logging.getLogger(uv_name)
    uv_logger.propagate = False  # 避免重复输出
    for h in [
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            _LOG_DIR / "scheduler.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
        ),
    ]:
        h.setFormatter(_uv_fmt)
        uv_logger.addHandler(h)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sched = init_scheduler()
    sync_all_tasks()
    logger.info("Scheduler started: %d jobs", len(sched.get_jobs()))
    yield
    sched.shutdown(wait=False)
    logger.info("Scheduler stopped")


app = FastAPI(title="Scheduler Service", version="1.0.0", lifespan=lifespan, redirect_slashes=False)
app.include_router(jobs.router)
app.include_router(scripts.router)


@app.get("/")
async def root() -> dict:
    return {"service": "scheduler", "version": "1.0.0"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "scheduler"}
