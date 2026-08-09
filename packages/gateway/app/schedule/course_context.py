# -*- coding: utf-8 -*-
"""课程数据同步服务：schedule_cache → courses 表 → 用户专属 AI 数据目录。

数据流（唯一来源原则）：
    教务系统抓取 → schedule_cache → 本模块同步 → courses 表 + AI 数据目录
    （网页课表 / AI 查询 全部基于 courses 表与 AI 目录，不另存数据）

AI 数据目录结构（settings.COURSE_DATA_DIR 下）：
    users/user_{user_id}/
        course.json          程序精确查询用（结构化）
        course_context.txt   自然语言上下文（供 LLM）
        course_summary.json  精确结构化摘要（供 AI 内部函数）

变化检测：对规范化课程计算 hash；hash 相同则不重写文件、不更新状态。
"""
import hashlib
import json
import logging
import re
from pathlib import Path

from ..config import settings
from . import course_db, db as cache_db

logger = logging.getLogger("gateway.schedule.course_context")

# 学校官方上课时间（来自上课时间表）：节次区间 → 起止时间
PERIOD_SLOTS = [
    (1, 2, "08:00", "09:35"),
    (3, 4, "09:50", "11:25"),
    (5, 5, "11:25", "12:15"),
    (6, 7, "13:30", "15:05"),
    (8, 9, "15:20", "16:55"),
    (10, 11, "18:30", "20:05"),
    (12, 12, "20:10", "20:55"),
]
DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 节次范围 → 时间范围（用于"第1-4节"这类跨区间课程）
_MIN_START = {1: "08:00", 3: "09:50", 5: "11:25", 6: "13:30", 8: "15:20", 10: "18:30", 12: "20:10"}
_MAX_END = {2: "09:35", 4: "11:25", 5: "12:15", 7: "15:05", 9: "16:55", 11: "20:05", 12: "20:55"}


def time_range(start: int, end: int) -> str:
    """节次区间 → 时间区间字符串（如 第1-2节 → 08:00-09:35）。"""
    for s, e, st, et in PERIOD_SLOTS:
        if start >= s and end <= e:
            return f"{st}-{et}"
    # 跨多个官方区间（如 1-4 节）：取最早开始、最晚结束
    b = _MIN_START.get(start) or "00:00"
    f = _MAX_END.get(end) or "23:59"
    return f"{b}-{f}"


def parse_weeks(weeks: str) -> tuple[int, int]:
    """解析周次字符串（如 '1-16周' / '1-8,10-16周'）→ (start_week, end_week)。

    多段周次取最小开始、最大结束（保守覆盖）。
    """
    nums = [int(x) for x in re.findall(r"\d+", weeks or "")]
    if not nums:
        return 1, 1
    return min(nums), max(nums)


def term_label(semester: str) -> str:
    """'2026-2027学年第一学期' → '2026秋'；解析失败保留原文。"""
    if not semester:
        return ""
    m = re.search(r"(20\d{2})\s*[-—–]\s*20\d{2}学年[^\d]*?第([一二三1-3])学期", semester)
    if m:
        year = m.group(1)
        nth = m.group(2)
        season = {"一": "秋", "1": "秋", "二": "春", "2": "春", "三": "夏", "3": "夏"}.get(nth, "")
        return f"{year}{season}"
    return semester


def _courses_hash(rows: list[dict]) -> str:
    """对规范化课程计算稳定 hash（用于变化检测）。"""
    normalized = [
        {k: r.get(k) for k in
         ("course_name", "teacher", "location", "weekday", "start_section",
          "end_section", "start_week", "end_week")}
        for r in rows
    ]
    blob = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _normalize(semester: str, courses: list[dict]) -> list[dict]:
    """把 service 层抓取结果规范化为 courses 行。"""
    rows: list[dict] = []
    for c in courses:
        start_week, end_week = parse_weeks(c.get("weeks", ""))
        rows.append({
            "course_name": c.get("name", "").strip(),
            "teacher": c.get("teacher", "").strip(),
            "location": c.get("room", "").strip(),
            "weekday": int(c.get("day", 0)),
            "start_section": int(c.get("start", 0)),
            "end_section": int(c.get("end", 0)),
            "start_week": start_week,
            "end_week": end_week,
        })
    # 过滤无效行（缺课程名或 weekday 越界）
    return [r for r in rows if r["course_name"] and 1 <= r["weekday"] <= 7]


