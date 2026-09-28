# -*- coding: utf-8 -*-
"""教务已登录会话池的回归测试。

用假 captcha 模块替换真实登录，验证池的复用/作废/独占/有界语义，
不需要网络与重依赖。

运行：
    cd D:\\project\\server
    .venv\\Scripts\\python.exe -m unittest tests.test_session_pool -v
"""
import sys
import threading
import time
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "gateway"))


def _stub(name, **attrs):
    """注册空桩模块，屏蔽未安装的重依赖（numpy/cv2 真实实现本机没有）。"""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return sys.modules[name]


_stub("numpy", ndarray=object, uint8="uint8", float32="float32",
      argmax=lambda seq: max(range(len(seq)), key=lambda i: seq[i]))
_stub("cv2", imencode=lambda *a, **k: (True, b"PNG"), imdecode=lambda *a, **k: (True, None))


class FakeSession:
    def __init__(self, tag):
        self.tag = tag
        self.closed = False

    def close(self):
        self.closed = True


class FakeCaptcha:
    """替换 app.schedule.captcha，记录登录次数。"""

    def __init__(self):
        self.logins = 0
        self.fail_next = 0
        self.alive = True
        self._n = 0
        self.mod = types.ModuleType("app.schedule.captcha")
        self.mod.login = self.login
        self.mod.get_timetable = self.get_timetable
        self.mod.is_login_page = lambda text: "RANDOMCODE" in (text or "")
        self.mod.BASE_URL = "http://fake"

    def login(self, account, password, session=None, max_retry=10, verbose=False):
        self.logins += 1
        if self.fail_next > 0:
            self.fail_next -= 1
            return False, None, "账号或密码错误"
        self._n += 1
        return True, FakeSession(f"{account}#{self._n}"), ""

    def get_timetable(self, session):
        return "GRID" if self.alive else '<form action="Logon.do">RANDOMCODE</form>'


import app.schedule as sched_pkg  # noqa: E402

# 导入真实的 session_pool，只把它的模块级 captcha 引用换成假的。
# 刻意不去动 sys.modules 里的 app.* 条目：那样会把假模块留在包属性上，
# 污染同批次后续导入的测试模块（unittest discover 下会报
# "app.schedule.session_pool has no attribute _SLOTS"）。
_fake = FakeCaptcha()

from app.schedule import session_pool  # noqa: E402

_REAL_CAPTCHA = session_pool.captcha


def setUpModule():
    session_pool.captcha = _fake.mod


def tearDownModule():
    session_pool.captcha = _REAL_CAPTCHA


class TestSessionPool(unittest.TestCase):
    def setUp(self):
        session_pool._SLOTS.clear()
        _fake.logins = 0
        _fake.fail_next = 0
        _fake.alive = True

    def test_second_call_reuses_session_and_skips_login(self):
        """核心收益：同一学生第二次取用不应再走验证码登录。"""
        with session_pool.session_for("260101208", "pw") as (s1, reused1):
            self.assertFalse(reused1, "首次应为新建登录")
            s1_tag = s1.tag
        with session_pool.session_for("260101208", "pw") as (s2, reused2):
            self.assertTrue(reused2, "二次应命中池中会话")
            self.assertEqual(s2.tag, s1_tag, "应复用同一个 Session 对象")
        self.assertEqual(_fake.logins, 1, "两次取用只应登录一次")

    def test_different_students_do_not_share_sessions(self):
        with session_pool.session_for("A", "pw") as (sa, _):
            with session_pool.session_for("B", "pw") as (sb, _):
                self.assertIsNot(sa, sb)
        self.assertEqual(_fake.logins, 2)

    def test_stale_session_triggers_relogin(self):
        with session_pool.session_for("S", "pw") as (_, reused):
            self.assertFalse(reused)
        _fake.alive = False  # 服务端作废该会话
        with session_pool.session_for("S", "pw", probe=session_pool.default_probe) as (_, reused):
            self.assertFalse(reused, "探测到失效后应重新登录")
        self.assertEqual(_fake.logins, 2)

    def test_exception_inside_block_discards_session(self):
        with self.assertRaises(RuntimeError):
            with session_pool.session_for("E", "pw") as (s, _):
                raise RuntimeError("boom")
        self.assertTrue(s.closed, "块内异常时必须释放连接")
        with session_pool.session_for("E", "pw") as (_, reused):
            self.assertFalse(reused, "异常后不应复用该会话")
        self.assertEqual(_fake.logins, 2)

    def test_login_failure_surfaces_as_login_failed_value_error(self):
        _fake.fail_next = 1
        with self.assertRaises(session_pool.LoginFailed) as ctx:
            with session_pool.session_for("F", "bad"):
                pass
        self.assertIn("账号", str(ctx.exception))
        self.assertIsInstance(ctx.exception, ValueError,
                              "须继承 ValueError 以兼容路由既有 except ValueError")
        self.assertIsNone(session_pool._SLOTS["F"].session,
                          "登录失败不得把会话留在池中")

    def test_ttl_expiry_forces_relogin(self):
        with session_pool.session_for("T", "pw") as (_, reused):
            self.assertFalse(reused)
        saved = session_pool.SESSION_TTL
        session_pool.SESSION_TTL = 0.0
        try:
            with session_pool.session_for("T", "pw") as (_, reused):
                self.assertFalse(reused, "TTL 到期应重新登录")
        finally:
            session_pool.SESSION_TTL = saved
        self.assertEqual(_fake.logins, 2)

    def test_invalidate_forces_relogin(self):
        with session_pool.session_for("I", "pw") as (_, _):
            pass
        session_pool.invalidate("I")
        with session_pool.session_for("I", "pw") as (_, reused):
            self.assertFalse(reused)
        self.assertEqual(_fake.logins, 2)

    def test_concurrent_use_of_same_student_is_serialised(self):
        """requests.Session 不可跨线程并发：同学号必须互斥检出。"""
        overlap = []
        active = []
        guard = threading.Lock()

        def worker():
            with session_pool.session_for("C", "pw") as (s, _):
                with guard:
                    active.append(s)
                    if len(active) > 1:
                        overlap.append(len(active))
                time.sleep(0.02)
                with guard:
                    active.remove(s)

        ts = [threading.Thread(target=worker) for _ in range(6)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(overlap, [], "同一学号的会话被并发借出了")
        self.assertEqual(_fake.logins, 1, "并发请求应共享一次登录")

    def test_pool_is_bounded(self):
        """访客路径允许任意学号，池必须有上界防止无界增长。"""
        saved = session_pool.MAX_SLOTS
        session_pool.MAX_SLOTS = 4
        try:
            for i in range(20):
                with session_pool.session_for(f"stu{i}", "pw"):
                    pass
            self.assertLessEqual(len(session_pool._SLOTS), 6)
        finally:
            session_pool.MAX_SLOTS = saved
            session_pool._SLOTS.clear()

    def test_empty_student_id_rejected(self):
        with self.assertRaises(session_pool.LoginFailed):
            with session_pool.session_for("   ", "pw"):
                pass

    def test_stats_exposes_no_credentials(self):
        with session_pool.session_for("260101208", "supersecret") as (_, _):
            pass
        st = session_pool.stats()
        self.assertEqual(st["reusable_sessions"], 1)
        self.assertNotIn("supersecret", repr(st))
        self.assertNotIn("260101208", repr(st))


if __name__ == "__main__":
    unittest.main(verbosity=2)
