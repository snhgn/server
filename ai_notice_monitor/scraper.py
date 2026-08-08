"""
scraper.py - 通知网页抓取模块

职责：
1. 抓取通知列表页，解析出 标题 / 链接 / 发布时间
2. 对单个通知抓取详情页，提取正文文本
3. 网络失败自动重试，结构变化时给出清晰错误

与 ai_summary.py / database.py 完全解耦，只输出结构化数据。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import ScraperConfig

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """抓取失败统一异常。"""


@dataclass(frozen=True)
class Notice:
    """一条通知的结构化数据。"""

    title: str
    url: str
    publish_time: str  # 列表页展示的发布时间，如 2026-07-13


class NoticeScraper:
    """北林理学院通知公告抓取器。"""

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})
        # 解析列表页时的容器选择器（基于实测结构：.post-list > .news-last > ul > li）
        self._list_container_selector = ".post-list .news-last ul"
        self._detail_container_selector = ".post-content .content"

    # ---------- 公共入口 ----------

    def fetch_latest(self) -> list[Notice]:
        """抓取最新通知列表（按配置抓取前 N 页，已去重）。"""
        all_notices: dict[str, Notice] = {}
        for page_index in range(self.config.max_pages):
            page_url = self._page_url(page_index)
            try:
                html = self._fetch_with_retry(page_url)
            except ScraperError as e:
                logger.error("抓取分页 %s 失败: %s", page_url, e)
                break  # 某页失败则停止后续页，避免放大故障
            notices = self._parse_list(html, page_url)
            if not notices:
                logger.warning("分页 %s 未解析到任何通知，可能结构变化", page_url)
                break
            for n in notices:
                all_notices.setdefault(n.url, n)
        logger.info("列表页共解析到 %d 条通知", len(all_notices))
        return list(all_notices.values())

    def fetch_detail_text(self, url: str) -> str:
        """抓取通知详情页并提取纯文本正文。失败时返回空串（不阻塞主流程）。"""
        try:
            html = self._fetch_with_retry(url)
        except ScraperError as e:
            logger.warning("抓取详情 %s 失败: %s", url, e)
            return ""
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one(self._detail_container_selector)
        if container is None:
            logger.warning("详情页 %s 未找到正文容器，可能结构变化", url)
            return ""
        # 去掉脚本/样式，取纯文本并压缩空白
        for tag in container.find_all(["script", "style"]):
            tag.decompose()
        text = container.get_text("\n", strip=True)
        text = re.sub(r"\n{2,}", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text

    # ---------- 内部方法 ----------

    def _page_url(self, page_index: int) -> str:
        """根据页码生成列表页 URL。第 0 页为首页，第 1 页起为 index1.html ..."""
        base = self.config.base_url
        if page_index == 0:
            return base
        # 首页形如 .../index.html，分页为 index1.html
        return re.sub(r"index\.html$", f"index{page_index}.html", base)

    def _fetch_with_retry(self, url: str) -> str:
        """带重试的请求。按配置次数重试，全部失败抛 ScraperError。"""
        last_exc: Exception | None = None
        for attempt in range(1, self.config.retries + 1):
            try:
                resp = self.session.get(url, timeout=self.config.timeout)
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or "utf-8"
                return resp.text
            except (requests.RequestException, ValueError) as e:
                last_exc = e
                logger.warning("请求 %s 第 %d/%d 次失败: %s", url, attempt, self.config.retries, e)
                if attempt < self.config.retries:
                    self._backoff(attempt)
        raise ScraperError(f"请求 {url} 重试 {self.config.retries} 次仍失败: {last_exc}")

    @staticmethod
    def _backoff(attempt: int) -> None:
        """失败后的退避等待：按次数递增间隔。"""
        import time

        wait = 2 * attempt
        logger.info("等待 %d 秒后重试...", wait)
        time.sleep(wait)

    def _parse_list(self, html: str, page_url: str) -> list[Notice]:
        """解析列表页 HTML，提取通知条目。"""
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one(self._list_container_selector)
        if container is None:
            logger.error("列表页 %s 未找到容器 %s，页面结构可能变化", page_url, self._list_container_selector)
            return []
        notices: list[Notice] = []
        for li in container.find_all("li"):
            a = li.find("a", href=True)
            if a is None:
                continue
            title = a.get("title") or a.get_text(strip=True)
            if not title:
                continue
            title = title.replace("\xa0", " ").strip()  # 清理不间断空格
            href = urljoin(page_url, a["href"])
            time_span = li.find("span", class_=re.compile(r"time", re.I))
            publish_time = time_span.get_text(strip=True) if time_span else ""
            notices.append(Notice(title=title, url=href, publish_time=publish_time))
        return notices