# ---------- AI 数据目录生成 ----------


def _user_dir(user_id: int) -> Path:
    d = Path(settings.COURSE_DATA_DIR) / "users" / f"user_{user_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_course_json(user_dir: Path, user_id: int, semester: str, rows: list[dict]) -> None:
    """course.json：程序精确查询。"""
    label = term_label(semester)
    data = {
        "user_id": str(user_id),
        "semester": semester,
        "term_label": label,
        "courses": [
            {
                "name": r["course_name"],
                "teacher": r["teacher"],
                "location": r["location"],
                "weekday": DAY_NAMES[r["weekday"] - 1],
                "time": f"第{'' if r['start_section'] == r['end_section'] else str(r['start_section']) + '-'}{r['end_section']}节"
                        if r["start_section"] != r["end_section"]
                        else f"第{r['start_section']}节",
                "weeks": f"{r['start_week']}-{r['end_week']}周"
                        if r["start_week"] != r["end_week"]
                        else f"{r['start_week']}周",
            }
            for r in rows
        ],
    }
    (user_dir / "course.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_context_txt(user_dir: Path, semester: str, rows: list[dict]) -> None:
    """course_context.txt：自然语言上下文，供 LLM 阅读。"""
    label = term_label(semester)
    lines = [f"用户当前学期课程信息（{label or semester}）：", ""]
    by_day: dict[int, list[dict]] = {}
    for r in rows:
        by_day.setdefault(r["weekday"], []).append(r)
    for day in sorted(by_day):
        lines.append(f"{DAY_NAMES[day - 1]}：")
        for r in sorted(by_day[day], key=lambda x: x["start_section"]):
            tr = time_range(r["start_section"], r["end_section"])
            weeks = f"{r['start_week']}-{r['end_week']}周" if r["start_week"] != r["end_week"] else f"{r['start_week']}周"
            part = f"  {tr}  {r['course_name']}"
            if r["location"]:
                part += f"  地点 {r['location']}"
            if r["teacher"]:
                part += f"  教师 {r['teacher']}"
            part += f"（第{'' if r['start_section'] == r['end_section'] else str(r['start_section']) + '-'}{r['end_section']}节，{weeks}）"
            lines.append(part)
        lines.append("")
    # 统计：哪些天没课、主要集中时段
    busy_days = sorted(by_day)
    free_days = [d for d in range(1, 8) if d not in by_day]
    if free_days:
        lines.append(f"每周没有课的天：{'、'.join(DAY_NAMES[d - 1] for d in free_days)}。")
    if busy_days:
        lines.append(f"课程主要集中在{'、'.join(DAY_NAMES[d - 1] for d in busy_days)}。")
    lines.append("")
    lines.append("可据此回答：今天有什么课、下一节课是什么、某课程在哪里、哪天没有课、本周空闲时间。")
    (user_dir / "course_context.txt").write_text("\n".join(lines), encoding="utf-8")


def _write_summary_json(user_dir: Path, user_id: int, semester: str, rows: list[dict]) -> None:
    """course_summary.json：AI 内部函数精确查询用。"""
    summary = {
        "user_id": user_id,
        "semester": semester,
        "term_label": term_label(semester),
        "day_names": DAY_NAMES,
        "courses": [
            {
                "name": r["course_name"],
                "teacher": r["teacher"],
                "location": r["location"],
                "weekday": r["weekday"],            # 1-7
                "day_name": DAY_NAMES[r["weekday"] - 1],
                "start": r["start_section"],
                "end": r["end_section"],
                "period": f"第{'' if r['start_section'] == r['end_section'] else str(r['start_section']) + '-'}{r['end_section']}节",
                "weeks": (f"{r['start_week']}-{r['end_week']}周" if r["start_week"] != r["end_week"]
                          else f"{r['start_week']}周"),
                "start_week": r["start_week"],
                "end_week": r["end_week"],
                "time_range": time_range(r["start_section"], r["end_section"]),
            }
            for r in sorted(rows, key=lambda x: (x["weekday"], x["start_section"]))
        ],
    }
    (user_dir / "course_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- 同步主流程 ----------


def sync_from_cache(user_id: int, sync_type: str = "auto") -> dict:
    """从 schedule_cache 同步到 courses 表 + AI 数据目录。

    返回 {"changed": bool, "status": "success"|"failed"|"skipped", "reason": str}。
    - hash 相同 → skipped（不重写文件、不更新数据）
    - hash 不同 → 更新 courses 表 + 重写三个 AI 文件
    """
    row = cache_db.get_cache(user_id)
    if not row:
        course_db.upsert_status(user_id, semester="", data_hash="", sync_status="failed",
                                last_error="no-cache", sync_type=sync_type)
        return {"changed": False, "status": "failed", "reason": "no-cache"}

    try:
        payload = json.loads(row["schedule_json"])
        semester = payload.get("semester", row["semester"]) or ""
        rows = _normalize(semester, payload.get("courses") or [])
    except Exception as exc:
        logger.warning("course sync parse failed user=%s: %s", user_id, str(exc)[:200])
        course_db.upsert_status(user_id, semester="", data_hash="", sync_status="failed",
                                last_error="parse-error", sync_type=sync_type)
        return {"changed": False, "status": "failed", "reason": "parse-error"}

    data_hash = _courses_hash(rows)
    prev = course_db.get_status(user_id)

    if prev and prev.get("data_hash") == data_hash and prev.get("sync_status") == "success":
        # 无变化：仅刷新同步时间，不重写文件
        course_db.upsert_status(user_id, semester=semester, data_hash=data_hash,
                                sync_status="success", sync_type=sync_type)
        return {"changed": False, "status": "skipped", "reason": "unchanged"}

    course_db.replace_courses(user_id, semester, rows)
    try:
        u_dir = _user_dir(user_id)
        _write_course_json(u_dir, user_id, semester, rows)
        _write_context_txt(u_dir, semester, rows)
        _write_summary_json(u_dir, user_id, semester, rows)
    except Exception as exc:
        # 数据库已更新，文件生成失败仍记录失败状态供重试
        logger.warning("course context write failed user=%s: %s", user_id, str(exc)[:200])
        course_db.upsert_status(user_id, semester=semester, data_hash=data_hash,
                                sync_status="failed", last_error="write-error",
                                sync_type=sync_type)
        return {"changed": True, "status": "failed", "reason": "write-error"}

    course_db.upsert_status(user_id, semester=semester, data_hash=data_hash,
                            sync_status="success", sync_type=sync_type)
    logger.info("course sync ok user=%s courses=%d changed=%s", user_id, len(rows), True)
    return {"changed": True, "status": "success", "reason": "updated"}


def sync_all_from_cache() -> list[dict]:
    """对全部有缓存课表的用户执行同步（定时任务用）。"""
    results = []
    for user_id in [c["user_id"] for c in cache_db.list_caches()]:
        try:
            results.append({"user_id": user_id, **sync_from_cache(user_id, sync_type="auto")})
        except Exception as exc:
            logger.warning("course sync all user=%s failed: %s", user_id, str(exc)[:200])
            results.append({"user_id": user_id, "changed": False,
                            "status": "failed", "reason": "unexpected"})
    return results
