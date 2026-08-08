"""AI 服务代理路由：/api/ai/* → ai-service:8000"""
import logging

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from ..auth import require_user
from ..config import settings

logger = logging.getLogger("gateway.ai")
router = APIRouter(prefix="/api/ai", tags=["ai"])

# 复用连接
_client = httpx.AsyncClient(
    base_url=settings.AI_SERVICE_URL,
    timeout=httpx.Timeout(settings.REQUEST_TIMEOUT),
)


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
)
async def proxy_ai(path: str, request: Request, user: dict = Depends(require_user)) -> Response:
    """转发请求到 ai-service"""
    url = f"/{path}"
    # 构造查询参数
    params = dict(request.query_params)

    # 读取请求体
    body = await request.body() if request.method in ("POST", "PUT") else None

    # 注入用户身份 Header（供 ai-service 读取）
    headers = {
        "X-User-Id": str(user["uid"]),
        "X-Username": user["sub"],
        "X-Role": user["role"],
    }

    # 转发 form-data（文件上传）
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        files = []
        data = {}
        for key, value in form.multi_items():
            if hasattr(value, "read"):  # UploadFile
                files.append((key, (value.filename, await value.read(), value.content_type)))
            else:
                data[key] = value
        resp = await _client.request(request.method, url, params=params, data=data, files=files, headers=headers)
    else:
        if body:
            headers["content-type"] = content_type
        resp = await _client.request(request.method, url, params=params, content=body, headers=headers)

    logger.info("AI proxy %s %s -> %d (user=%s)", request.method, url, resp.status_code, user["sub"])
    return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))
