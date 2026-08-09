"""Scripts 代理路由：/api/scripts/*（user）与 /api/admin/scripts/*（admin）→ scheduler"""
import logging

import httpx
from fastapi import APIRouter, Depends, Request, Response

from ..auth import require_admin, require_user
from ..config import settings

logger = logging.getLogger("gateway.scripts")
router = APIRouter(prefix="/api", tags=["scripts"])

_client = httpx.AsyncClient(
    base_url=settings.SCHEDULER_SERVICE_URL,
    timeout=httpx.Timeout(settings.REQUEST_TIMEOUT),
)


async def _proxy(request: Request, prefix: str, path: str, user: dict) -> Response:
    """转发到 scheduler；prefix 为 scheduler 侧路由前缀（如 /scripts、/admin/scripts）"""
    url = prefix + (f"/{path}" if path else "")
    params = dict(request.query_params)
    body = await request.body() if request.method in ("POST", "PUT") else None
    headers = {
        "X-User-Id": str(user["uid"]),
        "X-Username": user["sub"],
        "X-Role": user["role"],
    }
    if body:
        headers["content-type"] = request.headers.get("content-type", "")
    resp = await _client.request(
        request.method, url, params=params, content=body, headers=headers
    )
    logger.info("Scripts proxy %s %s -> %d (user=%s)", request.method, url,
                resp.status_code, user["sub"])
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


@router.api_route("/scripts", methods=["GET"])
@router.api_route("/scripts/{path:path}", methods=["GET"])
async def user_scripts(request: Request, path: str = "",
                       user: dict = Depends(require_user)) -> Response:
    """User 只读脚本接口"""
    return await _proxy(request, "/scripts", path, user)


@router.api_route("/admin/scripts", methods=["GET", "POST", "PUT", "DELETE"])
@router.api_route("/admin/scripts/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def admin_scripts(request: Request, path: str = "",
                        user: dict = Depends(require_admin)) -> Response:
    """Admin 管理接口（非 admin 在网关返回 403）"""
    return await _proxy(request, "/admin/scripts", path, user)
