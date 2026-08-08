"""Scheduler 服务代理路由：/api/scheduler/* → scheduler:8002"""
import logging

import httpx
from fastapi import APIRouter, Depends, Request, Response

from ..auth import require_auth
from ..config import settings

logger = logging.getLogger("gateway.scheduler")
router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

_client = httpx.AsyncClient(
    base_url=settings.SCHEDULER_SERVICE_URL,
    timeout=httpx.Timeout(settings.REQUEST_TIMEOUT),
)


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
    dependencies=[Depends(require_auth)],
)
async def proxy_scheduler(path: str, request: Request) -> Response:
    """转发请求到 scheduler 服务"""
    url = f"/{path}"
    params = dict(request.query_params)
    body = await request.body() if request.method in ("POST", "PUT") else None

    headers = {}
    if body:
        headers["content-type"] = request.headers.get("content-type", "")

    resp = await _client.request(
        request.method, url, params=params, content=body, headers=headers
    )

    logger.info("Scheduler proxy %s %s -> %d", request.method, url, resp.status_code)
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )
