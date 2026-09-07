"""课表路由：/api/schedule/*

- POST /get              提交学号/密码，登录教务系统抓取课表并缓存（登录用户 / 访客均可）
- GET  /current          返回当前登录用户缓存课表
- GET  /view/{user_id}   访客通过 user_id 查看缓存课表
- GET  /query            访客通过学号查看缓存课表
- GET  /status           （admin）缓存统计，不含任何课表详情

安全：本路由不记录学号/密码；凭据只在请求生命周期内存在。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth import optional_user, require_admin, require_user
from ..schedule import service

logger = logging.getLogger("gateway.schedule")
router = APIRouter(prefix="/api/schedule", tags=["schedule"])


class GetScheduleRequest(BaseModel):
    student_id: str
    password: str
    force: bool = False


@router.post("/get")
async def get_schedule(req: GetScheduleRequest,
                       user: dict | None = Depends(optional_user)) -> dict:
    """抓取课表（登录用户 / 访客均可使用）。

    - 登录用户：课表绑定到 user_id，支持 AI 课程同步
    - 访客：课表按学号缓存，后续可通过 GET /query?student_id=xxx 查看
    """
    student_id = req.student_id.strip()
    if not student_id or not req.password:
        raise HTTPException(400, "请输入学号和密码")
    uid = user["uid"] if user else service.guest_user_id(student_id)
    try:
        return await service.fetch_schedule(uid, student_id, req.password, req.force)
    except service.ScheduleError as e:
        raise HTTPException(e.http_status, e.message)


@router.get("/current")
def current(user: dict = Depends(require_user)) -> dict:
    """当前登录用户缓存课表；无缓存返回 404。"""
    data = service.get_current(user["uid"])
    if data is None:
        raise HTTPException(404, "暂无课表，请先获取课表")
    return data


@router.get("/view/{user_id}")
def view_schedule(user_id: int) -> dict:
    """访客查看指定用户的缓存课表（无需登录）；无缓存返回 404。"""
    data = service.get_current(user_id)
    if data is None:
        raise HTTPException(404, "该用户暂无课表")
    return data


@router.get("/query")
def query_by_student(student_id: str = Query(..., description="学号")) -> dict:
    """访客通过学号查看缓存课表（无需登录）。

    学号需与之前 POST /get 提交的一致；未抓取过返回 404。
    """
    sid = student_id.strip()
    if not sid:
        raise HTTPException(400, "请提供学号")
    uid = service.guest_user_id(sid)
    data = service.get_current(uid)
    if data is None:
        raise HTTPException(404, "暂无该学号的课表缓存，请先获取课表")
    return data


@router.get("/status")
def status(_: dict = Depends(require_admin)) -> dict:
    """管理端：课表缓存统计。"""
    caches = service.list_cache_stats()
    return {"total": len(caches), "caches": caches}

