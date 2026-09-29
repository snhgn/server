# -*- coding: utf-8 -*-
"""北林教务系统 (强智) 工具箱功能抓取与解析模块：
- 成绩查询与绩点计算 (get_grades)
- 考试安排查询 (get_exams)
- 空闲教室查询 (get_free_classrooms)
- 培养方案与学分进度 (get_training_plan)
- 等级考试查询 (get_level_exams)
"""
import re
import time
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
import requests

from . import captcha, session_pool

BASE_URL = "http://newjwxt.bjfu.edu.cn"

_classroom_cache: Dict[tuple, tuple[float, List[Dict[str, str]]]] = {}
CLASSROOM_CACHE_TTL = 300  # 5分钟缓存


def normalize_semester(semester: str) -> str:
    """标准化强智教务学期代码为 YYYY-YYYY-N 格式，如 '2026-2027-1'。"""
    if not semester or not semester.strip():
        return ""
    sem = semester.strip()
    m = re.search(r"(\d{4})[-~_](\d{4})[^\d]*([123一二三])", sem)
    if m:
        term_map = {"1": "1", "2": "2", "3": "3", "一": "1", "二": "2", "三": "3"}
        return f"{m.group(1)}-{m.group(2)}-{term_map.get(m.group(3), '1')}"
    return sem


def get_grades(session: requests.Session, semester: str = "", display_mode: str = "all") -> Dict[str, Any]:
    """查询成绩并自动计算学分绩点与均分。
    
    Args:
        session: 已登录的 requests.Session
        semester: 学期代码，如 '2025-2026-2'，空字符串表示全部学期
        display_mode: 'all' 全部成绩，'max' 最高成绩
    """
    norm_sem = normalize_semester(semester)
    url = f"{BASE_URL}/jsxsd/kscj/cjcx_list"
    data = {
        "kksj": norm_sem,
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
        "query_semester": norm_sem,
    }


