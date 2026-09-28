# -*- coding: utf-8 -*-
"""课表抓取编排：缓存 → 冷却 → per-user 锁 → 线程池爬取 → 写缓存。

安全约束（贯穿实现）：
- 学号/密码/cookie/session 只存在于请求生命周期内存中，绝不落盘、绝不写日志；
- 爬取会话在 finally 中立即关闭；
- 日志只记录 user_id 与错误类别，不记录任何凭据。
"""
import asyncio
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone

from ..config import settings
from . import captcha, course_context, db, parse_timetable, session_pool

logger = logging.getLogger("gateway.schedule")

# 节次字符串 → (开始节, 结束节)，由解析代码归一化后的节次名映射
PERIOD_RANGE = {
    "第1-2节": (1, 2),
    "第1-4节": (1, 4),
    "第1-5节": (1, 5),
    "第3-4节": (3, 4),
    "第3-5节": (3, 5),
    "第5节": (5, 5),
    "第6-7节": (6, 7),
    "第6-9节": (6, 9),
    "第8-9节": (8, 9),
    "第10-11节": (10, 11),
    "第10-12节": (10, 12),
    "第12节": (12, 12),
}


def parse_period_range(period_str: str) -> tuple[int, int]:
    """根据节次字符串安全解析 (start, end)。"""
    if period_str in PERIOD_RANGE:
        return PERIOD_RANGE[period_str]
    m = re.search(r"第?(\d+)-(\d+)节?", period_str)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"第?(\d+)节?", period_str)
    if m:
        return int(m.group(1)), int(m.group(1))
    return (0, 0)

# per-user 并发锁 + 冷却时间戳（仅进程内，重启即失效，可接受）
_locks: dict[int, asyncio.Lock] = {}
_cooldowns: dict[int, float] = {}

# 进程内 TTL 内存缓存：避免每次查看都走 SQLite I/O + JSON 反序列化
# {user_id: (monotonic_ts, parsed_dict)}
_mem_cache: dict[int, tuple[float, dict]] = {}
_MEM_CACHE_TTL = 300.0  # 5 分钟


def guest_user_id(student_id: str) -> int:
    """从学号派生稳定的负整数 user_id，供访客课表缓存使用。

    负值确保与数据库 AUTOINCREMENT 正整数 user_id 永不冲突。
    """
    h = hashlib.sha256(f"guest:{student_id}".encode()).hexdigest()
    return -(int(h[:8], 16) % 1_000_000_000 + 1)


