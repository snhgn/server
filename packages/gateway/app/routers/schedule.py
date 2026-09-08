"""课表路由：/api/schedule/*

- POST /get              提交学号/密码，登录教务系统抓取课表并缓存（登录用户 / 访客均可）
- GET  /current          返回当前登录用户缓存课表
- GET  /view/{user_id}   访客通过 user_id 查看缓存课表
- GET  /query            访客通过学号查看缓存课表
- GET  /status           （admin）缓存统计，不含任何课表详情

安全：本路由不记录密码；凭据只在请求生命周期内存在。
所有课表 API 均附带 no-cache 头，杜绝浏览器与中间代理持久缓存旧课表。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from ..auth import optional_user, require_admin, require_user
from ..schedule import service

logger = logging.getLogger("gateway.schedule")
router = APIRouter(prefix="/api/schedule", tags=["schedule"])


class GetScheduleRequest(BaseModel):
    student_id: str
    password: str
    force: bool = True  # 同步请求默认执行真实教务拉取，避免用户提交凭据后仍读旧缓存


def _set_no_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


@router.post("/get")
async def get_schedule(req: GetScheduleRequest,
                       response: Response,
                       user: dict | None = Depends(optional_user)) -> dict:
    """抓取课表（登录用户 / 访客均可使用）。

    - 登录用户：课表绑定到 user_id，同时更新 guest 映射并支持 AI 课程同步
    - 访客：课表按学号及 guest_user_id 缓存，后续可通过 GET /query?student_id=xxx 查看
    """
    _set_no_cache(response)
    student_id = req.student_id.strip()
    if not student_id or not req.password:
        raise HTTPException(400, "请输入学号和密码")
    uid = user["uid"] if user else service.guest_user_id(student_id)
    try:
        return await service.fetch_schedule(uid, student_id, req.password, req.force)
    except service.ScheduleError as e:
        raise HTTPException(e.http_status, e.message)


@router.get("/current")
def current(response: Response, user: dict = Depends(require_user)) -> dict:
    """当前登录用户缓存课表；无缓存返回 404。"""
    _set_no_cache(response)
    data = service.get_current(user["uid"])
    if data is None:
        raise HTTPException(404, "暂无课表，请先获取课表")
    return data


@router.get("/view/{user_id}")
def view_schedule(user_id: int, response: Response) -> dict:
    """访客查看指定用户的缓存课表（无需登录）；无缓存返回 404。"""
    _set_no_cache(response)
    data = service.get_current(user_id)
    if data is None:
        raise HTTPException(404, "该用户暂无课表")
    return data


@router.get("/query")
def query_by_student(response: Response,
                     student_id: str = Query(..., description="学号")) -> dict:
    """访客通过学号查看缓存课表（无需登录）。

    双重检索：按 student_id 或派生 guest_user_id；未抓取过返回 404。
    """
    _set_no_cache(response)
    sid = student_id.strip()
    if not sid:
        raise HTTPException(400, "请提供学号")
    data = service.get_by_student(sid)
    if data is None:
        raise HTTPException(404, "暂无该学号的课表缓存，请先获取课表")
    return data


@router.get("/status")
def status(response: Response, _: dict = Depends(require_admin)) -> dict:
    """管理端：课表缓存统计。"""
    _set_no_cache(response)
    caches = service.list_cache_stats()
    return {"total": len(caches), "caches": caches}
