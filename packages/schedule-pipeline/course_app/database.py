# -*- coding: utf-8 -*-
"""SQLite 数据访问层（标准库 sqlite3，零额外依赖）。

表结构 courses：
    id            INTEGER PRIMARY KEY
    name          TEXT    课程名
    teacher       TEXT    教师
    location      TEXT    教室
    weekday       INTEGER 星期 1-7
    start_section INTEGER 开始节次
    end_section   INTEGER 结束节次
    week_type     TEXT    all / odd / even（每周/单周/双周）
    start_week    INTEGER 起始周
    end_week      INTEGER 结束周
    weeks         TEXT    精确周次 JSON 数组（seed 时展开）
"""
import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "courses.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    teacher       TEXT    NOT NULL DEFAULT '',
    location      TEXT    NOT NULL DEFAULT '',
    weekday       INTEGER NOT NULL,
    start_section INTEGER NOT NULL,
    end_section   INTEGER NOT NULL,
    week_type     TEXT    NOT NULL DEFAULT 'all',
    start_week    INTEGER NOT NULL DEFAULT 1,
    end_week      INTEGER NOT NULL DEFAULT 1,
    weeks         TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_courses_weekday ON courses(weekday);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def clear_courses():
    with get_conn() as conn:
        conn.execute("DELETE FROM courses")


def insert_course(c):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO courses (name, teacher, location, weekday,"
            " start_section, end_section, week_type, start_week, end_week, weeks)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (c["name"], c["teacher"], c["location"], c["weekday"],
             c["start_section"], c["end_section"], c["week_type"],
             c["start_week"], c["end_week"], json.dumps(c["weeks"])),
        )


def fetch_courses(week=None):
    """返回全部课程；week 非空时只返回该周有课的课程。"""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM courses ORDER BY weekday, start_section, id"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["weeks"] = json.loads(d["weeks"])
        if week is not None:
            if week < d["start_week"] or week > d["end_week"]:
                continue
            if d["week_type"] == "odd" and week % 2 == 0:
                continue
            if d["week_type"] == "even" and week % 2 == 1:
                continue
            if week not in d["weeks"]:
                continue
        out.append(d)
    return out
