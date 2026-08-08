"""认证路由：/api/auth/*"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth import create_token, require_auth, verify_password
from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: str | None = None
    expires_in_hours: int | None = None


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    if not settings.ADMIN_PASSWORD_HASH:
        raise HTTPException(500, "Admin password not configured")
    if not verify_password(req.password, settings.ADMIN_PASSWORD_HASH):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong password")
    token = create_token()
    return LoginResponse(success=True, token=token, expires_in_hours=settings.JWT_EXPIRE_HOURS)


@router.get("/verify")
async def verify(payload: dict = Depends(require_auth)) -> dict:
    return {"valid": True, "user": payload.get("sub")}
