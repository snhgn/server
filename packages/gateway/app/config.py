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

    # ---- 通用 ----
    REQUEST_TIMEOUT: float = 130.0


settings = Settings()
