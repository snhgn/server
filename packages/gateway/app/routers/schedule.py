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
import json
import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from .. import sessions
from ..auth import invalidate_session_cache, optional_user, require_admin, require_user
from ..config import settings
from ..schedule import db as schedule_db, notifier, service, toolbox

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


# ===================== 4位邀请码课表共享 API 路由 =====================


class CreateShareRequest(BaseModel):
    student_id: str
    owner_name: str = ""
    regenerate: bool = False


@router.post("/share/create")
def create_share_code(req: CreateShareRequest, response: Response) -> dict:
    """生成或获取用户的4位共享课表邀请码（不泄露学号，不以学号直接绑定）。"""
    _set_no_cache(response)
    sid = req.student_id.strip()
    if not sid:
        raise HTTPException(400, "请提供学号以生成邀请码")

    # 优先查找该学生是否已有缓存课表
    cache = service.get_by_student(sid)
    if not cache:
        raise HTTPException(400, "尚未检索到您的课表，请先查询并保存个人课表后再生成邀请码")

    raw_cache = schedule_db.get_cache_by_student(sid)
    sched_json = raw_cache["schedule_json"] if raw_cache else json.dumps(cache.get("courses", []))
    sem = cache.get("semester") or "2026-2027-1"

    code = schedule_db.create_or_update_share(
        student_id=sid,
        owner_name=req.owner_name.strip(),
        schedule_json=sched_json,
        semester=sem,
        regenerate=req.regenerate,
    )
    return {
        "code": code,
        "owner_name": req.owner_name.strip(),
        "share_url": f"/schedule?code={code}",
    }


@router.get("/share/my")
def get_my_share_code(response: Response, student_id: str = Query(..., description="学号")) -> dict:
    """查询指定学号已生成的4位邀请码。"""
    _set_no_cache(response)
    sid = student_id.strip()
    if not sid:
        raise HTTPException(400, "请提供学号")
    share = schedule_db.get_share_by_student(sid)
    if not share:
        return {"has_code": False}
    return {
        "has_code": True,
        "code": share["code"],
        "owner_name": share["owner_name"],
        "share_url": f"/schedule?code={share['code']}",
    }


@router.get("/share/{code}")
def view_shared_schedule(code: str, response: Response) -> dict:
    """通过4位邀请码查看共享课表（完全不泄露分享者的学号）。"""
    _set_no_cache(response)
    c = code.strip().upper()
    if not c or len(c) != 4:
        raise HTTPException(404, "无效的4位邀请码")

    share = schedule_db.get_share_by_code(c)
    if not share:
        raise HTTPException(404, "邀请码不存在或已失效")

    # 尝试从该同学最新的 schedule_cache 读取最新课表，若无则使用分享快照
    sid = share["student_id"]
    latest_cache = service.get_by_student(sid) if sid else None

    if latest_cache and latest_cache.get("courses"):
        courses = latest_cache["courses"]
        sem = latest_cache.get("semester") or share["semester"]
        up_time = latest_cache.get("updated_time") or share["updated_at"]
    else:
        try:
            courses = json.loads(share["schedule_json"]) if share["schedule_json"] else []
        except Exception:
            courses = []
        sem = share["semester"]
        up_time = share["updated_at"]

    # 严格杜绝返回 student_id 或 real user_id，确保隐私彻底隔绝
    return {
        "code": share["code"],
        "owner_name": share["owner_name"] or "同学",
        "semester": sem,
        "updated_time": up_time,
        "courses": courses,
    }


# ================= 成绩出分监控与邮件通知 =================

class GradeMonitorSaveRequest(BaseModel):
    student_id: str
    email: str
    enabled: bool = True
    send_test: bool = True  # 保存时是否发送测试邮件，默认 True


class GradeMonitorTestRequest(BaseModel):
    student_id: str = ""
    email: str


@router.get("/monitor/get")
async def get_grade_monitor_api(
    response: Response,
    student_id: str = Query("", description="学号"),
):
    """获取指定学号的成绩监控配置。"""
    _set_no_cache(response)
    sid = student_id.strip()
    if not sid:
        return {"has_monitor": False}
    m = schedule_db.get_grade_monitor(sid)
    if not m:
        return {"has_monitor": False}
    return {
        "has_monitor": True,
        "email": m["email"],
        "enabled": bool(m["enabled"]),
        "updated_at": m["updated_at"],
    }


@router.post("/monitor/test")
async def send_grade_monitor_test_api(
    req: GradeMonitorTestRequest,
    response: Response,
):
    """发送出分监控测试邮件。"""
    _set_no_cache(response)
    email = req.email.strip()
    if not email:
        raise HTTPException(400, "请输入有效的接收邮箱")

    ok, msg = await asyncio.to_thread(notifier.send_test_grade_monitor_email, email, req.student_id)
    if not ok:
        raise HTTPException(400, msg)
    return {"success": True, "message": msg}


@router.post("/monitor/save")
async def save_grade_monitor_api(
    req: GradeMonitorSaveRequest,
    response: Response,
):
    """保存或更新成绩监控设置；若开启且填写了邮箱，默认自动发送一封测试邮件。"""
    _set_no_cache(response)
    sid = req.student_id.strip()
    email = req.email.strip()

    if req.enabled and not email:
        raise HTTPException(400, "开启监控必须提供有效的接收通知邮箱")

    if email and not notifier.validate_email_address(email):
        raise HTTPException(400, "邮箱地址格式无效，请检查")

    # 持久化存储
    schedule_db.save_grade_monitor(sid, email, req.enabled)

    # 若开启且要求发送测试邮件
    test_sent = False
    test_msg = ""
    if req.enabled and email and req.send_test:
        ok, test_msg = await asyncio.to_thread(notifier.send_test_grade_monitor_email, email, sid)
        test_sent = ok
        if not ok:
            return {
                "success": True,
                "email": email,
                "enabled": req.enabled,
                "test_email_sent": False,
                "message": f"设置已保存，但测试邮件发送失败：{test_msg}",
            }

    msg = f"监控设置已保存，测试邮件已发送至 {email}，请查收！" if test_sent else "成绩监控设置已保存"
    return {
        "success": True,
        "email": email,
        "enabled": req.enabled,
        "test_email_sent": test_sent,
        "message": msg,
    }


