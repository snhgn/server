from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """服务配置：所有密钥从 .env 读取，绝不写入代码"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ---- 智谱 GLM（官方 zai-sdk）----
    GLM_API_KEY: str = ""
    # 只允许调用以下白名单模型（默认选最新）
    GLM_TEXT_MODEL: str = "glm-4.7-flash"          # 文本：最新
    GLM_TEXT_FALLBACK_MODEL: str = "glm-4-flash-250414"  # 文本：备选
    GLM_VISION_MODEL: str = "glm-4.6v-flash"       # 视觉：最新
    GLM_VISION_THINK_MODEL: str = "glm-4.1v-thinking-flash"  # 视觉：思考型
    GLM_VISION_FALLBACK_MODEL: str = "glm-4v-flash"  # 视觉：备选
    GLM_IMAGE_MODEL: str = "cogview-3-flash"       # 图片生成
    GLM_IMAGE_SIZE: str = "1024x1024"              # 生成图片尺寸
    GLM_VISION_MAX_TOKENS: int = 32768
    GLM_MAX_TOKENS: int = 65536
    GLM_TEMPERATURE: float = 1.0

    # ---- Google Gemini（官方 HTTP 接口）----
    GEMINI_API_KEY: str = ""
    # 只允许调用以下白名单模型（默认选最新）
    GEMINI_MODEL: str = "gemini-3.6-flash"
    # 开关：默认关闭（国内无法直连 Google API，避免等待超时）
    # 设置为 true 时启用 Gemini 作为 GLM 失败后的备用
    GEMINI_ENABLED: bool = False

    # ---- 硅基流动 SiliconFlow（OpenAI 兼容，独立于 GLM 白名单）----
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    # 翻译模型：腾讯混元（MT 机器翻译）
    HUNYUAN_TRANSLATE_MODEL: str = "tencent/Hunyuan-MT-7B"
    # 总结模型：通义千问
    QWEN_SUMMARY_MODEL: str = "Qwen/Qwen3-8B"

    # ---- 知识库 / RAG ----
    KNOWLEDGE_BASE_DIR: str = "/data/knowledge"
    SQLITE_DB_PATH: str = "/data/memory.db"
    CHROMA_PERSIST_DIR: str = "/data/chroma"
    CHROMA_COLLECTION_NAME: str = "knowledge"
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 3

    # ---- 用户上传文件 ----
    UPLOAD_STORAGE_DIR: str = "/data/uploads"
    UPLOAD_MAX_SIZE_MB: int = 20

    # ---- 课程数据（gateway 同步服务生成的 AI 数据目录）----
    COURSE_DATA_DIR: str = "/data/course-data"

    # ---- 通用 ----
    REQUEST_TIMEOUT: float = 30.0


settings = Settings()
