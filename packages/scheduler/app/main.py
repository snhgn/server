"""Scheduler 服务入口"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .core import init_scheduler
from .routers import jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scheduler")


@asynccontextmanager
async def lifespan(app: FastAPI):
    sched = init_scheduler()
    logger.info("Scheduler started: %d jobs", len(sched.get_jobs()))
    yield
    sched.shutdown(wait=False)
    logger.info("Scheduler stopped")


app = FastAPI(title="Scheduler Service", version="1.0.0", lifespan=lifespan)
app.include_router(jobs.router)


@app.get("/")
async def root() -> dict:
    return {"service": "scheduler", "version": "1.0.0"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "scheduler"}
