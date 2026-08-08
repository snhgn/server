"""
database.py - SQLite 存储与去重模块

职责：
1. 保存历史通知（URL 唯一键，天然去重）
2. 记录每条通知是否已发送
3. 支持长期运行：并发安全（WAL）、幂等插入

表结构 notices：
    id             INTEGER PRIMARY KEY AUTOINCREMENT
    url            TEXT UNIQUE NOT NULL       -- 通知链接（唯一键）
    title          TEXT NOT NULL              -- 标题
    publish_time   TEXT                       -- 发布时间（列表页展示）
    first_seen_at  TEXT                       -- 首次发现时间
    sent           INTEGER DEFAULT 0          -- 0=未发送 1=已发送
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import DatabaseConfig
from scraper import Notice

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    publish_time TEXT,
    first_seen_at TEXT,
    sent INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notices_sent ON notices(sent);
CREATE INDEX IF NOT EXISTS idx_notices_publish ON notices(publish_time);
"""


class NoticeDatabase:
    """通知存储与去重。"""

    def __init__(self, config: DatabaseConfig) -> None:
        self.db_path: Path = config.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # WAL 模式提升并发读写性能，长期运行更稳
        self.conn.execute("PRAGMA journal_mode=WAL")
        # executescript 支持一次执行多条 DDL 语句
        self.conn.executescript(_SCHEMA)
        self.conn.commit()
        logger.info("数据库已就绪: %s", self.db_path)

    def close(self) -> None:
        """关闭数据库连接。"""
        self.conn.close()

    def insert_new(self, notice: Notice) -> bool:
        """
        插入一条新通知。返回 True 表示"新记录"（可发送），
        返回 False 表示已存在（跳过，不重复发送）。
        """
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            self.conn.execute(
                "INSERT INTO notices (url, title, publish_time, first_seen_at, sent) "
                "VALUES (?, ?, ?, ?, 0)",
                (notice.url, notice.title, notice.publish_time, now),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # URL 已存在 → 去重命中
            return False

    def mark_sent(self, notice: Notice) -> None:
        """把已发送的通知标记为已发送。"""
        self.conn.execute(
            "UPDATE notices SET sent=1 WHERE url=? AND sent=0", (notice.url,)
        )
        self.conn.commit()

    def has_notice(self, url: str) -> bool:
        """判断某通知是否已存在。"""
        cur = self.conn.execute("SELECT 1 FROM notices WHERE url=?", (url,))
        return cur.fetchone() is not None

    def count(self) -> int:
        """返回库中通知总数。"""
        cur = self.conn.execute("SELECT COUNT(*) AS c FROM notices")
        return int(cur.fetchone()["c"])

    def count_unsent(self) -> int:
        """返回未发送的通知数。"""
        cur = self.conn.execute("SELECT COUNT(*) AS c FROM notices WHERE sent=0")
        return int(cur.fetchone()["c"])
