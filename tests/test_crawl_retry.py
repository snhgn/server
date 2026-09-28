# -*- coding: utf-8 -*-
"""课表抓取与工具箱借用在「池中会话已失效」时的重登重试语义。

用假 session_pool/captcha 驱动 service._crawl_sync 与 toolbox.execute_with_login，
验证：失效会话会被重登一次、成功结果被正常归一化、登录失败不被误报成抓取错误。

运行：
    cd D:\\project\\server
    .venv\\Scripts\\python.exe -m unittest tests.test_crawl_retry -v
"""
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "gateway"))


def _stub(name, **attrs):
    """注册空桩模块，屏蔽未安装的重依赖。"""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return sys.modules[name]


# 真实 cv2/numpy/bs4 本机没装，先塞桩才能 import app.schedule.*
_stub("bs4", BeautifulSoup=object)
_stub("numpy", ndarray=object, uint8="uint8", float32="float32",
      argmax=lambda seq: max(range(len(seq)), key=lambda i: seq[i]))
_stub("cv2", imencode=lambda *a, **k: (True, b"PNG"), imdecode=lambda *a, **k: (True, None))


# ---- 假 captcha / session_pool / parse 层 ----------------------------------
LOGIN_HTML = "<form action='Logon.do'><input name='RANDOMCODE'></form>"
GRID_HTML = "GRID"


def is_login(text):
    return not text or "RANDOMCODE" in text


class _FakeCaptcha:
    def __init__(self):
        self.logins = 0
        self.fail = False

    def login(self, account, password, session=None, max_retry=10, verbose=False):
        self.logins += 1
        if self.fail:
            return False, None, "账号或密码错误"
        return True, object(), ""

    def get_timetable(self, session):
        return getattr(session, "html", GRID_HTML)

    def is_login_page(self, text):
        return is_login(text)


class _FakeSession:
    def __init__(self, html):
        self.html = html


class _FakePool:
    """按脚本发放会话；fail=True 时像真实池一样抛 LoginFailed。"""

    def __init__(self):
        self.scripts = []
        self.i = 0
        self.invalidated = []

    def session_for(self, sid, password, max_retry=5, verbose=False, probe=None):
        pool = self

        class _Ctx:
            def __enter__(self):
                if _fake_captcha.fail:
                    raise LoginFailed("账号或密码错误")
                sess = pool.scripts[min(pool.i, len(pool.scripts) - 1)]
                pool.i += 1
                return sess, False

            def __exit__(self, *a):
                return False
        return _Ctx()

    def invalidate(self, sid):
        self.invalidated.append(sid)


class LoginFailed(ValueError):
    pass


# 导入真实的 service/toolbox，然后只替换它们的**模块级属性**。
# 刻意不去替换 sys.modules 里的 app.* 条目：那样假模块会留在包属性上，
# 污染同批次后续导入的测试模块（unittest discover 下表现为
# "app.schedule.session_pool has no attribute _SLOTS" 之类的诡异报错）。
import app.schedule.service as service  # noqa: E402
import app.schedule.toolbox as toolbox  # noqa: E402

_fake_captcha = _FakeCaptcha()
_fake_pool = _FakePool()

_fake_captcha_mod = _FakeCaptcha()
_fake_captcha_mod.login = _fake_captcha.login
_fake_captcha_mod.get_timetable = _fake_captcha.get_timetable
_fake_captcha_mod.is_login_page = _fake_captcha.is_login_page

# 假的 session_pool 门面：只提供 service/toolbox 用到的两个名字
_fake_pool_mod = types.SimpleNamespace(
    LoginFailed=LoginFailed,
    session_for=None,   # 每个用例的 setUp 填
    invalidate=None,
)

_fake_parse = types.SimpleNamespace(
    merge_adjacent=lambda rows: rows,
    parse_grid=lambda html: [],
    extract_selects=lambda html: {},
    fetch_semester=lambda s, v: "",
    strip_tags=lambda s: s,
)

# 快照被改写前的原值，tearDownModule 逐一还原
_ORIGINALS = [
    (service, "captcha", service.captcha),
    (service, "session_pool", service.session_pool),
    (service, "parse_timetable", service.parse_timetable),
    (service, "course_context", service.course_context),
    (service, "_current_semester", service._current_semester),
    (toolbox, "captcha", toolbox.captcha),
    (toolbox, "session_pool", toolbox.session_pool),
]


def setUpModule():
    service.captcha = _fake_captcha_mod
    service.session_pool = _fake_pool_mod
    service.parse_timetable = _fake_parse
    service._current_semester = lambda html: "2025-2026-1"
    service.course_context = types.SimpleNamespace(
        sync_from_cache=lambda *a, **k: None)
    toolbox.captcha = _fake_captcha_mod
    toolbox.session_pool = _fake_pool_mod


def tearDownModule():
    for mod, attr, value in _ORIGINALS:
        setattr(mod, attr, value)


