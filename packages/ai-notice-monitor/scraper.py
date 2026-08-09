"""
scraper.py - 多站点通知抓取模块

职责：
1. 抓取多个通知列表页，解析出 标题 / 链接 / 发布时间（来源站点名）
2. 对单个通知抓取详情页，提取正文文本（多候选正文容器，失败降级取整页文本）
3. 网络失败自动重试，结构变化时给出清晰错误

通用列表解析：遍历页面内所有 <li>，要求其文本包含 "20xx-xx-xx" 日期，
标题取第一个指向 .html 的 <a>。兼容 cos/gxy/jwc/sports 的常见高校 CMS 结构。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import ScraperConfig, SiteItem

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """抓取失败统一异常。"""


@dataclass(frozen=True)
class Notice:
    """一条通知的结构化数据。"""

    title: str
    url: str
    publish_time: str  # 列表页展示的发布时间，如 2026-07-13
    source: str = "理学院通知"  # 来源站点名


# 详情页正文候选容器（不同站点结构不同，逐个尝试）
_DETAIL_SELECTORS = (
    ".post-content .content",  # cos 理学院
    ".trbox",                  # jwc 教务处详情页模板
    ".ctx-middle",             # gxy 国际学院
    ".article-content",
    ".v_news_content",
    ".TRS_Editor",
    ".newsContent",
    "#content",
    ".content",
    "article",
)

# 日期正则：20xx-xx-xx
_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")


class NoticeScraper:
    """北林多站点通知抓取器。"""

    def __init__(self, config: ScraperConfig, sites: tuple[SiteItem, ...]) -> None:
        self.config = config
        self.sites = sites
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

    # ---------- 公共入口 ----------

    def fetch_site(self, site: SiteItem) -> list[Notice]:
        """抓取单个站点最新通知列表（新通知一般在首页，单页足够）。"""
        try:
            html = self._fetch_with_retry(site.url)
        except ScraperError as e:
            logger.error("抓取站点 %s(%s) 失败: %s", site.name, site.url, e)
            return []
        notices = self._parse_list(html, site.url, site.name)
        logger.info("站点 %s 解析到 %d 条通知", site.name, len(notices))
        return notices

    def fetch_all(self) -> list[Notice]:
        """抓取全部站点，返回合并后的通知列表（去重）。"""
        all_notices: dict[str, Notice] = {}
        for site in self.sites:
            for n in self.fetch_site(site):
                all_notices.setdefault(n.url, n)
        logger.info("全部站点共解析到 %d 条去重通知", len(all_notices))
        return list(all_notices.values())

    def fetch_detail_text(self, url: str) -> str:
        """抓取通知详情页并提取正文文本。失败时返回空串（不阻塞主流程）。"""
        try:
            html = self._fetch_with_retry(url)
        except ScraperError as e:
            logger.warning("抓取详情 %s 失败: %s", url, e)
            return ""
        soup = BeautifulSoup(html, "html.parser")
        container = None
        for sel in _DETAIL_SELECTORS:
            cand = soup.select_one(sel)
            if cand is None:
                continue
            if len(cand.get_text(" ", strip=True)) >= 50:
                container = cand
                break
            # 命中但文本过短（可能正文为空壳容器），继续尝试下一个候选
            logger.warning("详情页 %s 容器 %s 文本过短，尝试下一个", url, sel)
        if container is None:
            # 无已知容器 → 选文本最长的容器（可避开导航菜单），再不行取整页
            texts = []
            for cand in soup.find_all(["div", "article", "section"]):
                t = cand.get_text(" ", strip=True)
                if len(t) > 50:
                    texts.append((len(t), cand))
            if texts:
                container = max(texts, key=lambda x: x[0])[1]
            else:
                container = soup.body or soup
            logger.warning("详情页 %s 未匹配已知正文容器，使用最长文本容器", url)
        # 去掉脚本/样式/导航，取纯文本并压缩空白
        for tag in container.find_all(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = container.get_text("\n", strip=True)
        text = re.sub(r"\n{2,}", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text

    # ---------- 内部方法 ----------

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

    @staticmethod
    def _parse_list(html: str, page_url: str, source: str) -> list[Notice]:
        """
        通用列表解析：遍历 li，要求含 "20xx-xx-xx" 日期，标题取第一个指向 .html 的 a。
        日期在 li 内任意位置（span/p/div 均可），天然过滤无日期的导航菜单项。
        """
        soup = BeautifulSoup(html, "html.parser")
        notices: list[Notice] = []
        for li in soup.find_all("li"):
            # 1. 日期：li 文本中匹配 20xx-xx-xx
            date_m = _DATE_RE.search(li.get_text(" ", strip=True))
            if not date_m:
                continue
            # 2. 标题：第一个 href 含 .html 的链接
            a = None
            for cand in li.find_all("a", href=True):
                if ".html" in cand["href"] or cand["href"].endswith("/"):
                    a = cand
                    break
            if a is None:
                continue
            title = a.get("title") or a.get_text(strip=True)
            if not title:
                continue
            title = title.replace("\xa0", " ").strip()
            if len(title) < 4:  # 跳过过短的导航/装饰链接
                continue
            href = urljoin(page_url, a["href"])
            notices.append(Notice(
                title=title, url=href,
                publish_time=date_m.group(0), source=source,
            ))
        return notices
