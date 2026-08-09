"""课表路由：/api/schedule/*

- POST /get      用户提交学号/密码，登录教务系统抓取课表并缓存
- GET  /current  返回当前用户缓存课表
- GET  /status   （admin）缓存统计，不含任何课表详情

安全：本路由不记录学号/密码；凭据只在请求生命周期内存在。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_admin, require_user
from ..schedule import service

logger = logging.getLogger("gateway.schedule")
router = APIRouter(prefix="/api/schedule", tags=["schedule"])


class GetScheduleRequest(BaseModel):
    student_id: str
    password: str
    force: bool = False


@router.post("/get")
async def get_schedule(req: GetScheduleRequest,
                       user: dict = Depends(require_user)) -> dict:
    """抓取课表：非 force 且缓存新鲜时直接返回缓存，否则登录教务系统爬取。"""
    student_id = req.student_id.strip()
    if not student_id or not req.password:
        raise HTTPException(400, "请输入学号和密码")
    try:
        return await service.fetch_schedule(
            user["uid"], student_id, req.password, req.force)
    except service.ScheduleError as e:
        raise HTTPException(e.http_status, e.message)


@router.get("/current")
def current(user: dict = Depends(require_user)) -> dict:
    """当前用户缓存课表；无缓存返回 404。"""
    data = service.get_current(user["uid"])
    if data is None:
        raise HTTPException(404, "暂无课表，请先获取课表")
    return data


@router.get("/status")
def status(_: dict = Depends(require_admin)) -> dict:
    """管理端：课表缓存统计。"""
    caches = service.list_cache_stats()
    return {"total": len(caches), "caches": caches}