class TestCrawlSync(unittest.TestCase):
    def setUp(self):
        self.pool = _FakePool()
        # 填上门面里 service/toolbox 用到的两个名字
        _fake_pool_mod.session_for = self.pool.session_for
        _fake_pool_mod.invalidate = self.pool.invalidate
        _fake_captcha.fail = False
        _fake_captcha.logins = 0
        _fake_parse.parse_grid = lambda html: []
        service._current_semester = lambda html: "2025-2026-1"
        self._pt = service.parse_timetable
        self._sem = service._current_semester

    def tearDown(self):
        service.parse_timetable = self._pt
        service._current_semester = self._sem

    def _grid(self, rows):
        # 登录页解析不出任何课程，模拟真实的"失效会话表现为空课表"
        _fake_parse.parse_grid = (
            lambda html: [] if is_login(html) else rows)
        service._current_semester = lambda html: "2025-2026-1"

    def test_success_on_first_attempt_normalises_courses(self):
        self.pool.scripts = [_FakeSession(GRID_HTML)]
        self._grid([{"name": "高数", "period": "第1-2节", "day": 1}])
        sem, courses = service._crawl_sync("260101208", "pw")
        self.assertEqual(sem, "2025-2026-1")
        self.assertEqual(courses[0]["name"], "高数")
        self.assertEqual((courses[0]["start"], courses[0]["end"]), (1, 2))

    def test_stale_session_triggers_one_relogin(self):
        """池中会话被作废 -> 第一次拿到登录页 -> 重登后成功。"""
        self.pool.scripts = [_FakeSession(LOGIN_HTML), _FakeSession(GRID_HTML)]
        self._grid([{"name": "英语", "period": "第3-4节", "day": 2}])
        sem, courses = service._crawl_sync("260101208", "pw")
        self.assertEqual(courses[0]["name"], "英语")
        self.assertEqual(self.pool.i, 2, "应恰好重试一次")

    def test_persistently_stale_gives_empty_timetable_error(self):
        self.pool.scripts = [_FakeSession(LOGIN_HTML), _FakeSession(LOGIN_HTML)]
        self._grid([])
        with self.assertRaises(service.ScheduleError) as ctx:
            service._crawl_sync("260101208", "pw")
        self.assertEqual(ctx.exception.http_status, 400)
        self.assertIn("暂无课表", ctx.exception.message)

    def test_genuinely_empty_semester_does_not_retry(self):
        """真的没课时不该再烧一次验证码。"""
        self.pool.scripts = [_FakeSession(GRID_HTML)]
        self._grid([])
        with self.assertRaises(service.ScheduleError) as ctx:
            service._crawl_sync("260101208", "pw")
        self.assertEqual(ctx.exception.http_status, 400)
        self.assertEqual(self.pool.i, 1, "非失效场景应只尝试一次")

    def test_login_failure_mapped_to_400_not_502(self):
        _fake_captcha.fail = True
        try:
            self.pool.scripts = [_FakeSession(GRID_HTML)]
            with self.assertRaises(service.ScheduleError) as ctx:
                service._crawl_sync("260101208", "bad")
            self.assertEqual(ctx.exception.http_status, 400)
            self.assertIn("密码", ctx.exception.message)
        finally:
            _fake_captcha.fail = False

    def test_parser_valueerror_is_not_misreported_as_login_error(self):
        """回归：抓取阶段的 ValueError 曾被当成登录失败，谎报「账号或密码错误」。"""
        def boom(html):
            raise ValueError("表格列数异常")
        self.pool.scripts = [_FakeSession(GRID_HTML), _FakeSession(GRID_HTML)]
        _fake_parse.parse_grid = boom
        with self.assertRaises(service.ScheduleError) as ctx:
            service._crawl_sync("260101208", "pw")
        self.assertEqual(ctx.exception.http_status, 502,
                         "解析异常应报 502 上游不可用，而非 400 账号密码错误")


class TestExecuteWithLogin(unittest.TestCase):
    def setUp(self):
        self.pool = _FakePool()
        _fake_pool_mod.session_for = self.pool.session_for
        _fake_pool_mod.invalidate = self.pool.invalidate
        _fake_captcha.fail = False
        self.pool.scripts = [_FakeSession(GRID_HTML)]

    def test_task_receives_the_session(self):
        seen = []
        out = toolbox.execute_with_login(" 260101208 ", "pw",
                                         lambda s, *a: seen.append(s) or "ok")
        self.assertEqual(out, "ok")
        self.assertIsInstance(seen[0], _FakeSession)
        self.assertEqual(seen[0].html, GRID_HTML)

    def test_login_failure_propagates_as_value_error(self):
        _fake_captcha.fail = True
        try:
            with self.assertRaises(LoginFailed):
                toolbox.execute_with_login("260101208", "bad", lambda s: "ok")
        finally:
            _fake_captcha.fail = False

    def test_task_exception_discards_and_retries_once(self):
        calls = []

        def flaky(sess):
            calls.append(sess)
            if len(calls) == 1:
                raise RuntimeError("stale")
            return "recovered"

        self.pool.scripts = [_FakeSession(GRID_HTML), _FakeSession(GRID_HTML)]
        self.assertEqual(toolbox.execute_with_login("260101208", "pw", flaky), "recovered")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
