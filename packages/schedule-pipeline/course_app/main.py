# -*- coding: utf-8 -*-
"""课表展示服务（FastAPI）。

启动：
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

接口：
    GET /course             课表页面
    GET /api/course         全部课程 JSON
    GET /api/course?week=N  只返回第 N 周有课的课程
    GET /api/meta           学期/周历元信息
"""
import os
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="课表服务", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 学年周历：2026-2027-1 学期（教务系统当前学期）
META = {
    "semester": "2026-2027-1",
    "first_monday": "2026-09-07",   # 学年第一周周一
    "total_weeks": 20,
    "sections": [
        ("08:00", "08:45"), ("08:55", "09:40"),
        ("10:00", "10:45"), ("10:55", "11:40"),
        ("14:00", "14:45"), ("14:55", "15:40"),
        ("16:00", "16:45"), ("16:55", "17:40"),
        ("19:00", "19:45"), ("19:55", "20:40"),
        ("20:50", "21:35"), ("21:45", "22:30"),
    ],
}


@app.get("/course")
def course_page():
    return FileResponse(os.path.join(TEMPLATE_DIR, "course.html"))


@app.get("/api/course")
def api_course(week: Optional[int] = Query(default=None, ge=1)):
    try:
        return database.fetch_courses(week=week)
    except Exception as e:  # 数据库异常时给前端可读错误
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/meta")
def api_meta():
    return META
