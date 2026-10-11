# -*- coding: utf-8 -*-
r"""登录失败限流表的内存边界测试。

背景（回归用例）：
    限流表 `_login_fails` 按 username 计数。原实现只在 `_login_blocked()` 里惰性清理
    「被查询过的那个 username」，而攻击者只要让**每个用户名只失败一次**就永远不会被
    `_login_blocked` 查询到 —— 字典只增不减。实测 5000 个不同用户名即可占用约 4MB，
    而 gateway 的 mem_limit 只有 384MB，属于可被低成本放大的内存耗尽面。

修复：写入前检查容量，超限先做一轮过期清理，仍超限则整体清空；
      查询时若该用户名窗口内已无有效记录，连带删除条目。

运行：
    cd d:\project\server
    .venv\Scripts\python.exe -m unittest tests.test_login_rate_limit -v
"""
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = tempfile.mkdtemp(prefix="gw_loginfail_")
os.environ.update({
    "SQLITE_DB_PATH": str(Path(TMP) / "gateway.db"),
    "JWT_SECRET": "rate-limit-secret",
    "LOG_DIR": str(Path(TMP) / "logs"),
})

conn = sqlite3.connect(os.environ["SQLITE_DB_PATH"])
conn.execute(
    "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE,"
    " password_hash TEXT, role TEXT)"
)
conn.commit()
conn.close()

sys.path.insert(0, str(ROOT / "packages" / "gateway"))

from app.routers import auth as auth_router  # noqa: E402

# 与实现保持一致的上限
MAX_KEYS = auth_router._LOGIN_FAILS_MAX_KEYS


class LoginRateLimitTest(unittest.TestCase):
    def setUp(self):
        auth_router._login_fails.clear()

    def test_table_is_bounded_under_username_enumeration(self):
        for i in range(MAX_KEYS * 4):
            auth_router._record_login_fail(f"attacker-{i}")
        self.assertLessEqual(
            len(auth_router._login_fails), MAX_KEYS,
            "限流表在用户名枚举下必须保持有界",
        )

    def test_still_blocks_after_max_failures_for_one_user(self):
        for _ in range(auth_router._LOGIN_MAX_FAILS):
            auth_router._record_login_fail("victim")
        self.assertTrue(auth_router._login_blocked("victim"))

    def test_not_blocked_below_threshold(self):
        auth_router._record_login_fail("victim")
        self.assertFalse(auth_router._login_blocked("victim"))

    def test_expired_entry_is_dropped_on_query(self):
        """窗口内已无有效记录的条目，查询时应连带删除，避免字典只增不减。"""
        stale_ts = time.monotonic() - (auth_router._LOGIN_WINDOW + 60)
        auth_router._login_fails["stale"] = deque([stale_ts])
        self.assertFalse(auth_router._login_blocked("stale"))
        self.assertNotIn("stale", auth_router._login_fails)


if __name__ == "__main__":
    unittest.main()
