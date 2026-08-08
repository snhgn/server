# -*- coding: utf-8 -*-
"""种子脚本：解析 captcha_solver/timetable.html -> course_app/courses.db。

用法：
    python seed.py            # 全量重建（清空后导入）
    python seed.py --dry      # 只解析打印，不写库
"""
import argparse
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "captcha_solver"))

import database  # noqa: E402
from parse_timetable import parse_grid, merge_adjacent  # noqa: E402

HTML_FILE = os.path.join(ROOT_DIR, "captcha_solver", "timetable.html")


def parse_weeks(ws):
    """解析周次字符串 -> (weeks 列表, week_type)。

    支持格式：
        "1(周)"                    每周第1周
        "1-8,10-14(周)"            每周，断裂周次
        "1-16(单周)" / "2-16(双周)" 单双周
        "10,12-13(周)"             每周，混合段
    """
    ws = ws.strip()
    wtype = "all"
    if "单" in ws:
        wtype = "odd"
    elif "双" in ws:
        wtype = "even"
    ws = re.sub(r"[（(][^）)]*[）)]", "", ws)  # 去掉 (周)/(单周) 后缀
    weeks = []
    for part in ws.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            weeks.extend(range(int(a), int(b) + 1))
        else:
            weeks.append(int(part))
    weeks = sorted(set(weeks))
    if not weeks:  # 兜底：解析失败视为第1周
        weeks = [1]
    return weeks, wtype


def parse_period(p):
    """解析 "第3-4节" / "第5节" / "第10-12节" -> (start, end)。"""
    m = re.search(r"第(\d+)(?:-(\d+))?节", p)
    a = int(m.group(1))
    b = int(m.group(2)) if m.group(2) else a
    return a, b


def build_courses():
    """解析课表 HTML 为课程 dict 列表（与接口 JSON 同构）。"""
    if not os.path.isfile(HTML_FILE):
        raise SystemExit(f"未找到课表文件: {HTML_FILE}\n请先运行 captcha_solver 抓取课表")
    html = open(HTML_FILE, encoding="utf-8").read()
    rows = merge_adjacent(parse_grid(html))
    if not rows:
        raise SystemExit("课表为空（可能该学期未公布），请先抓取有数据的课表")
    courses = []
    for r in rows:
        weeks, wtype = parse_weeks(r["weeks"])
        a, b = parse_period(r["period"])
        courses.append({
            "name": r["name"],
            "teacher": r["teacher"],
            "location": r["room"],
            "weekday": r["day"],
            "start_section": a,
            "end_section": b,
            "week_type": wtype,
            "start_week": min(weeks),
            "end_week": max(weeks),
            "weeks": weeks,
        })
    return courses


def main():
    parser = argparse.ArgumentParser(description="导入课表到 SQLite")
    parser.add_argument("--dry", action="store_true", help="只解析不写库")
    args = parser.parse_args()

    courses = build_courses()
    print(f"解析到 {len(courses)} 条课程记录")
    if args.dry:
        for c in courses[:5]:
            print(" ", c["name"], c["weekday"], c["start_section"],
                  c["weeks"], c["teacher"], c["location"])
        return

    database.init_db()
    database.clear_courses()
    for c in courses:
        database.insert_course(c)
    print(f"已导入 {len(courses)} 条 -> {database.DB_PATH}")


if __name__ == "__main__":
    main()
