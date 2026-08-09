# -*- coding: utf-8 -*-
"""课程数据 AI 内部函数（供 AI 助手直接调用，不新增 HTTP API）。

数据源：gateway 同步服务生成的用户专属 AI 数据目录
    {COURSE_DATA_DIR}/users/user_{user_id}/course_summary.json / course_context.txt

函数返回结构化数据，方便未来接入 Agent Function Calling：
    get_today_courses(user_id, date=None)  今天有什么课
    get_week_courses(user_id, week=None)   某周（默认本周）的课
    get_course_info(user_id, course_name)  某课程详情
    get_free_time(user_id)                 空闲时间分析
    get_schedule_context(user_id)          自然语言上下文（整段注入 prompt）

周次推算基于当前学期起止（与前端课表页同一套配置）。
"""
import json
import logging
from datetime import date, datetime
from pathlib import Path

from .config import settings

logger = logging.getLogger("ai-service.course_tools")

# 当前学期配置（与前端 ScheduleView.vue 保持一致，换学期时同步修改）
TERM_START = "2026-09-07"
TERM_END = "2027-01-15"
TERM_LABEL = "2026秋"

DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 学校官方节次时间（与 gateway 生成 summary 时一致）
PERIOD_SLOTS = [
    (1, 2, "08:00", "09:35"),
    (3, 4, "09:50", "11:25"),
    (5, 5, "11:25", "12:15"),
    (6, 7, "13:30", "15:05"),
    (8, 9, "15:20", "16:55"),
    (10, 11, "18:30", "20:05"),
    (12, 12, "20:10", "20:55"),
]


# ---------- 内部数据读取 ----------


def _summary_path(user_id: int) -> Path:
    return Path(settings.COURSE_DATA_DIR) / "users" / f"user_{user_id}" / "course_summary.json"


def _context_path(user_id: int) -> Path:
    return Path(settings.COURSE_DATA_DIR) / "users" / f"user_{user_id}" / "course_context.txt"


