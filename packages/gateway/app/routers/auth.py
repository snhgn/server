"""认证路由：/api/auth/*"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth import create_token, get_user_by_username, require_auth, verify_password
from ..config import settings

logger = logging.getLogger("gateway.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: str | None = None
    role: str | None = None
    username: str | None = None
    expires_in_hours: int | None = None


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    user = get_user_by_username(req.username)
    if not user:
        logger.warning("Login failed: user '%s' not found", req.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not verify_password(req.password, user["password_hash"]):
        logger.warning("Login failed: wrong password for '%s'", req.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    token = create_token(user)
    logger.info("Login ok: user='%s' role=%s", user["username"], user["role"])
    return LoginResponse(
        success=True,
        token=token,
        role=user["role"],
        username=user["username"],
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
