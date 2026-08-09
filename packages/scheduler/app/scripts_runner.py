"""脚本执行：命令运行 + 每日分片日志 + 状态回写"""
import logging
import os
from datetime import datetime, timezone

from . import scripts_db as db
from .config import settings
from .executor import execute_command

logger = logging.getLogger("scheduler.scripts_runner")


def _script_log_dir(name: str) -> str:
    return os.path.join(settings.SCRIPTS_LOG_DIR, name)


def _log_path(name: str, dt: datetime) -> str:
    return os.path.join(_script_log_dir(name), dt.strftime("%Y-%m-%d") + ".log")


def write_log(name: str, line: str) -> None:
    """追加一行到当日日志文件（自动建目录）"""
    try:
        d = datetime.now(timezone.utc).astimezone()
        path = _log_path(name, d)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{d.isoformat(timespec='seconds')}] {line}\n")
    except Exception as exc:
        logger.warning("write_log failed %s: %s", name, exc)


async def execute_script(script_id: int, trigger: str = "scheduled",
                         run_id: int | None = None) -> None:
    """执行脚本：建 run 记录 → 跑命令 → 写结果/日志 → 回写状态。
    run_id 由手动运行预创建时传入；定时任务为 None 时自动创建。"""
    script = db.get_script(script_id)
    if not script:
        return
    # 定时触发且已禁用 → 跳过
    if trigger == "scheduled" and not script["enabled"]:
        return

    run_id = run_id or db.create_run(script_id, trigger)
    db.set_script_status(script_id, "running")

    log_head = f"===== RUN #{run_id} trigger={trigger} start ====="
    write_log(script["name"], log_head)

    success, output, error = False, "", ""
    try:
        success, output, error = await execute_command(
            script["command"], settings.SCRIPT_TIMEOUT, job_id=f"script_{script_id}"
        )
    except Exception as exc:
        error = str(exc)

    db.finish_run(run_id, success, output, error)

    # 状态回写：失败 → failed；成功 → 启用则 waiting / 禁用则 disabled
    if success:
        db.set_script_status(script_id, "disabled" if not script["enabled"] else "waiting")
    else:
        db.set_script_status(script_id, "failed")

    # 日志：输出摘要 + 错误
    out_tail = output.strip().splitlines()[-20:] if output.strip() else []
    for line in out_tail:
        write_log(script["name"], f"[output] {line}")
    if error.strip():
        for line in error.strip().splitlines()[:20]:
            write_log(script["name"], f"[error] {line}")
    write_log(script["name"], f"===== RUN #{run_id} end {'OK' if success else 'FAILED'} =====")

    logger.info("Script %s (%s) trigger=%s -> %s", script["name"], run_id, trigger,
                "OK" if success else "FAILED")
