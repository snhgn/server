"""课表路由：/api/schedule/*

- POST /get              提交学号/密码，登录教务系统抓取课表并缓存（登录用户 / 访客均可）
                         访客首次同步时自动创建以学号为账号的访客用户并设置 Session Cookie
- GET  /current          返回当前登录用户缓存课表
- GET  /view/{user_id}   访客通过 user_id 查看缓存课表
- GET  /query            访客通过学号查看缓存课表
- GET  /status           （admin）缓存统计，不含任何课表详情

安全：本路由不记录密码；凭据只在请求生命周期内存在。
所有课表 API 均附带 no-cache 头，杜绝浏览器与中间代理持久缓存旧课表。
"""
import asyncio
import logging
import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from .. import sessions
from ..auth import invalidate_session_cache, optional_user, require_admin, require_user
from ..config import settings
from ..schedule import service, toolbox

logger = logging.getLogger("gateway.schedule")
router = APIRouter(prefix="/api/schedule", tags=["schedule"])


class GetScheduleRequest(BaseModel):
    student_id: str
    password: str
    force: bool = True  # 同步请求默认执行真实教务拉取，避免用户提交凭据后仍读旧缓存


class ToolboxAuthRequest(BaseModel):
    student_id: str
    password: str


class GradesQueryRequest(ToolboxAuthRequest):
    semester: str = ""
    display_mode: str = "all"


class ExamsQueryRequest(ToolboxAuthRequest):
    semester: str = ""
    category: str = ""


class ClassroomQueryRequest(ToolboxAuthRequest):
    semester: str = "2026-2027-1"
    building: str = ""
    week: int = 1
    day: int = 1
    start_period: int = 1
    end_period: int = 2


def _set_no_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


def _get_or_create_guest_user(student_id: str) -> int:
    """按学号查找或创建访客用户，返回 user_id。

    - username = student_id（学号即账号）
    - password_hash = 随机不可用哈希（不保存真实密码，仅占位）
    - role = 'user'
    """
    conn = sqlite3.connect(settings.SQLITE_DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE username=?", (student_id,)
        ).fetchone()
        if row:
            return int(row["id"])
        # 创建新用户：密码哈希设为不可逆随机串，无人能用密码登录此账号
        fake_hash = f"$nologin${secrets.token_hex(32)}"
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (student_id, fake_hash, "user"),
        )
        conn.commit()
        new_row = conn.execute(
            "SELECT id FROM users WHERE username=?", (student_id,)
        ).fetchone()
        logger.info("Auto-created guest user: student_id=%s, user_id=%s", student_id, new_row["id"])
        return int(new_row["id"])
    finally:
        conn.close()


def _set_session_cookie(response: Response, user_id: int, request: Request) -> None:
    """为用户创建 Server-side Session 并设置 HttpOnly Cookie。
    若请求已携带旧 Cookie，先使旧 Session 失效（Session 旋转防 fixation）。"""
    # 旋转旧 Session
    old_sid = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if old_sid:
        sessions.delete_session(old_sid)
        invalidate_session_cache(old_sid)
    # 创建新 Session
    sid, _ = sessions.create_session(user_id)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=sid,
        max_age=settings.SESSION_EXPIRE_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )


@router.post("/get")
async def get_schedule(req: GetScheduleRequest,
                       request: Request,
                       response: Response,
                       user: dict | None = Depends(optional_user)) -> dict:
    """抓取课表（登录用户 / 访客均可使用）。

    - 登录用户：课表绑定到 user_id
    - 访客：自动以学号创建账号（不保存密码），设置 Session Cookie，
      后续刷新页面通过 Cookie 直接加载自己的课表，无需额外登录
    """
    _set_no_cache(response)
    student_id = req.student_id.strip()
    if not student_id or not req.password:
        raise HTTPException(400, "请输入学号和密码")

    if user:
        uid = user["uid"]
    else:
        # 访客：自动创建/查找以学号为 username 的用户
        uid = await asyncio.to_thread(_get_or_create_guest_user, student_id)
        # 设置 Session Cookie，让用户后续免登录访问课表
        await asyncio.to_thread(_set_session_cookie, response, uid, request)

    try:
        result = await service.fetch_schedule(uid, student_id, req.password, req.force)
        # 返回 user_id 给前端，方便后续直接通过 view/{user_id} 查看
        result["user_id"] = uid
        return result
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


# ===================== 教务工具箱 API 路由 =====================


@router.post("/grades")
async def get_grades(req: GradesQueryRequest, response: Response) -> dict:
    """查询个人各学期成绩与平均学分绩点(GPA)。"""
    _set_no_cache(response)
    sid = req.student_id.strip()
    if not sid or not req.password:
        raise HTTPException(400, "请输入学号和密码")
    try:
        data = await asyncio.to_thread(
            toolbox.execute_with_login,
            sid,
            req.password,
            toolbox.get_grades,
            req.semester,
            req.display_mode,
        )
        return data
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("Failed to fetch grades: %s", e)
        raise HTTPException(502, "教务系统成绩查询暂时不可用")


@router.post("/exams")
async def get_exams(req: ExamsQueryRequest, response: Response) -> list:
    """查询个人考试日程、考场与座位号。"""
    _set_no_cache(response)
    sid = req.student_id.strip()
    if not sid or not req.password:
        raise HTTPException(400, "请输入学号和密码")
    try:
        data = await asyncio.to_thread(
            toolbox.execute_with_login,
            sid,
            req.password,
            toolbox.get_exams,
            req.semester,
            req.category,
        )
        return data
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("Failed to fetch exams: %s", e)
        raise HTTPException(502, "教务系统考试查询暂时不可用")


@router.post("/classrooms")
async def get_free_classrooms(req: ClassroomQueryRequest, response: Response) -> list:
    """查询指定时段空闲自习教室。"""
    _set_no_cache(response)
    sid = req.student_id.strip()
    if not sid or not req.password:
        raise HTTPException(400, "请输入学号和密码")
    try:
        data = await asyncio.to_thread(
            toolbox.execute_with_login,
            sid,
            req.password,
            toolbox.get_free_classrooms,
            req.semester,
            req.building,
            req.week,
            req.day,
            req.start_period,
            req.end_period,
        )
        return data
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("Failed to fetch classrooms: %s", e)
        raise HTTPException(502, "教务系统教室查询暂时不可用")


@router.post("/training_plan")
async def get_training_plan(req: ToolboxAuthRequest, response: Response) -> list:
    """查询大学四年培养方案与必修/选修课程列表。"""
    _set_no_cache(response)
    sid = req.student_id.strip()
    if not sid or not req.password:
        raise HTTPException(400, "请输入学号和密码")
    try:
        data = await asyncio.to_thread(
            toolbox.execute_with_login,
            sid,
            req.password,
            toolbox.get_training_plan,
        )
        return data
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("Failed to fetch training plan: %s", e)
        raise HTTPException(502, "教务系统培养方案查询暂时不可用")


@router.post("/level_exams")
async def get_level_exams(req: ToolboxAuthRequest, response: Response) -> list:
    """查询大学英语四六级等社会等级考试成绩。"""
    _set_no_cache(response)
    sid = req.student_id.strip()
    if not sid or not req.password:
        raise HTTPException(400, "请输入学号和密码")
    try:
        data = await asyncio.to_thread(
            toolbox.execute_with_login,
            sid,
            req.password,
            toolbox.get_level_exams,
        )
        return data
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("Failed to fetch level exams: %s", e)
        raise HTTPException(502, "教务系统等级考试查询暂时不可用")

