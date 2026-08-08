"""API Gateway - 统一入口"""
import logging
import logging.handlers
import os
from pathlib import Path

from fastapi import FastAPI

from .routers import ai, auth, scheduler, status

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

app = FastAPI(title="API Gateway", version="1.0.0")

app.include_router(auth.router)
app.include_router(ai.router)
app.include_router(scheduler.router)
app.include_router(status.router)


@app.get("/")
async def root() -> dict:
    return {"service": "gateway", "version": "1.0.0"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "gateway"}
