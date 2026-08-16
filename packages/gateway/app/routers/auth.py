"""认证路由：/api/auth/*"""
import asyncio
import logging
import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from .. import sessions
from ..auth import (
    create_token,
    get_user_by_username,
    invalidate_session_cache,
    require_auth,
    verify_password,
)
from ..config import settings

logger = logging.getLogger("gateway.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])

# ---- 登录失败限流（进程内滑动窗口，防爆破；单实例轻量方案）----
_LOGIN_WINDOW = 300.0  # 5 分钟窗口
_LOGIN_MAX_FAILS = 10   # 窗口内最大失败次数（含用户不存在）
_login_fails: dict[str, deque] = {}


def _login_blocked(username: str) -> bool:
    q = _login_fails.get(username)
    if not q:
        return False
    now = time.monotonic()
    while q and now - q[0] > _LOGIN_WINDOW:
        q.popleft()
    return len(q) >= _LOGIN_MAX_FAILS


def _record_login_fail(username: str) -> None:
    _login_fails.setdefault(username, deque()).append(time.monotonic())


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: str | None = None
    role: str | None = None
    username: str | None = None
    user_id: int | None = None
    expires_in_hours: int | None = None


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, response: Response, req: LoginRequest) -> LoginResponse:
    # SQLite 查询与 bcrypt（~100ms CPU）均走线程池，避免登录阻塞其他请求
    user = await asyncio.to_thread(get_user_by_username, req.username)
    if not user:
        _record_login_fail(req.username)
        logger.warning("Login failed: user '%s' not found", req.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if _login_blocked(req.username):
        logger.warning("Login blocked (rate limit): '%s'", req.username)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts, retry later")
    if not await asyncio.to_thread(
        verify_password, req.password, user["password_hash"]
    ):
        _record_login_fail(req.username)
        logger.warning("Login failed: wrong password for '%s'", req.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    _login_fails.pop(req.username, None)  # 成功后清零

    token = create_token(user)

    # ---- 创建 Server-side Session，设置 HttpOnly Cookie（持久登录）----
    sid, _ = await asyncio.to_thread(sessions.create_session, user["id"])
    # Session 旋转（防 fixation）：若请求携带旧 cookie（如重新登录），旧 Session 立即失效
    old_sid = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if old_sid and old_sid != sid:
        await asyncio.to_thread(sessions.delete_session, old_sid)
        invalidate_session_cache(old_sid)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=sid,
        max_age=settings.SESSION_EXPIRE_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )

    logger.info("Login ok: user='%s' role=%s", user["username"], user["role"])
    return LoginResponse(
        success=True,
        token=token,
        role=user["role"],
        username=user["username"],
        user_id=user["id"],
        expires_in_hours=settings.JWT_EXPIRE_HOURS,
    )


@router.get("/verify")
async def verify(payload: dict = Depends(require_auth)) -> dict:
    return {
        "valid": True,
        "user": payload.get("sub"),
        "user_id": payload.get("uid"),
        "role": payload.get("role"),
    }


@router.get("/me")
async def me(payload: dict = Depends(require_auth)) -> dict:
    """当前用户信息（前端启动时恢复登录状态）；未登录由 require_auth 返回 401。
    只返回基本信息，不含密码哈希/Session ID 等敏感字段。"""
    return {
        "authenticated": True,
        "user": {
            "id": payload.get("uid"),
            "username": payload.get("sub"),
            "role": payload.get("role"),
        },
    }


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    """退出登录：服务端删除 Session（立即失效）+ 清除客户端 Cookie（幂等）"""
    sid = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if sid:
        await asyncio.to_thread(sessions.delete_session, sid)
        invalidate_session_cache(sid)
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return {"success": True}
