"""Scheduler 配置"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # SQLite 持久化路径（容器内）
    SQLITE_DB_PATH: str = "/data/sqlite/scheduler.db"

    # 时区
    TIMEZONE: str = "Asia/Shanghai"

    # 任务执行超时（秒）
    JOB_TIMEOUT: int = 300

    # 历史记录保留条数
    HISTORY_LIMIT: int = 100

    # ---- Scripts 自动化模块 ----
    SCRIPTS_DB_PATH: str = "/data/sqlite/scripts.db"
    SCRIPTS_LOG_DIR: str = "/app/logs/scripts"
    SCRIPT_TIMEOUT: int = 1800          # 单次脚本执行超时（秒）
    SCRIPT_OUTPUT_LIMIT: int = 10000    # script_runs.output 截断长度
    LOG_TAIL_LINES: int = 200           # 日志接口返回行数

    # ---- AI 错误分析（复用 ai-service）----
    AI_SERVICE_URL: str = "http://ai-service:8000"
    AI_ANALYZE_TIMEOUT: float = 60.0

    # ---- AI 代码生成/审查（管理员新建脚本，复用 ai-service）----
    SCRIPTS_CODE_DIR: str = "/app/scripts"   # AI 生成脚本的落盘目录（需 volume 持久化）
    AI_GENERATE_TIMEOUT: float = 110.0        # 单次 AI 调用上限（须 < gateway REQUEST_TIMEOUT=130s）
    AI_CODE_PROVIDER: str = "glm"             # 代码生成 provider
    AI_REVIEW_PROVIDER: str = "gemini"        # 代码审查 provider（另一个 AI，交叉验证）


settings = Settings()
