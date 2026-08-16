"""Scripts API：/scripts（User 只读）与 /admin/scripts（Admin）"""
import ast
import json
import logging
import os
import re
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .. import scripts_db as db
from ..config import settings
from ..scripts_core import get_next_run, run_script_now, stop_script, sync_task

logger = logging.getLogger("scheduler.scripts")
router = APIRouter(tags=["scripts"])

VALID_TYPES = ("crawler", "ai_task", "service", "automation")
VALID_VISIBILITY = ("public", "private")


def require_admin(x_role: str = Header("", alias="X-Role")) -> None:
    """Admin 校验：由 Gateway 转发时注入 X-Role（直接访问 scheduler 也安全）"""
    if x_role != "admin":
        raise HTTPException(403, "Admin only")


# ---- 请求模型 ----


class ScriptCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    type: str = "automation"
    command: str | None = None          # 手写执行命令（与 code 二选一）
    code: str | None = None            # AI 生成的 Python 代码（后端落盘并自动生成 command）
    visibility: str = "public"
    cron: str | None = None
    enabled: bool = True


class ScriptUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    command: str | None = None
    code: str | None = None            # 重新生成/手改后的代码，覆盖落盘
    visibility: str | None = None
    cron: str | None = None
    enabled: bool | None = None


class CodeGenerateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)   # 任务名（供 AI 理解用途）
    prompt: str = Field(..., min_length=10, max_length=8000)  # 需求提示词


class CodeReviewRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100000)
    name: str = ""
    description: str = ""


# ---- 通用构建函数 ----


def _public_script(row: dict) -> dict:
    """User 可见字段：不含 command / owner 等信息"""
    last = db.latest_run(row["id"])
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "type": row["type"],
        "status": row["status"],
        "visibility": row["visibility"],
        "enabled": bool(row["enabled"]),
        "next_run": get_next_run(row["id"]),
        "last_run": {
            "start_time": last["start_time"],
            "end_time": last["end_time"],
            "status": last["status"],
            "duration_ms": last["duration_ms"],
        } if last else None,
    }


def _admin_script(row: dict) -> dict:
    item = _public_script(row)
    task = db.get_task(row["id"])
    item["command"] = row["command"]
    item["cron"] = task["cron"] if task else None
    item["owner_id"] = row["owner_id"]
    item["created_at"] = row["created_at"]
    return item


def _build_summary(script_id: int) -> dict:
    runs = db.list_runs(script_id, limit=20)
    total = len(runs)
    success = sum(1 for r in runs if r["status"] == "success")
    failed = sum(1 for r in runs if r["status"] == "failed")
    durations = [r["duration_ms"] for r in runs if r.get("duration_ms")]
    avg = int(sum(durations) / len(durations)) if durations else None
    return {
        "script_id": script_id,
        "total_runs": total,
        "success": success,
        "failed": failed,
        "avg_duration_ms": avg,
        "recent_runs": runs[:10],
    }


# ---- User 接口（只读，仅公开脚本）----


@router.get("/scripts")
async def list_public_scripts() -> dict:
    rows = [r for r in db.list_scripts(public_only=True)]
    return {"scripts": [_public_script(r) for r in rows]}


@router.get("/scripts/{script_id}/status")
async def script_status(script_id: int) -> dict:
    row = db.get_script(script_id)
    if not row or row["visibility"] != "public" or not row["enabled"]:
        raise HTTPException(404, "Script not found")
    last = db.latest_run(script_id)
    return {
        "id": row["id"],
        "status": row["status"],
        "enabled": bool(row["enabled"]),
        "next_run": get_next_run(script_id),
        "last_run_status": last["status"] if last else None,
        "last_run_time": last["start_time"] if last else None,
    }


@router.get("/scripts/{script_id}/summary")
async def script_summary(script_id: int) -> dict:
    row = db.get_script(script_id)
    if not row or row["visibility"] != "public" or not row["enabled"]:
        raise HTTPException(404, "Script not found")
    return _build_summary(script_id)


# ---- AI 代码生成 / 审查（生成与审查用不同 provider，交叉验证）----


async def _ai_chat(message: str, provider: str) -> tuple[str, str]:
    """调用 ai-service 非流式 chat，返回 (answer, 实际使用的 provider)"""
    async with httpx.AsyncClient(
        base_url=settings.AI_SERVICE_URL, timeout=settings.AI_GENERATE_TIMEOUT
    ) as client:
        resp = await client.post(
            "/api/chat",
            json={"message": message, "use_rag": False, "use_memory": False,
                  "provider": provider},
            headers={"X-User-Id": "0", "X-Username": "admin", "X-Role": "admin"},
        )
        data = resp.json()
    if not data.get("success") or not data.get("answer"):
        raise HTTPException(502, data.get("error") or "AI service returned empty answer")
    return data["answer"], data.get("provider") or provider


