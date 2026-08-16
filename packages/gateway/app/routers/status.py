"""系统状态路由：/api/status"""
import asyncio
import shutil
import socket
import time

import httpx
import psutil
from fastapi import APIRouter, Depends

from ..auth import require_admin

router = APIRouter(prefix="/api/status", tags=["status"])

_start_time = time.time()


async def _get_docker_containers() -> list[dict]:
    """通过 Docker API 获取运行中的容器（无需 docker CLI）"""
    import logging
    logger = logging.getLogger("gateway.status")
    try:
        async with httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(uds="/var/run/docker.sock"),
            timeout=5.0,
        ) as client:
            resp = await client.get("http://docker/containers/json")
            if resp.status_code != 200:
                logger.warning("Docker API %d: %s", resp.status_code, resp.text[:200])
                return []
            data = resp.json()
            return [
                {
                    "name": c["Names"][0].lstrip("/") if c.get("Names") else "",
                    "image": c.get("Image", ""),
                    "status": c.get("Status", ""),
                    "ports": [
                        f"{p.get('PublicPort','')}:{p.get('PrivatePort','')}"
                        for p in c.get("Ports", [])
                        if p.get("PublicPort")
                    ],
                }
                for c in data
            ]
    except Exception as e:
        logger.warning("Docker API error: %s", e)
        return []


@router.get("")
@router.get("/")
async def system_status(_: dict = Depends(require_admin)) -> dict:
    """系统状态"""
    # cpu_percent(interval=1) 会阻塞 1 秒采样，走线程池避免阻塞事件循环
    cpu_percent = await asyncio.to_thread(psutil.cpu_percent, 1)
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage("/")

    return {
        "hostname": socket.gethostname(),
        "uptime_seconds": round(time.time() - _start_time),
        "cpu": {"cores": psutil.cpu_count(), "percent": cpu_percent},
        "memory": {
            "total": mem.total,
            "used": mem.used,
            "available": mem.available,
            "percent": mem.percent,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": round(disk.used / disk.total * 100, 1),
        },
        "containers": await _get_docker_containers(),
    }


@router.get("/health")
async def health() -> dict:
    """公开健康检查（不需要认证）"""
    return {"status": "ok", "service": "gateway"}
