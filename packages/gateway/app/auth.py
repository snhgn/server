"""JWT 认证 + 权限中间件"""
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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
    cred: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """基础 JWT 验证：返回 payload（含 uid, role）"""
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    try:
        payload = decode_token(cred.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    # 校验用户仍然存在（防止已删除用户的 token 继续生效）
    user = get_user_by_id(payload.get("uid", 0))
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
