"""AI 服务代理路由：/api/ai/* → ai-service:8000"""
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from ..auth import require_user
from ..config import settings

logger = logging.getLogger("gateway.ai")
router = APIRouter(prefix="/api/ai", tags=["ai"])

# 复用连接：流式响应需要更长的 read timeout（None 表示无限等待）
_client = httpx.AsyncClient(
    base_url=settings.AI_SERVICE_URL,
    timeout=httpx.Timeout(connect=10.0, read=None, write=30.0, pool=10.0),
)


async def aclose() -> None:
    """优雅关闭 HTTP 客户端连接池"""
    await _client.aclose()


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy_ai(path: str, request: Request, user: dict = Depends(require_user)) -> Response:
    """转发请求到 ai-service"""
    url = f"/api/{path}"
    # 构造查询参数
    params = dict(request.query_params)

    # 注入用户身份 Header（供 ai-service 读取）
    headers = {
        "X-User-Id": str(user["uid"]),
        "X-Username": user["sub"],
        "X-Role": user["role"],
    }
    content_type = request.headers.get("content-type", "")

    # multipart（文件上传）：原始体流式透传，不解析、不缓存。
    # 网关内存占用与文件大小无关（大小/类型校验由 ai-service 负责）。
    if "multipart/form-data" in content_type:
        async def _raw_body():
            async for chunk in request.stream():
                yield chunk

        fwd_headers = {**headers, "content-type": content_type}
        req = _client.build_request(
            request.method, url, params=params, content=_raw_body(), headers=fwd_headers
        )
        try:
            resp = await _client.send(req, stream=False)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise HTTPException(502, "AI 服务暂时不可用，请稍后重试")
        except httpx.TimeoutException:
            raise HTTPException(504, "AI 服务请求超时，请稍后重试")
        except httpx.RequestError as exc:
            logger.warning("AI proxy upload error %s: %s", url, exc)
            raise HTTPException(502, f"AI 服务通信异常: {exc}")
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type"),
        )

    # 读取请求体（JSON 等小体）
    body = await request.body() if request.method in ("POST", "PUT", "PATCH") else None

    # SSE 流式：使用 client.stream()，逐块转发
    is_sse = path.endswith("/chat/stream") or path == "chat/stream"
    if is_sse and request.method == "POST":
        req_headers = {**headers, "content-type": content_type} if body else headers

        async def sse_iter():
            try:
                async with _client.stream(
                    "POST", url, params=params, content=body, headers=req_headers
                ) as resp:
                    async for chunk in resp.aiter_raw():
                        yield chunk
            except (httpx.ConnectError, httpx.ConnectTimeout):
                logger.warning("AI proxy SSE connect failed %s", url)
                yield b'event: error\ndata: {"message": "AI service unavailable"}\n\n'
            except httpx.TimeoutException:
                logger.warning("AI proxy SSE timeout %s", url)
                yield b'event: error\ndata: {"message": "AI service request timeout"}\n\n'
            except Exception as exc:
                logger.warning("AI proxy SSE stream error %s: %s", url, exc)
                yield b'event: error\ndata: {"message": "AI service stream interrupted"}\n\n'

        logger.info("AI proxy SSE POST %s (user=%s)", url, user["sub"])
        return StreamingResponse(
            sse_iter(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 普通请求
    if body:
        headers["content-type"] = content_type
    try:
        resp = await _client.request(request.method, url, params=params, content=body, headers=headers)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        raise HTTPException(502, "AI 服务暂时不可用，请稍后重试")
    except httpx.TimeoutException:
        raise HTTPException(504, "AI 服务响应超时，请稍后重试")
    except httpx.RequestError as exc:
        logger.warning("AI proxy request error %s %s: %s", request.method, url, exc)
        raise HTTPException(502, f"AI 服务通信异常: {exc}")

    logger.info("AI proxy %s %s -> %d (user=%s)", request.method, url, resp.status_code, user["sub"])
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )
