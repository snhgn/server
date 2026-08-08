"""任务管理路由"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core import (
    add_job, get_job, list_jobs, pause_job, remove_job, resume_job, trigger_job,
)
from ..executor import get_history

router = APIRouter(tags=["scheduler"])


class JobCreate(BaseModel):
    id: str = Field(..., description="任务 ID（唯一）")
    name: str
    type: str = Field(..., description="command 或 http")
    payload: str = Field(..., description="command: shell 命令; http: JSON {url,method,headers,body}")
    cron: str = Field(..., description="cron 表达式: '分 时 日 月 周'")
    timeout: int = 300


class JobResponse(BaseModel):
    id: str
    name: str
    type: str
    cron: str


@router.get("/jobs")
async def list_all_jobs() -> dict:
    return {"jobs": list_jobs()}


@router.get("/jobs/{job_id}")
async def get_job_detail(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(req: JobCreate) -> JobResponse:
    if req.type not in ("command", "http"):
        raise HTTPException(400, "type must be 'command' or 'http'")
    add_job(req.id, req.name, req.type, req.payload, req.cron, req.timeout)
    return JobResponse(id=req.id, name=req.name, type=req.type, cron=req.cron)


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> dict:
    if not remove_job(job_id):
        raise HTTPException(404, "Job not found")
    return {"removed": job_id}


@router.post("/jobs/{job_id}/pause")
async def pause(job_id: str) -> dict:
    if not pause_job(job_id):
        raise HTTPException(404, "Job not found")
    return {"paused": job_id}


@router.post("/jobs/{job_id}/resume")
async def resume(job_id: str) -> dict:
    if not resume_job(job_id):
        raise HTTPException(404, "Job not found")
    return {"resumed": job_id}


@router.post("/jobs/{job_id}/trigger")
async def trigger(job_id: str) -> dict:
    if not await trigger_job(job_id):
        raise HTTPException(404, "Job not found")
    return {"triggered": job_id}


@router.get("/history")
async def history(job_id: str | None = None, limit: int = 20) -> dict:
    return {"history": get_history(job_id, limit)}
