# -*- coding: utf-8 -*-
"""北林教务系统 (强智) 工具箱功能抓取与解析模块：
- 成绩查询与绩点计算 (get_grades)
- 考试安排查询 (get_exams)
- 空闲教室查询 (get_free_classrooms)
- 培养方案与学分进度 (get_training_plan)
- 等级考试查询 (get_level_exams)
"""
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
import requests

from . import captcha

BASE_URL = "http://newjwxt.bjfu.edu.cn"


def get_grades(session: requests.Session, semester: str = "", display_mode: str = "all") -> Dict[str, Any]:
    """查询成绩并自动计算学分绩点与均分。
    
    Args:
        session: 已登录的 requests.Session
        semester: 学期代码，如 '2025-2026-2'，空字符串表示全部学期
        display_mode: 'all' 全部成绩，'max' 最高成绩
    """
    url = f"{BASE_URL}/jsxsd/kscj/cjcx_list"
    data = {
        "kksj": semester,
        "kcxz": "",
        "kcmc": "",
        "xsfs": display_mode,
    }
    headers = {"Referer": f"{BASE_URL}/jsxsd/kscj/cjcx_query?Ves632DSdyV=NEW_XSD_XJCJ"}
    r = session.post(url, data=data, headers=headers, timeout=15)
    soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "html.parser")
    table = soup.find("table", id="dataList") or soup.find("table")
    
    courses = []
    total_credits = 0.0
    total_points = 0.0
    total_score_sum = 0.0
    scored_credits = 0.0

    if table:
        for tr in table.find_all("tr")[1:]:
            tds = [td.text.strip() for td in tr.find_all("td")]
            if len(tds) >= 8:
                # 序号 开课学期 课程编号 课程名称 成绩 学分 总学时 课程属性 ...
                term = tds[1] if len(tds) > 1 else ""
                code = tds[2] if len(tds) > 2 else ""
                name = tds[3] if len(tds) > 3 else ""
                score_str = tds[4] if len(tds) > 4 else ""
                credit_str = tds[5] if len(tds) > 5 else "0"
                hours = tds[6] if len(tds) > 6 else ""
                attr = tds[7] if len(tds) > 7 else ""
                category = tds[10] if len(tds) > 10 else ""

                try:
                    credit = float(credit_str)
                except ValueError:
                    credit = 0.0

                try:
                    score = float(score_str)
                    # 北林绩点标准公式: (成绩 >= 60 ? (成绩 - 50) / 10 : 0)
                    gpa = max(0.0, (score - 50.0) / 10.0) if score >= 60 else 0.0
                    total_points += gpa * credit
                    total_score_sum += score * credit
                    scored_credits += credit
                except ValueError:
                    # 等级制判定 (优=95, 良=85, 中=75, 及格=65, 不及格=0)
                    grade_map = {"优": (95.0, 4.5), "优秀": (95.0, 4.5), "良": (85.0, 3.5), "良好": (85.0, 3.5),
                                 "中": (75.0, 2.5), "中等": (75.0, 2.5), "及格": (65.0, 1.5), "通过": (65.0, 1.5),
                                 "不及格": (0.0, 0.0), "不通过": (0.0, 0.0)}
                    if score_str in grade_map:
                        equiv_score, equiv_gpa = grade_map[score_str]
                        total_points += equiv_gpa * credit
                        total_score_sum += equiv_score * credit
                        scored_credits += credit

                total_credits += credit
                courses.append({
                    "term": term,
                    "code": code,
                    "name": name,
                    "score": score_str,
                    "credit": credit,
                    "hours": hours,
                    "attribute": attr,
                    "category": category,
                })

    avg_gpa = round(total_points / scored_credits, 2) if scored_credits > 0 else 0.0
    avg_score = round(total_score_sum / scored_credits, 1) if scored_credits > 0 else 0.0

    return {
        "courses": courses,
        "total_courses": len(courses),
        "total_credits": round(total_credits, 1),
        "avg_gpa": avg_gpa,
        "avg_score": avg_score,
    }


def get_exams(session: requests.Session, semester: str = "", category: str = "") -> List[Dict[str, str]]:
    """查询学生考试日程与安排。"""
    url = f"{BASE_URL}/jsxsd/xsks/xsksap_list"
    data = {
        "xnxqid": semester,
        "xqlb": category,
    }
    headers = {"Referer": f"{BASE_URL}/jsxsd/xsks/xsksap_query?Ves632DSdyV=NEW_XSD_KSBM"}
    r = session.post(url, data=data, headers=headers, timeout=15)
    soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "html.parser")
    table = soup.find("table", id="dataList") or soup.find("table")
    
    exams = []
    if table:
        for tr in table.find_all("tr")[1:]:
            tds = [td.text.strip() for td in tr.find_all("td")]
            if len(tds) >= 8:
                # 序号 考试场次 课程编号 课程名称 考试时间 考场 座位号 准考证号
                exams.append({
                    "batch": tds[1] if len(tds) > 1 else "",
                    "code": tds[2] if len(tds) > 2 else "",
                    "name": tds[3] if len(tds) > 3 else "",
                    "time": tds[4] if len(tds) > 4 else "",
                    "room": tds[5] if len(tds) > 5 else "",
                    "seat": tds[6] if len(tds) > 6 else "",
                    "ticket": tds[7] if len(tds) > 7 else "",
                })
    return exams


