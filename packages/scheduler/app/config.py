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


settings = Settings()
