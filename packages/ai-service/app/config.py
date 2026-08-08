from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """服务配置：所有密钥从 .env 读取，绝不写入代码"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ---- 智谱 GLM（官方 zai-sdk）----
    GLM_API_KEY: str = ""
    GLM_MODEL: str = "glm-4.7-flash"
    GLM_MAX_TOKENS: int = 65536
    GLM_TEMPERATURE: float = 1.0

    # ---- Google Gemini（官方 HTTP 接口）----
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-latest"
    # 开关：默认关闭（国内无法直连 Google API，避免等待超时）
    # 设置为 true 时启用 Gemini 作为 GLM 失败后的备用
    GEMINI_ENABLED: bool = False

    # ---- 知识库 / RAG ----
    KNOWLEDGE_BASE_DIR: str = "/data/knowledge"
    SQLITE_DB_PATH: str = "/data/memory.db"
    CHROMA_PERSIST_DIR: str = "/data/chroma"
    CHROMA_COLLECTION_NAME: str = "knowledge"
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 3

    # ---- 通用 ----
    REQUEST_TIMEOUT: float = 30.0


settings = Settings()
