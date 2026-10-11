"""Scheduler 服务代理路由：/api/scheduler/* → scheduler:8002"""
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..auth import require_user
from ..config import settings

logger = logging.getLogger("gateway.scheduler")
router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

_client = httpx.AsyncClient(
    base_url=settings.SCHEDULER_SERVICE_URL,
    timeout=httpx.Timeout(settings.REQUEST_TIMEOUT),
)


async def aclose() -> None:
    """优雅关闭 HTTP 客户端连接池"""
    await _client.aclose()


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
)
async def proxy_scheduler(path: str, request: Request, user: dict = Depends(require_user)) -> Response:
    """转发请求到 scheduler 服务；写操作仅限 admin"""
    if request.method in ("POST", "PUT", "DELETE") and user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    url = f"/{path}"
    params = dict(request.query_params)
    body = await request.body() if request.method in ("POST", "PUT") else None

    # 注入用户身份 Header
    headers = {
        "X-User-Id": str(user["uid"]),
        "X-Username": user["sub"],
        "X-Role": user["role"],
    }
    if body:
        headers["content-type"] = request.headers.get("content-type", "")

    try:
        resp = await _client.request(
            request.method, url, params=params, content=body, headers=headers
        )
    except (httpx.ConnectError, httpx.ConnectTimeout):
        raise HTTPException(502, "定时任务服务暂时不可用，请稍后重试")
    except httpx.TimeoutException:
        raise HTTPException(504, "定时任务服务请求超时，请稍后重试")
    except httpx.RequestError as exc:
        logger.warning("Scheduler proxy error %s %s: %s", request.method, url, exc)
        raise HTTPException(502, f"定时任务服务通信异常: {exc}")

    logger.info("Scheduler proxy %s %s -> %d (user=%s)", request.method, url, resp.status_code, user["sub"])
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )
