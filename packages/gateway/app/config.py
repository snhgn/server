from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Gateway 配置：密钥从 .env 读取，绝不写入代码"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ---- 认证 ----
    ADMIN_PASSWORD_HASH: str = ""
    JWT_SECRET: str = ""
    JWT_EXPIRE_HOURS: int = 24

    # ---- 用户数据库 ----
    SQLITE_DB_PATH: str = "/data/gateway.db"

    # ---- 内部服务地址（容器名:端口）----
    AI_SERVICE_URL: str = "http://ai-service:8000"
    SCHEDULER_SERVICE_URL: str = "http://scheduler:8002"

    # ---- Schedule 课表模块 ----
    SCHEDULE_CACHE_TTL_HOURS: float = 6.0      # 缓存有效期，减少重复访问教务系统
    SCHEDULE_COOLDOWN_SECONDS: int = 30        # 同一用户两次爬取的最小间隔
    SCHEDULE_CRAWL_TIMEOUT: int = 75           # 单次爬取总超时（秒）
    SCHEDULE_CAPTCHA_MAX_RETRY: int = 5        # 验证码识别最大重试次数

    # ---- 课程数据同步 / AI 数据目录 ----
    COURSE_DATA_DIR: str = "/data/course-data" # 用户专属 AI 数据目录（与 ai-service 共享）
    COURSE_SYNC_HOUR: int = 3                  # 每日定时同步时刻（24 小时制，服务器时区）

    # ---- 通用 ----
    REQUEST_TIMEOUT: float = 130.0


settings = Settings()