def _strip_code_fence(text: str) -> str:
    """剥离 AI 回答中的 markdown 围栏/前后解释，提取纯代码"""
    fence = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    code = fence.group(1) if fence else text
    # 无围栏时去掉首尾可能的解释性行（保留以 #/\"开头的代码体）
    return code.strip() + "\n"


def _syntax_check(code: str) -> tuple[bool, str]:
    """本地语法校验（ast），不依赖 AI"""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as exc:
        return False, f"line {exc.lineno}: {exc.msg}"


def _sanitize_filename(name: str) -> str:
    """任务名 → 安全文件名（仅字母数字下划线连字符，防空目录穿越/命令注入）"""
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name).strip("_")
    return safe or "script"


def _save_code_file(name: str, code: str) -> str:
    """代码落盘到 SCRIPTS_CODE_DIR/<safe>.py，返回容器内执行命令"""
    path = os.path.join(settings.SCRIPTS_CODE_DIR, _sanitize_filename(name) + ".py")
    os.makedirs(settings.SCRIPTS_CODE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    os.chmod(path, 0o644)
    return f"python {path}"


_GENERATE_PROMPT = """你是服务器自动化脚本工程师。请根据以下需求编写一个 Python 脚本。

【硬性约束】
1. 只能使用 Python 3.12 标准库（urllib.request、json、os、re、datetime、sqlite3、subprocess、email 等），禁止使用 requests、numpy 等第三方库
2. 脚本在 Linux 容器内以 `python <脚本路径>` 方式一次性执行，超时 1800 秒后会被强制终止
3. 网络请求必须设置超时（建议 30 秒），失败时重试 2-3 次，最终失败以 sys.exit(1) 结束
4. 关键步骤用 print() 输出进度（stdout 会被记录到运行日志）
5. 严禁任何危险操作：rm -rf、格式化磁盘、修改系统文件、反弹 shell、fork 炸弹、无节制死循环
6. 代码顶部用 docstring 说明用途

【任务名】{name}
【需求】{prompt}

请直接输出完整 Python 代码：第一个字符必须是 docstring 或注释，不要使用 markdown 代码块围栏，不要输出任何解释文字。"""


_REVIEW_PROMPT = """你是资深代码审查员，负责审查将在生产服务器容器中定时执行的 Python 自动化脚本。

【脚本信息】任务名：{name}；描述：{description}

【待审代码】
{code}

【审查维度】
1. 安全性：是否存在删除文件、破坏系统、命令注入、数据外发到未知地址、危险系统调用
2. 正确性：逻辑是否完整、异常处理是否到位、是否存在可能的死循环或资源泄漏
3. 健壮性：网络超时、编码处理、失败时的退出码
4. 可运行性：是否只依赖 Python 标准库（容器内无第三方库）

请严格按以下 JSON 格式输出，不要输出 JSON 以外的任何内容：
{{"verdict": "pass 或 warn 或 fail", "issues": ["问题描述1", "问题描述2"], "summary": "一句话总评"}}
verdict 取值：pass=安全可运行；warn=有小问题但不影响运行；fail=存在危险行为或严重缺陷，不建议运行。没有问题时 issues 为空数组。"""


def _parse_review(text: str) -> dict:
    """从 AI 回答中提取审查 JSON（容错：围栏/前后缀）"""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            verdict = data.get("verdict", "warn")
            if verdict not in ("pass", "warn", "fail"):
                verdict = "warn"
            return {
                "verdict": verdict,
                "issues": [str(i) for i in data.get("issues", [])][:20],
                "summary": str(data.get("summary", ""))[:500],
            }
        except (ValueError, TypeError):
            pass
    return {"verdict": "warn", "issues": ["审查结果解析失败，原文：" + text[:300]],
            "summary": ""}


@router.post("/admin/scripts/generate")
async def admin_generate_code(req: CodeGenerateRequest,
                              _: None = Depends(require_admin)) -> dict:
    """提示词 → AI（CODE_PROVIDER）生成 Python 脚本代码"""
    message = _GENERATE_PROMPT.format(name=req.name, prompt=req.prompt)
    try:
        answer, provider = await _ai_chat(message, settings.AI_CODE_PROVIDER)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("AI generate error: %s", exc)
        raise HTTPException(502, f"AI service unavailable: {str(exc)[:150]}")
    code = _strip_code_fence(answer)
    syntax_ok, syntax_error = _syntax_check(code)
    return {"code": code, "syntax_ok": syntax_ok, "syntax_error": syntax_error,
            "generator": provider}


@router.post("/admin/scripts/review")
async def admin_review_code(req: CodeReviewRequest,
                            _: None = Depends(require_admin)) -> dict:
    """代码 → 另一个 AI（REVIEW_PROVIDER）交叉审查；语法错直接 fail 不调 AI"""
    syntax_ok, syntax_error = _syntax_check(req.code)
    if not syntax_ok:
        return {"verdict": "fail", "issues": [f"语法错误 {syntax_error}"],
                "summary": "代码存在语法错误，无法执行", "reviewer": "local-ast",
                "syntax_ok": False, "syntax_error": syntax_error}
    message = _REVIEW_PROMPT.format(name=req.name or "(未命名)",
                                    description=req.description or "(无)",
                                    code=req.code[:30000])
    try:
        answer, provider = await _ai_chat(message, settings.AI_REVIEW_PROVIDER)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("AI review error: %s", exc)
        raise HTTPException(502, f"AI service unavailable: {str(exc)[:150]}")
    review = _parse_review(answer)
    review.update({"reviewer": provider, "syntax_ok": True, "syntax_error": ""})
    return review


# ---- Admin 接口 ----


@router.get("/admin/scripts")
async def admin_list_scripts(_: None = Depends(require_admin)) -> dict:
    return {"scripts": [_admin_script(r) for r in db.list_scripts()]}


@router.post("/admin/scripts", status_code=201)
async def admin_create_script(req: ScriptCreate,
                              _: None = Depends(require_admin)) -> dict:
    if req.type not in VALID_TYPES:
        raise HTTPException(400, f"type must be one of {VALID_TYPES}")
    if req.visibility not in VALID_VISIBILITY:
        raise HTTPException(400, "visibility must be 'public' or 'private'")
    if req.cron:
        from apscheduler.triggers.cron import CronTrigger
        try:
            CronTrigger.from_crontab(req.cron, timezone=settings.TIMEZONE)
        except Exception:
            raise HTTPException(400, "Invalid cron expression")

    command = req.command
    if req.code is not None:
        # AI 生成/手改代码：语法校验 → 落盘 → 自动生成执行命令
        if not req.code.strip():
            raise HTTPException(400, "code must not be empty")
        syntax_ok, syntax_error = _syntax_check(req.code)
        if not syntax_ok:
            raise HTTPException(400, f"Code syntax error: {syntax_error}")
        try:
            command = _save_code_file(req.name, req.code)
        except OSError as exc:
            raise HTTPException(500, f"Failed to save code file: {exc}")
    if not command:
        raise HTTPException(400, "command or code is required")

    script_id = db.create_script(
        req.name, req.description, req.type, command, req.visibility, 0
    )
    db.update_script(script_id, enabled=1 if req.enabled else 0)
    sync_task(script_id, req.cron, req.enabled)
    return _admin_script(db.get_script(script_id))


@router.put("/admin/scripts/{script_id}")
async def admin_update_script(script_id: int, req: ScriptUpdate,
                              _: None = Depends(require_admin)) -> dict:
    row = db.get_script(script_id)
    if not row:
        raise HTTPException(404, "Script not found")
    old_command = row["command"]
    updates: dict = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.description is not None:
        updates["description"] = req.description
    if req.type is not None:
        if req.type not in VALID_TYPES:
            raise HTTPException(400, f"type must be one of {VALID_TYPES}")
        updates["type"] = req.type
    if req.command is not None:
        updates["command"] = req.command
    if req.code is not None:
        # 重新生成/手改后的代码：校验 → 按目标名落盘（name 同步变更时清理旧文件）
        syntax_ok, syntax_error = _syntax_check(req.code)
        if not syntax_ok:
            raise HTTPException(400, f"Code syntax error: {syntax_error}")
        try:
            updates["command"] = _save_code_file(
                req.name if req.name is not None else row["name"], req.code
            )
        except OSError as exc:
            raise HTTPException(500, f"Failed to save code file: {exc}")
    if req.visibility is not None:
        if req.visibility not in VALID_VISIBILITY:
            raise HTTPException(400, "visibility must be 'public' or 'private'")
        updates["visibility"] = req.visibility
    if req.enabled is not None:
        updates["enabled"] = 1 if req.enabled else 0
    db.update_script(script_id, **updates)

    # name 变更时清理旧代码文件（仅限 SCRIPTS_CODE_DIR 内由本服务生成的文件）
    old_code_prefix = f"python {settings.SCRIPTS_CODE_DIR}/"
    if req.code is not None and req.name is not None and old_command.startswith(old_code_prefix):
        old_file = old_command[len("python "):]
        new_file = os.path.join(settings.SCRIPTS_CODE_DIR, _sanitize_filename(req.name) + ".py")
        if old_file != new_file and os.path.exists(old_file):
            try:
                os.remove(old_file)
            except OSError as exc:
                logger.warning("remove old code file failed %s: %s", old_file, exc)

    # 任务同步：cron 字段显式更新时才动调度
    if req.cron is not None or req.enabled is not None:
        task = db.get_task(script_id)
        cron = req.cron if req.cron is not None else (task["cron"] if task else None)
        enabled = req.enabled if req.enabled is not None else bool(row["enabled"])
        sync_task(script_id, cron, enabled)

    return _admin_script(db.get_script(script_id))


@router.delete("/admin/scripts/{script_id}")
async def admin_delete_script(script_id: int,
                              _: None = Depends(require_admin)) -> dict:
    row = db.get_script(script_id)
    if not row:
        raise HTTPException(404, "Script not found")
    # 清理落盘代码文件（仅限 SCRIPTS_CODE_DIR 内由本服务生成的）
    old_code_prefix = f"python {settings.SCRIPTS_CODE_DIR}/"
    if row["command"].startswith(old_code_prefix):
        code_file = row["command"][len("python "):]
        try:
            os.remove(code_file)
        except OSError as exc:
            logger.warning("remove code file on delete failed %s: %s", code_file, exc)
    db.delete_script(script_id)
    # 移除 APScheduler job
    from ..core import get_scheduler
    from ..scripts_core import job_id
    job = get_scheduler().get_job(job_id(script_id))
    if job:
        job.remove()
    return {"deleted": script_id}


@router.post("/admin/scripts/{script_id}/run")
async def admin_run_script(script_id: int,
                           _: None = Depends(require_admin)) -> dict:
    if not db.get_script(script_id):
        raise HTTPException(404, "Script not found")
    try:
        run_id = run_script_now(script_id)
    except ValueError:
        raise HTTPException(404, "Script not found")
    return {"run_id": run_id, "status": "running"}


@router.post("/admin/scripts/{script_id}/stop")
async def admin_stop_script(script_id: int,
                            _: None = Depends(require_admin)) -> dict:
    if not db.get_script(script_id):
        raise HTTPException(404, "Script not found")
    killed = stop_script(script_id)
    return {"stopped": script_id, "killed": killed}


@router.get("/admin/scripts/{script_id}/summary")
async def admin_script_summary(script_id: int,
                               _: None = Depends(require_admin)) -> dict:
    if not db.get_script(script_id):
        raise HTTPException(404, "Script not found")
    return _build_summary(script_id)


@router.get("/admin/scripts/{script_id}/logs")
async def admin_script_logs(script_id: int, date: str | None = None,
                            _: None = Depends(require_admin)) -> dict:
    row = db.get_script(script_id)
    if not row:
        raise HTTPException(404, "Script not found")
    from ..scripts_runner import _log_path
    dt = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now(timezone.utc).astimezone()
    path = _log_path(row["name"], dt)
    lines = []
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()[-settings.LOG_TAIL_LINES:]
    except Exception as exc:
        logger.warning("read log failed: %s", exc)
    last = db.latest_run(script_id)
    return {
        "date": dt.strftime("%Y-%m-%d"),
        "path": f"logs/scripts/{row['name']}/{dt.strftime('%Y-%m-%d')}.log",
        "lines": lines,
        "latest_run": last,
    }


@router.post("/admin/scripts/{script_id}/analyze-error")
async def admin_analyze_error(script_id: int,
                              _: None = Depends(require_admin)) -> dict:
    row = db.get_script(script_id)
    if not row:
        raise HTTPException(404, "Script not found")
    error = db.latest_failed_error(script_id)
    if not error:
        raise HTTPException(400, "No failed run error available to analyze")

    prompt = (
        f"你是服务器自动化脚本运维专家。以下是脚本「{row['name']}」最近一次执行的错误信息：\n\n"
        f"{error[:3000]}\n\n"
        "请分析可能的原因（可考虑：网站结构变化、网络异常、请求频率限制、配置错误、代码问题等），"
        "并给出可操作的解决建议。请用简洁的中文，分「可能原因」和「解决建议」两部分输出，"
        "不要输出多余内容。"
    )
    try:
        async with httpx.AsyncClient(
            base_url=settings.AI_SERVICE_URL, timeout=settings.AI_ANALYZE_TIMEOUT
        ) as client:
            resp = await client.post(
                "/api/chat",
                json={"message": prompt, "use_rag": True, "use_memory": False},
                headers={
                    "X-User-Id": "0",
                    "X-Username": "admin",
                    "X-Role": "admin",
                },
            )
            data = resp.json()
    except Exception as exc:
        logger.warning("AI analyze error: %s", exc)
        raise HTTPException(502, f"AI service unavailable: {str(exc)[:150]}")
    if not data.get("success"):
        raise HTTPException(502, data.get("error", "AI analysis failed"))
    return {"script_id": script_id, "analysis": data.get("answer", "")}
