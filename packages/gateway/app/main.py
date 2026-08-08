"""API Gateway - 统一入口"""
import logging

from fastapi import FastAPI

from .routers import ai, auth, scheduler, status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gateway")

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