def _load_summary(user_id: int) -> dict | None:
    p = _summary_path(user_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("course summary load failed user=%s: %s", user_id, str(exc)[:150])
        return None


def current_week(d: date | None = None) -> int:
    """当前系统周（1 起）；学期前/后返回 0（表示非教学周）。"""
    d = d or date.today()
    start = datetime.strptime(TERM_START, "%Y-%m-%d").date()
    end = datetime.strptime(TERM_END, "%Y-%m-%d").date()
    if d < start or d > end:
        return 0
    return (d - start).days // 7 + 1


# ---------- 对外函数（返回结构化数据） ----------


def get_schedule_context(user_id: int) -> str:
    """返回课表自然语言上下文（供注入 prompt）；无数据返回空串。"""
    p = _context_path(user_id)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("course context read failed user=%s: %s", user_id, str(exc)[:150])
        return ""


def get_today_courses(user_id: int, d: date | None = None) -> dict:
    """今天（或指定日期）的课程列表。"""
    d = d or date.today()
    summary = _load_summary(user_id)
    if not summary:
        return {"has_schedule": False, "reason": "no-data"}
    weekday = d.isoweekday()  # 1-7
    week = current_week(d)
    courses = [
        c for c in summary["courses"]
        if c["weekday"] == weekday
        and (week == 0 or c["start_week"] <= week <= c["end_week"])
    ]
    return {
        "has_schedule": True,
        "term_label": summary.get("term_label") or summary.get("semester", ""),
        "date": d.isoformat(),
        "day_name": DAY_NAMES[weekday - 1],
        "week": week,
        "courses": [
            {"time": c["time_range"], "name": c["name"],
             "location": c["location"], "teacher": c["teacher"]}
            for c in courses
        ],
    }


def get_week_courses(user_id: int, week: int | None = None) -> dict:
    """指定周（默认当前周）的全部课程，按天分组。"""
    summary = _load_summary(user_id)
    if not summary:
        return {"has_schedule": False, "reason": "no-data"}
    w = week if week is not None else current_week()
    by_day: dict[int, list[dict]] = {}
    for c in summary["courses"]:
        if c["start_week"] <= w <= c["end_week"]:
            by_day.setdefault(c["weekday"], []).append(c)
    days = [
        {
            "day_name": DAY_NAMES[d - 1],
            "courses": [
                {"time": c["time_range"], "name": c["name"],
                 "location": c["location"], "teacher": c["teacher"]}
                for c in sorted(by_day[d], key=lambda x: x["start"])
            ],
        }
        for d in sorted(by_day)
    ]
    return {
        "has_schedule": True,
        "term_label": summary.get("term_label") or summary.get("semester", ""),
        "week": w,
        "days": days,
        "total_courses": sum(len(x["courses"]) for x in days),
    }


def get_course_info(user_id: int, course_name: str) -> dict:
    """按课程名精确/模糊查询（返回全部匹配项）。"""
    summary = _load_summary(user_id)
    if not summary:
        return {"has_schedule": False, "reason": "no-data"}
    name = (course_name or "").strip()
    if not name:
        return {"has_schedule": True, "found": False, "matches": []}
    matches = [
        c for c in summary["courses"] if name in c["name"] or c["name"] in name
    ]
    return {
        "has_schedule": True,
        "query": course_name,
        "found": bool(matches),
        "matches": [
            {"name": c["name"], "teacher": c["teacher"], "location": c["location"],
             "day_name": c["day_name"], "period": c["period"],
             "time": c["time_range"], "weeks": c["weeks"]}
            for c in matches
        ],
    }


def get_free_time(user_id: int) -> dict:
    """空闲时间分析：每天的空闲节次时段 + 全天无课的天。"""
    summary = _load_summary(user_id)
    if not summary:
        return {"has_schedule": False, "reason": "no-data"}

    # 每天被占用的节次集合
    busy: dict[int, set[int]] = {d: set() for d in range(1, 8)}
    for c in summary["courses"]:
        for sec in range(c["start"], c["end"] + 1):
            busy[c["weekday"]].add(sec)

    day_breakdown = []
    for d in range(1, 8):
        free = [
            {"period": f"第{'' if s == e else str(s) + '-'}{e}节", "time": f"{st}-{et}"}
            for s, e, st, et in PERIOD_SLOTS
            if not any(busy[d].__contains__(x) for x in range(s, e + 1))
        ]
        day_breakdown.append({
            "day_name": DAY_NAMES[d - 1],
            "free_slots": free,
            "fully_free": not busy[d],
        })

    return {
        "has_schedule": True,
        "term_label": summary.get("term_label") or summary.get("semester", ""),
        "free_days": [x["day_name"] for x in day_breakdown if x["fully_free"]],
        "day_breakdown": day_breakdown,
    }


def build_schedule_prompt(user_id: int, user_message: str) -> str:
    """根据用户消息意图，调用对应函数并组装为 prompt 片段。

    由 ai-service chat 调用；非课表问题返回空串。
    """
    msg = user_message or ""
    kw_today = ("今天有什么课", "今天的课", "今日课", "今天上什么", "今天有课")
    kw_week = ("这周", "本周", "这一周", "这周的课", "这周有")
    kw_course = ("在哪上", "在哪儿", "在哪", "哪个教室", "哪里上课", "上课地点",
                 "什么时候上", "课程信息", "这门课")
    kw_free = ("空闲", "没课", "没有课", "有空", "哪天没课", "什么时候休息", "什么时候有空")
    kw_schedule = ("课表", "我的课", "课程")

    # 精确意图优先
    if any(k in msg for k in kw_today):
        return _fmt("今天（{day_name}）的课程如下", get_today_courses(user_id))
    if any(k in msg for k in kw_free):
        return _fmt("用户的空闲时间分析如下", get_free_time(user_id))
    if any(k in msg for k in kw_week):
        return _fmt("本周（第 {week} 周）课程如下", get_week_courses(user_id))
    if any(k in msg for k in kw_course):
        return _fmt("查询课程信息结果如下", get_course_info(user_id, msg))
    if any(k in msg for k in kw_schedule):
        ctx = get_schedule_context(user_id)
        return f"用户课表（自然语言）：\n{ctx}" if ctx else ""
    return ""


def _fmt(prefix: str, data: dict) -> str:
    """把结构化结果转成 prompt 片段（AI 回答时引用）。"""
    if not data.get("has_schedule"):
        return "用户尚未同步课表数据，请提示用户先在教学网页获取课表。"
    return f"{prefix}：\n{json.dumps(data, ensure_ascii=False, indent=2)}"
