"""AI 服务代理路由：/api/ai/* → ai-service:8000"""
import logging

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from ..auth import require_auth
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
    dependencies=[Depends(require_auth)],
)
async def proxy_ai(path: str, request: Request) -> Response:
    """转发请求到 ai-service"""
    url = f"/{path}"
    # 构造查询参数
    params = dict(request.query_params)

    # 读取请求体
    body = await request.body() if request.method in ("POST", "PUT") else None

    # 转发 form-data（文件上传）
    headers = {}
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
        resp = await _client.request(request.method, url, params=params, data=data, files=files)
    else:
        if body:
            headers["content-type"] = content_type
        resp = await _client.request(request.method, url, params=params, content=body, headers=headers)

    logger.info("AI proxy %s %s -> %d", request.method, url, resp.status_code)
    return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))
