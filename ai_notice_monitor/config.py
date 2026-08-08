"""
config.py - 项目配置模块

从 .env 文件读取配置（密钥不写死在代码里）。
所有配置项提供默认值，缺失时使用默认值并告警。
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path

# 尝试加载 .env；未安装 python-dotenv 时忽略（此时需手动设置环境变量）
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - 仅在依赖缺失时触发
    logging.getLogger(__name__).warning("python-dotenv 未安装，跳过 .env 加载")

# 项目根目录（config.py 所在目录）
BASE_DIR = Path(__file__).resolve().parent


def _get_env(key: str, default: str = "") -> str:
    """读取环境变量，缺失时返回默认值并记录告警日志。"""
    value = os.getenv(key, default)
    if not value and not default:
        logging.getLogger(__name__).warning("环境变量 %s 未配置，使用默认值", key)
    return value


@dataclass
class ScraperConfig:
    """网页抓取配置。"""

    base_url: str = _get_env("NOTICE_BASE_URL", "https://cos.bjfu.edu.cn/tzgg/index.html")
    """通知列表首页地址"""

    max_pages: int = int(_get_env("SCRAPER_MAX_PAGES", "2"))
    """最多抓取多少页列表（默认 2 页，防止新通知出现在第二页；越大越慢）"""

    timeout: int = int(_get_env("SCRAPER_TIMEOUT", "15"))
    """单次请求超时（秒）"""

    retries: int = int(_get_env("SCRAPER_RETRIES", "3"))
    """网络失败重试次数"""

    user_agent: str = _get_env(
        "SCRAPER_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    """请求 User-Agent"""


@dataclass
class DatabaseConfig:
    """SQLite 数据库配置。"""

    db_path: Path = BASE_DIR / _get_env("DB_PATH", "notices.db")
    """数据库文件路径（默认项目目录下 notices.db）"""


@dataclass
class AISummaryConfig:
    """AI 摘要配置。

    provider 取值：ollama / deepseek / openai
    三者切换只需修改 provider 与对应 api_base/api_key。
    """

    provider: str = _get_env("AI_PROVIDER", "ollama")
    """摘要提供方"""

    model: str = _get_env("AI_MODEL", "qwen3-4b-8k:latest")
    """模型名"""

    api_base: str = _get_env("AI_API_BASE", "http://localhost:11434/v1")
    """OpenAI 兼容接口地址（ollama 默认 /v1；deepseek/openai 用各自官方地址）"""

    api_key: str = _get_env("AI_API_KEY", "ollama")
    """API 密钥（ollama 本地可填任意值如 ollama）"""

    timeout: int = int(_get_env("AI_TIMEOUT", "60"))
    """AI 请求超时（秒）"""

    max_content_chars: int = int(_get_env("AI_MAX_CONTENT_CHARS", "3000"))
    """送入 AI 的正文最大长度（防止长文超上下文）"""


@dataclass
class EmailConfig:
    """SMTP 邮件配置。"""

    smtp_host: str = _get_env("SMTP_HOST", "")
    """SMTP 服务器（QQ: smtp.qq.com / 163: smtp.163.com）"""

    smtp_port: int = int(_get_env("SMTP_PORT", "465"))
    """SMTP 端口（SSL 465）"""

    sender_email: str = _get_env("SMTP_SENDER", "")
    """发件邮箱"""

    auth_code: str = _get_env("SMTP_AUTH_CODE", "")
    """邮箱授权码（不是登录密码）"""

    receiver_email: str = _get_env("SMTP_RECEIVER", "")
    """收件邮箱"""


@dataclass
class RunConfig:
    """运行行为配置。"""

    first_run_send_all: bool = _get_env("FIRST_RUN_SEND_ALL", "false").lower() == "true"
    """首次运行是否发送历史通知（默认 false：只发新通知）"""


@dataclass
class AppConfig:
    """应用总配置。"""

    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ai: AISummaryConfig = field(default_factory=AISummaryConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    run: RunConfig = field(default_factory=RunConfig)


def load_config() -> AppConfig:
    """加载全部配置。"""
    return AppConfig()