def get_exams(session: requests.Session, semester: str = "", category: str = "") -> List[Dict[str, str]]:
    """查询学生考试日程与安排。"""
    norm_sem = normalize_semester(semester)
    url = f"{BASE_URL}/jsxsd/xsks/xsksap_list"
    data = {
        "xnxqid": norm_sem,
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


EXCLUDE_ROOM_KEYWORDS = [
    "体育场", "操场", "校园", "羽毛球", "网球", "篮球", "乒乓", "排球", "游泳",
    "湿地", "艺实验", "油泥", "模型", "心理", "同传", "实习", "机房",
    "形体", "舞蹈", "琴房", "排演", "音乐", "画室", "陶艺", "木工", "演播"
]


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
        building: 教学楼编号，'' 为全部，'001' 一教，'003' 二教，'014' 学研大厦，'004' 主楼等
        week: 周次 (1-30)
        day: 星期几 (1-7)
        start_period: 开始节次 (1-12)
        end_period: 结束节次 (1-12)
    """
    norm_sem = normalize_semester(semester) or "2026-2027-1"
    url = f"{BASE_URL}/jsxsd/kbxx/jsjy_query2"
    data = {
        "typewhere": "jszq",
        "xnxqh": norm_sem,
        "jxlbh": building or "",
        "jsbh": "",
        "bjfh": "=",
        "rnrs": "",
        "jszt": "5",  # 5 = 空闲
        "zc": str(week) if week else "",
        "zc2": str(week) if week else "",
        "xq": str(day) if day else "",
        "xq2": str(day) if day else "",
        "jc": f"{start_period:02d}" if start_period else "",
        "jc2": f"{end_period:02d}" if end_period else "",
    }
    headers = {"Referer": f"{BASE_URL}/jsxsd/kbxx/jsjy_query?Ves632DSdyV=NEW_XSD_PYGL"}
    r = session.post(url, data=data, headers=headers, timeout=15)
    soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "html.parser")
    table = soup.find("table", id="dataList") or soup.find("table")
    
    free_rooms = []
    if table:
        for tr in table.find_all("tr"):
            tds = [td.text.strip() for td in tr.find_all(["td", "th"])]
            if not tds or len(tds) < 2:
                continue
            room_info = tds[0]
            # 过滤表头及底部符号说明
            if any(k in room_info for k in ["星期", "教室", "说明", "节次", "时间"]):
                continue
            
            # tds[1:] 包含查询时段内各节次的状态
            status_cells = tds[1:]
            # 只有当所有节次均为空时（即没有 ◆, J, K, L, G, X 等占用标志），才算完全空闲
            if all(not s for s in status_cells):
                m = re.match(r"([^(]+)(?:\(([^)]+)\))?", room_info)
                if m:
                    name = m.group(1).strip()
                    cap = m.group(2) if m.group(2) else ""
                else:
                    name = room_info
                    cap = ""
                
                # 若未指定特定教学楼，过滤非自习室设施（操场、专业工作室、湿地实验室等）
                if not building and any(k in name or k in room_info for k in EXCLUDE_ROOM_KEYWORDS):
                    continue

                # 智能识别教学楼归属（北林教务实际核心为一教、二教、学研中心排课）
                if "一教" in name or building == "001":
                    b_name = "第一教学楼 (一教)"
                    short_b = "一教"
                elif "二教" in name or building == "003":
                    b_name = "第二教学楼 (二教)"
                    short_b = "二教"
                elif any(name.startswith(x) for x in ["A", "B", "C", "学研"]) or building == "014":
                    b_name = "学研中心"
                    short_b = "学研中心"
                elif building:
                    b_name = f"教学楼({building})"
                    short_b = building
                else:
                    b_name = "全校教学区"
                    short_b = "全校"

                free_rooms.append({
                    "name": name,
                    "raw": room_info,
                    "capacity": cap,
                    "building": b_name,
                    "short_building": short_b,
                })
    return free_rooms


def get_free_classrooms_cached(
    account: str,
    password: str,
    semester: str = "2026-2027-1",
    building: str = "",
    week: int = 1,
    day: int = 1,
    start_period: int = 1,
    end_period: int = 2,
) -> List[Dict[str, str]]:
    """带缓存的空闲教室查询，全校自习教室为公共数据，5分钟内无需反复登录打码。"""
    norm_sem = normalize_semester(semester) or "2026-2027-1"
    cache_key = (norm_sem, building or "", int(week), int(day), int(start_period), int(end_period))
    now = time.time()
    if cache_key in _classroom_cache:
        cached_time, cached_data = _classroom_cache[cache_key]
        if now - cached_time < CLASSROOM_CACHE_TTL:
            return cached_data

    data = execute_with_login(
        account,
        password,
        get_free_classrooms,
        norm_sem,
        building,
        week,
        day,
        start_period,
        end_period,
    )
    _classroom_cache[cache_key] = (now, data)
    return data


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


class _SessionStale(Exception):
    """池中会话被服务端作废，需要重新登录。"""


def execute_with_login(account: str, password: str, task_fn, *args, **kwargs):
    """借出已登录会话并调用目标抓取函数。

    会话来自进程内会话池，同一学生连续查询成绩/考试/培养方案/等级考试时
    只在第一次走验证码登录。是否需要「探一下有没有被踢下线」由会话池统一
    决定（只对静置较久的会话探测，见 session_pool.PROBE_AFTER_IDLE），
    这里不再额外发请求——探针要拉一次课表页，放在这层会白吃掉收益。

    抓取函数自身抛异常即视为会话不可信，会话被丢弃后重试一次。
    """
    sid = account.strip()
    for attempt in (1, 2):
        try:
            with session_pool.session_for(
                sid, password, max_retry=5, probe=session_pool.default_probe
            ) as (sess, _reused):
                return task_fn(sess, *args, **kwargs)
        except _SessionStale:
            session_pool.invalidate(sid)
            if attempt == 2:
                raise ValueError("教务系统会话已失效，请稍后重试")
            continue
        except session_pool.LoginFailed:
            # 账号密码/验证码问题：重试无意义，直接上抛（路由转 400）
            raise
        except Exception:
            # 抓取途中出错：会话大概率已不可信，丢弃后最后再试一次
            session_pool.invalidate(sid)
            if attempt == 2:
                raise
    raise ValueError("教务系统会话已失效，请稍后重试")