def get_training_plan(session: requests.Session) -> List[Dict[str, Any]]:
    """查询个人培养方案（全部学期要求修读课程列表及学分属性）。"""
    url = f"{BASE_URL}/jsxsd/pyfa/pyfa_query?Ves632DSdyV=NEW_XSD_PYGL"
    r = session.get(url, timeout=15)
    soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "html.parser")
    table = soup.find("table", id="dataList") or (soup.find_all("table")[1] if len(soup.find_all("table")) > 1 else None)
    
    plan = []
    if table:
        for tr in table.find_all("tr")[1:]:
            tds = [td.text.strip() for td in tr.find_all("td")]
            if len(tds) >= 7:
                # 序号 开课学期 课程编号 课程名称 开课单位 学分 总学时 课程属性
                plan.append({
                    "term": tds[1] if len(tds) > 1 else "",
                    "code": tds[2] if len(tds) > 2 else "",
                    "name": tds[3] if len(tds) > 3 else "",
                    "dept": tds[4] if len(tds) > 4 else "",
                    "credit": float(tds[5]) if len(tds) > 5 and tds[5].replace(".", "", 1).isdigit() else 0.0,
                    "hours": tds[6] if len(tds) > 6 else "",
                    "attribute": tds[7] if len(tds) > 7 else "",
                })
    return plan


def get_free_classrooms(
    session: requests.Session,
    semester: str = "2026-2027-1",
    building: str = "",
    week: int = 1,
    day: int = 1,
    start_period: int = 1,
    end_period: int = 2
) -> List[Dict[str, str]]:
    """查询指定时段的空闲教室列表。
    
    Args:
        building: 教学楼编号，'' 为全部，'001' 一教，'003' 二教，'014' 学研大厦
        week: 周次 (1-20)
        day: 星期几 (1-7)
        start_period: 开始节次 (1-12)
        end_period: 结束节次 (1-12)
    """
    url = f"{BASE_URL}/jsxsd/kbxx/jsjy_query2"
    data = {
        "typewhere": "jszq",
        "xnxqh": semester,
        "jxlbh": building,
        "zc": str(week),
        "zc2": str(week),
        "xq": str(day),
        "xq2": str(day),
        "jc": f"{start_period:02d}",
        "jc2": f"{end_period:02d}",
    }
    headers = {"Referer": f"{BASE_URL}/jsxsd/kbxx/jsjy_query?Ves632DSdyV=NEW_XSD_PYGL"}
    r = session.post(url, data=data, headers=headers, timeout=15)
    soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "html.parser")
    table = soup.find("table", id="dataList") or soup.find("table")
    
    free_rooms = []
    if table:
        for tr in table.find_all("tr")[1:]:
            tds = [td.text.strip() for td in tr.find_all("td")]
            if len(tds) >= 2:
                room_info = tds[0]
                status = tds[1]
                # 状态为空或无占用标志表示空闲
                if not status or status.strip() == "":
                    # 提取名称和容量，形如 'A0212(56/28)'
                    m = re.match(r"([^(]+)(?:\(([^)]+)\))?", room_info)
                    if m:
                        name = m.group(1).strip()
                        cap = m.group(2) if m.group(2) else ""
                    else:
                        name = room_info
                        cap = ""
                    free_rooms.append({
                        "name": name,
                        "raw": room_info,
                        "capacity": cap,
                        "building": building or "全校",
                    })
    return free_rooms


def get_level_exams(session: requests.Session) -> List[Dict[str, str]]:
    """查询四六级等社会等级考试成绩与准考证信息。"""
    url = f"{BASE_URL}/jsxsd/xsdjks/xsdjks_list?Ves632DSdyV=NEW_XSD_KSBM"
    r = session.post(url, timeout=15)
    soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "html.parser")
    tables = soup.find_all("table")
    
    results = []
    # 成绩表通常为第二个或第三个 table
    for table in tables:
        for tr in table.find_all("tr")[1:]:
            tds = [td.text.strip() for td in tr.find_all("td")]
            if len(tds) >= 5 and any("级" in td or "英语" in td or "计算机" in td for td in tds):
                results.append({
                    "name": tds[1] if len(tds) > 1 else "",
                    "level": tds[2] if len(tds) > 2 else "",
                    "time": tds[3] if len(tds) > 3 else "",
                    "score": tds[4] if len(tds) > 4 else "",
                })
    return results


def execute_with_login(account: str, password: str, task_fn, *args, **kwargs):
    """自动完成登录并调用目标抓取函数，确保 Session 生命周期安全关闭。"""
    success, sess, reason = captcha.login(account.strip(), password)
    if not success:
        raise ValueError(reason or "账号或密码错误或验证码识别失败")
    try:
        return task_fn(sess, *args, **kwargs)
    finally:
        sess.close()