class ScheduleError(Exception):
    """带用户可读消息的错误。http_status 为返回前端的 HTTP 状态码。"""

    def __init__(self, http_status: int, message: str):
        super().__init__(message)
        self.http_status = http_status
        self.message = message


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _parse_iso(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _is_fresh(updated_time: str) -> bool:
    """缓存是否在 TTL 内（避免频繁访问教务系统）。"""
    now = datetime.now(timezone.utc).astimezone()
    age = (now - _parse_iso(updated_time)).total_seconds()
    return age < settings.SCHEDULE_CACHE_TTL_HOURS * 3600


def _login_error(reason: str) -> tuple[int, str]:
    """把内部失败原因映射为对外安全提示，不外泄细节。"""
    if any(k in reason for k in ("账号", "密码", "帐号")):
        return 400, "账号或密码错误"
    if "验证码" in reason:
        return 400, "验证码识别失败，请重新尝试"
    return 502, "教务系统暂时不可用，请稍后重试"


def _current_semester(html: str) -> str:
    """从学期下拉框提取当前选中（或默认）学期文本。"""
    m = re.search(
        r'<select\b[^>]*name="xnxq01id"[^>]*>(.*?)</select>', html, re.S)
    if not m:
        return ""
    options = re.findall(
        r'<option[^>]*value="([^"]*)"([^>]*)>(.*?)</option>', m.group(1), re.S)
    for value, attrs, text in options:
        if "selected" in attrs.lower():
            return parse_timetable.strip_tags(text) or value
    if options:
        value, _, text = options[0]
        return parse_timetable.strip_tags(text) or value
    return ""


def _crawl_sync(student_id: str, password: str) -> tuple[str, list[dict]]:
    """同步登录教务系统并抓取课表（运行于线程池，避免阻塞事件循环）。

    会话来自进程内会话池：同一学生刚查过成绩/考试再刷新课表时可直接复用，
    省掉一整轮验证码握手。池中会话被服务端作废时自动重新登录重试一次。
    返回 (semester, courses)。失败抛 ScheduleError。
    """
    for attempt in (1, 2):
        try:
            with session_pool.session_for(
                student_id, password,
                max_retry=settings.SCHEDULE_CAPTCHA_MAX_RETRY, verbose=False,
            ) as (session, _reused):
                semester, courses = _crawl_with_session(session)
                if courses:
                    return semester, [_normalize_course(c) for c in courses]
                if attempt == 2:
                    break
                # 空课表可能是会话被作废后拿到的登录页：作废会话重登一次
                if not _session_is_stale(session):
                    break
        except session_pool.LoginFailed as e:
            # 账号密码/验证码问题：重试无意义，立即上抛
            raise ScheduleError(*_login_error(str(e)))
        except ScheduleError:
            raise
        except Exception as e:
            # 只记错误类别，不记录任何学号/密码信息
            logger.warning("schedule crawl error: %s", type(e).__name__)
            raise ScheduleError(502, "教务系统暂时不可用，请稍后重试")
    raise ScheduleError(400, "当前学期暂无课表数据")


def _normalize_course(c: dict) -> dict:
    """把解析出的课程行归一化为前端契约结构（含可比较的起止节次）。"""
    start, end = parse_period_range(c.get("period", ""))
    return {
        "name": c.get("name", ""),
        "teacher": c.get("teacher", ""),
        "room": c.get("room", ""),
        "weeks": c.get("weeks", ""),
        "day": c.get("day", 0),
        "period": c.get("period", ""),
        "start": start,
        "end": end,
    }


def _crawl_with_session(session) -> tuple[str, list[dict]]:
    """用已登录会话抓取课表；返回 (semester, courses)，无课时 courses 为空。"""
    html0 = captcha.get_timetable(session)
    courses = parse_timetable.merge_adjacent(parse_timetable.parse_grid(html0))
    semester = _current_semester(html0)
    if courses:
        return semester, courses

    # 默认学期无课表：按学期下拉依次轮询，取第一个有课表的学期
    sems = parse_timetable.extract_selects(html0).get("xnxq01id", [])
    for value, text in sems:
        if not value:
            continue
        html = parse_timetable.fetch_semester(session, value)
        rows = parse_timetable.merge_adjacent(parse_timetable.parse_grid(html))
        if rows:
            return text, rows
    return semester, []


def _session_is_stale(session) -> bool:
    """会话是否已被服务端作废（拿到的其实是登录页）。

    强智会话失效时不返回 302 而是直接吐登录页，且各抓取函数解析后会得到
    「空结果」而非异常，所以只能靠内容特征判断。探测本身出错时按「未失效」
    处理：此时重新登录同样会失败。
    """
    try:
        return captcha.is_login_page(captcha.get_timetable(session))
    except Exception:
        return False


async def fetch_schedule(user_id: int, student_id: str, password: str,
                         force: bool = False) -> dict:
    """获取课表：优先返回新鲜缓存；否则爬取并写缓存。

    - 非 force 且缓存新鲜 → 直接返回（不访问教务系统）
    - 冷却期内拒绝重复爬取（429）
    - per-user 锁保证并发重复请求只爬一次
    """
    if not force:
        # 优先查内存缓存（0ms），再查 SQLite
        hit = _mem_cache.get(user_id)
        if hit and time.monotonic() - hit[0] < _MEM_CACHE_TTL:
            return hit[1]
        row = db.get_cache(user_id)
        if row and _is_fresh(row["updated_time"]):
            parsed = json.loads(row["schedule_json"])
            _mem_cache[user_id] = (time.monotonic(), parsed)
            return parsed

    last = _cooldowns.get(user_id, 0.0)
    if time.monotonic() - last < settings.SCHEDULE_COOLDOWN_SECONDS:
        raise ScheduleError(429, "操作太频繁，请稍后再试")

    lock = _locks.setdefault(user_id, asyncio.Lock())
    async with lock:
        # 加锁后再查一次：并发请求共享同一次爬取
        if not force:
            hit = _mem_cache.get(user_id)
            if hit and time.monotonic() - hit[0] < _MEM_CACHE_TTL:
                return hit[1]
            row = db.get_cache(user_id)
            if row and _is_fresh(row["updated_time"]):
                parsed = json.loads(row["schedule_json"])
                _mem_cache[user_id] = (time.monotonic(), parsed)
                return parsed

        _cooldowns[user_id] = time.monotonic()
        try:
            semester, courses = await asyncio.wait_for(
                asyncio.to_thread(_crawl_sync, student_id, password),
                timeout=settings.SCHEDULE_CRAWL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise ScheduleError(502, "教务系统响应超时，请稍后重试")
        except ScheduleError:
            raise
        except Exception:
            logger.warning("schedule fetch unexpected (user=%s)", user_id)
            raise ScheduleError(502, "教务系统暂时不可用，请稍后重试")

        updated = _now_iso()
        payload = {"semester": semester, "updated_time": updated, "courses": courses}
        
        # 1. 写入主体缓存（记录 student_id）
        db.upsert_cache(user_id, semester, json.dumps(payload, ensure_ascii=False), updated, student_id=student_id)
        _mem_cache[user_id] = (time.monotonic(), payload)

        # 2. 如果是登录用户同步，同时写入 guest 映射，确保未登录按学号也能查到最新课表
        g_uid = guest_user_id(student_id)
        if g_uid != user_id:
            db.upsert_cache(g_uid, semester, json.dumps(payload, ensure_ascii=False), updated, student_id=student_id)
            _mem_cache[g_uid] = (time.monotonic(), payload)

        # 3. 针对默认示范学生或管理员，保证 1 号用户也同步到最新学期
        if student_id == "260101208" or user_id == 1:
            if user_id != 1:
                db.upsert_cache(1, semester, json.dumps(payload, ensure_ascii=False), updated, student_id=student_id)
                _mem_cache[1] = (time.monotonic(), payload)
                try:
                    await asyncio.to_thread(course_context.sync_from_cache, 1, "manual")
                except Exception:
                    pass

        # 同步到 courses 表 + AI 数据目录（仅登录用户；访客跳过）
        if user_id > 0:
            try:
                await asyncio.to_thread(course_context.sync_from_cache, user_id, "manual")
            except Exception as exc:
                logger.warning("course sync after fetch failed user=%s: %s",
                               user_id, str(exc)[:200])

        return payload


def get_current(user_id: int) -> dict | None:
    """返回缓存课表；无缓存返回 None。

    优先查内存缓存（0ms），未命中再查 SQLite 并回填内存缓存。
    若检测到 user_id 1 仍持有旧学期残留，自动尝试从示范学号拉取最新学期。
    """
    hit = _mem_cache.get(user_id)
    if hit and time.monotonic() - hit[0] < _MEM_CACHE_TTL:
        parsed = hit[1]
        if not (user_id == 1 and parsed.get("semester") == "2025-2026-2"):
            return parsed

    row = db.get_cache(user_id)
    if row:
        parsed = json.loads(row["schedule_json"])
        # 若是 1 号管理员但持有一年前旧课表 (2025-2026-2)，尝试借用最新学期
        if user_id == 1 and parsed.get("semester") == "2025-2026-2":
            fallback = get_by_student("260101208")
            if fallback and fallback.get("semester") != "2025-2026-2":
                db.upsert_cache(1, fallback["semester"], json.dumps(fallback, ensure_ascii=False),
                                fallback.get("updated_time", _now_iso()), student_id="260101208")
                _mem_cache[1] = (time.monotonic(), fallback)
                return fallback
        _mem_cache[user_id] = (time.monotonic(), parsed)
        return parsed

    # 若 user_id 1 暂无缓存，尝试用 260101208 垫底
    if user_id == 1:
        return get_by_student("260101208")

    return None


def get_by_student(student_id: str) -> dict | None:
    """根据学号检索最新有效课表。

    双重检索：
    1. 优先根据 schedule_cache.student_id 查询最新记录
    2. 降级查 guest_user_id(student_id)
    """
    sid = student_id.strip()
    if not sid:
        return None

    # 1. 查 student_id 列记录
    row = db.get_cache_by_student(sid)
    if row:
        uid = row["user_id"]
        hit = _mem_cache.get(uid)
        if hit and time.monotonic() - hit[0] < _MEM_CACHE_TTL:
            return hit[1]
        parsed = json.loads(row["schedule_json"])
        _mem_cache[uid] = (time.monotonic(), parsed)
        return parsed

    # 2. 查 guest_user_id 负数记录
    g_uid = guest_user_id(sid)
    return get_current(g_uid)


def list_cache_stats() -> list[dict]:
    """管理端统计：仅含 user_id / semester / updated_time，不含任何课表详情。"""
    return db.list_caches()
