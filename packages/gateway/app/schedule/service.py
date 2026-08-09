# -*- coding: utf-8 -*-
"""课表抓取编排：缓存 → 冷却 → per-user 锁 → 线程池爬取 → 写缓存。

安全约束（贯穿实现）：
- 学号/密码/cookie/session 只存在于请求生命周期内存中，绝不落盘、绝不写日志；
- 爬取会话在 finally 中立即关闭；
- 日志只记录 user_id 与错误类别，不记录任何凭据。
"""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone

from ..config import settings
from . import captcha, course_context, db, parse_timetable

logger = logging.getLogger("gateway.schedule")

# 节次字符串 → (开始节, 结束节)，由解析代码归一化后的节次名映射
PERIOD_RANGE = {
    "第1-2节": (1, 2),
    "第3-4节": (3, 4),
    "第5节": (5, 5),
    "第6-7节": (6, 7),
    "第8-9节": (8, 9),
    "第10-11节": (10, 11),
    "第10-12节": (10, 12),
    "第12节": (12, 12),
}

# per-user 并发锁 + 冷却时间戳（仅进程内，重启即失效，可接受）
_locks: dict[int, asyncio.Lock] = {}
_cooldowns: dict[int, float] = {}


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

    返回 (semester, courses)。失败抛 ScheduleError；会话在 finally 中销毁。
    """
    session = None
    try:
        ok, session, reason = captcha.login(
            student_id, password,
            max_retry=settings.SCHEDULE_CAPTCHA_MAX_RETRY, verbose=False,
        )
        if not ok:
            raise ScheduleError(*_login_error(reason))

        html0 = captcha.get_timetable(session)
        courses = parse_timetable.merge_adjacent(parse_timetable.parse_grid(html0))
        semester = _current_semester(html0)
        if not courses:
            # 默认学期无课表：按学期下拉依次轮询，取第一个有课表的学期
            sems = parse_timetable.extract_selects(html0).get("xnxq01id", [])
            for value, text in sems:
                if not value:
                    continue
                html = parse_timetable.fetch_semester(session, value)
                rows = parse_timetable.merge_adjacent(parse_timetable.parse_grid(html))
                if rows:
                    courses = rows
                    semester = text
                    break
            else:
                raise ScheduleError(400, "当前学期暂无课表数据")

        out = []
        for c in courses:
            start, end = PERIOD_RANGE.get(c.get("period", ""), (0, 0))
            out.append({
                "name": c.get("name", ""),
                "teacher": c.get("teacher", ""),
                "room": c.get("room", ""),
                "weeks": c.get("weeks", ""),
                "day": c.get("day", 0),
                "period": c.get("period", ""),
                "start": start,
                "end": end,
            })
        return semester, out
    except ScheduleError:
        raise
    except Exception as e:
        # 只记错误类别，不记录任何学号/密码信息
        logger.warning("schedule crawl error: %s", type(e).__name__)
        raise ScheduleError(502, "教务系统暂时不可用，请稍后重试")
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass


async def fetch_schedule(user_id: int, student_id: str, password: str,
                         force: bool = False) -> dict:
    """获取课表：优先返回新鲜缓存；否则爬取并写缓存。

    - 非 force 且缓存新鲜 → 直接返回（不访问教务系统）
    - 冷却期内拒绝重复爬取（429）
    - per-user 锁保证并发重复请求只爬一次
    """
    if not force:
        row = db.get_cache(user_id)
        if row and _is_fresh(row["updated_time"]):
            return json.loads(row["schedule_json"])

    last = _cooldowns.get(user_id, 0.0)
    if time.monotonic() - last < settings.SCHEDULE_COOLDOWN_SECONDS:
        raise ScheduleError(429, "操作太频繁，请稍后再试")

    lock = _locks.setdefault(user_id, asyncio.Lock())
    async with lock:
        # 加锁后再查一次：并发请求共享同一次爬取
        if not force:
            row = db.get_cache(user_id)
            if row and _is_fresh(row["updated_time"]):
                return json.loads(row["schedule_json"])

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
        db.upsert_cache(user_id, semester, json.dumps(payload, ensure_ascii=False), updated)

        # 同步到 courses 表 + AI 数据目录（失败不阻断主流程，由每日任务兜底重试）
        try:
            await asyncio.to_thread(course_context.sync_from_cache, user_id, "manual")
        except Exception as exc:
            logger.warning("course sync after fetch failed user=%s: %s",
                           user_id, str(exc)[:200])

        return payload


def get_current(user_id: int) -> dict | None:
    """返回缓存课表（不论新旧）；无缓存返回 None。"""
    row = db.get_cache(user_id)
    return json.loads(row["schedule_json"]) if row else None


def list_cache_stats() -> list[dict]:
    """管理端统计：仅含 user_id / semester / updated_time，不含任何课表详情。"""
    return db.list_caches()
