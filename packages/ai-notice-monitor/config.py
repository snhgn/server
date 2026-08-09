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

# 项目根目录（config.py 所在目录）
BASE_DIR = Path(__file__).resolve().parent

# 尝试加载 .env（优先加载脚本目录下的 .env，兼容容器内 CWD 非脚本目录的情况）
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover - 仅在依赖缺失时触发
    logging.getLogger(__name__).warning("python-dotenv 未安装，跳过 .env 加载")


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

    provider: str = _get_env("AI_PROVIDER", "aiapi")
    """摘要提供方：aiapi(本平台 ai-service) / ollama / deepseek / openai"""

    model: str = _get_env("AI_MODEL", "")
    """模型名（aiapi 由 ai-service 决定，可留空；其余提供方必填）"""

    api_base: str = _get_env("AI_API_BASE", "http://ai-service:8000")
    """aiapi: ai-service 地址（容器内 http://ai-service:8000）；其余为 OpenAI 兼容地址"""

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


@dataclass(frozen=True)
class SiteItem:
    """一个被监控的站点（列表页）。"""

    name: str
    """站点名（用于日志/邮件区分来源）"""

    url: str
    """列表页 URL"""


def _load_sites() -> tuple[SiteItem, ...]:
    """从 MONITOR_SITES 读取站点列表（JSON 数组），未配置时默认只监控理学院。"""
    raw = os.getenv("MONITOR_SITES", "").strip()
    if not raw:
        return (SiteItem("理学院通知", "https://cos.bjfu.edu.cn/tzgg/index.html"),)
    try:
        import json

        items = json.loads(raw)
        if not isinstance(items, list) or not items:
            raise ValueError("empty list")
        return tuple(
            SiteItem(name=str(it.get("name") or it.get("url")),
                     url=str(it["url"]))
            for it in items
            if isinstance(it, dict) and it.get("url")
        )
    except Exception as e:  # 配置损坏时回退默认，不阻塞启动
        logging.getLogger(__name__).warning("MONITOR_SITES 解析失败(%s)，使用默认站点", e)
        return (SiteItem("理学院通知", "https://cos.bjfu.edu.cn/tzgg/index.html"),)


@dataclass
class AppConfig:
    """应用总配置。"""

    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ai: AISummaryConfig = field(default_factory=AISummaryConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    run: RunConfig = field(default_factory=RunConfig)
    sites: tuple[SiteItem, ...] = field(default_factory=_load_sites)
    """监控站点列表（可多个来源）"""


def load_config() -> AppConfig:
    """加载全部配置。"""
    return AppConfig()
