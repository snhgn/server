"""JWT 认证 + 权限中间件"""
import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import sessions
from .config import settings

logger = logging.getLogger("gateway.auth")

ALGORITHM = "HS256"
security = HTTPBearer(auto_error=False)


# ---- 用户存储（SQLite）----


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_user_by_username(username: str) -> dict | None:
    """按用户名查询用户"""
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username=?",
        (username,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    """按 ID 查询用户（用于 token 验证）"""
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, username, role FROM users WHERE id=?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ---- 用户缓存（进程内 TTL，避免每个请求都查 SQLite）----
# role 变更/删除用户后最多 TTL 秒内生效；适合单实例网关的轻量方案
_USER_CACHE_TTL = 30.0
_user_cache: dict[int, tuple[float, dict]] = {}


async def _get_user_cached(user_id: int) -> dict | None:
    import time as _time

    now = _time.monotonic()
    hit = _user_cache.get(user_id)
    if hit is not None and now - hit[0] < _USER_CACHE_TTL:
        return hit[1]
    user = await asyncio.to_thread(get_user_by_id, user_id)
    if user is not None:
        _user_cache[user_id] = (now, user)
    return user


# ---- Session 缓存（进程内 TTL，Cookie 命中时避免每请求查 SQLite）----
_session_cache: dict[str, tuple[float, dict]] = {}


async def _get_payload_from_session(sid: str) -> dict | None:
    """Cookie session → 统一 payload {sub, uid, role}（用户信息以数据库为准）"""
    import time as _time

    now = _time.monotonic()
    hit = _session_cache.get(sid)
    if hit is not None and now - hit[0] < _USER_CACHE_TTL:
        return hit[1]
    uid = await asyncio.to_thread(sessions.get_session_user_id, sid)
    if uid is None:
        return None
    user = await _get_user_cached(uid)
    if user is None:
        return None
    payload = {"sub": user["username"], "uid": user["id"], "role": user["role"]}
    _session_cache[sid] = (now, payload)
    return payload


def invalidate_session_cache(sid: str | None = None) -> None:
    """Session 失效（logout/旋转）后立即清除缓存，确保不再可用"""
    if sid is None:
        _session_cache.clear()
    else:
        _session_cache.pop(sid, None)


def invalidate_user_cache(user_id: int | None = None) -> None:
    """用户信息变更（改角色/删除/改密）后主动失效缓存"""
    if user_id is None:
        _user_cache.clear()
    else:
        _user_cache.pop(user_id, None)
    _session_cache.clear()  # session 缓存的 payload 含 role，一并失效


# ---- 密码 & Token ----


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user: dict) -> str:
    """签发 JWT：包含 user_id, username, role"""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {
        "exp": expire,
        "sub": user["username"],
        "uid": user["id"],
        "role": user["role"],
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])


# ---- 权限中间件 ----


async def require_auth(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """鉴权（双通道）：优先 HttpOnly Cookie Session，回退 Bearer JWT。
    返回统一 payload（含 uid, sub, role），下游依赖无感知。"""
    # 通道 1：Cookie Session（持久登录）
    sid = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if sid:
        payload = await _get_payload_from_session(sid)
        if payload is not None:
            return payload

    # 通道 2：Bearer JWT（兼容旧客户端）
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(cred.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    # 校验用户仍然存在（防止已删除用户的 token 继续生效）；
    # 走 TTL 缓存，未命中才查 SQLite（线程池执行，不阻塞事件循环）
    user = await _get_user_cached(payload.get("uid", 0))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    payload["role"] = user["role"]  # 以数据库为准，防止 role 变更后旧 token 仍带旧 role
    return payload


async def require_user(payload: dict = Depends(require_auth)) -> dict:
    """要求 user 或 admin 角色"""
    if payload.get("role") not in ("user", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    return payload


async def require_admin(payload: dict = Depends(require_auth)) -> dict:
    """要求 admin 角色"""
    if payload.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return payload
