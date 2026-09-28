# -*- coding: utf-8 -*-
"""测试包初始化：把 SQLite 路径在**任何 app 模块被导入之前**指到临时目录。

为什么需要它：app/config.py 用 pydantic-settings，`settings` 只在首次 import
时按环境变量实例化一次，之后改 os.environ 无效。tests/test_auth_session.py
原本依赖「自己最先被导入」这一点，于是同一批跑时，只要别的测试模块先 import
了 app.config，auth 测试就会去开 /data/gateway.db（Linux 容器里的路径）而在
Windows 上报 "unable to open database file"。

在这里统一兜底后，无论模块导入顺序如何，settings 都会落在一个可写的临时
文件上；test_auth_session 仍会在自己被导入时再覆盖一次（此时若它最先导入则
生效，否则沿用这里设的临时路径——同样是隔离且可写的）。
"""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="gw_tests_"))
os.environ.setdefault("SQLITE_DB_PATH", str(_TMP / "gateway.db"))
os.environ.setdefault("JWT_SECRET", "test-secret-for-unittest")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
