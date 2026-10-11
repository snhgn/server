# -*- coding: utf-8 -*-
r"""前后端接口契约测试：前端调用的每个 /api/* 路径都必须在 Gateway 上有路由。

背景（回归用例）：
    SettingsView 曾经调用 `/api/settings`，而 Gateway 只有 `/api/ai/settings`
    （设置能力由 ai-service 承载，统一挂在 /api/ai 前缀下）。该路径在网关没有路由，
    请求直接 404 —— 页面上的「长期对话记忆」开关既读不到真实值，保存也静默失败。

本测试直接扫描前端源码里出现的 API 路径字面量，逐一在 Gateway 的路由表上匹配，
确保这类「前端改了路径、后端没有对应路由」的缺口不会再溜过去。

运行：
    cd d:\project\server
    .venv\Scripts\python.exe -m unittest tests.test_route_contract -v
"""
import os
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = ROOT / "web" / "src"

TMP = tempfile.mkdtemp(prefix="gw_route_")
os.environ.update({
    "SQLITE_DB_PATH": str(Path(TMP) / "gateway.db"),
    "JWT_SECRET": "route-contract-secret",
    "LOG_DIR": str(Path(TMP) / "logs"),
    "COURSE_DATA_DIR": str(Path(TMP) / "course-data"),
})
sys.path.insert(0, str(ROOT / "packages" / "gateway"))


def _stub(name, **attrs):
    """注册桩模块，屏蔽本地 venv 缺失的重依赖（cv2 / bs4 / ddddocr …）"""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return sys.modules[name]


_stub("numpy", ndarray=object, uint8="uint8", float32="float32",
      argmax=lambda seq: max(range(len(seq)), key=lambda i: seq[i]))
_stub("cv2", imdecode=lambda *a, **k: (True, None), imencode=lambda *a, **k: (True, None),
      threshold=lambda *a, **k: (0, None), bitwise_not=lambda x: x, INTER_AREA=3,
      COLOR_BGR2GRAY=6, IMREAD_COLOR=1, IMREAD_GRAYSCALE=0, THRESH_BINARY=0,
      THRESH_OTSU=8, ADAPTIVE_THRESH_GAUSSIAN_C=1, MORPH_CLOSE=2, MORPH_OPEN=3,
      MORPH_RECT=0, medianBlur=lambda *a, **k: None, GaussianBlur=lambda *a, **k: None,
      getStructuringElement=lambda *a, **k: None, morphologyEx=lambda *a, **k: None,
      resize=lambda *a, **k: None,
      connectedComponentsWithStats=lambda *a, **k: ([], None, None, None, None))
_stub("ddddocr", DdddOcr=lambda *a, **k: None)
_stub("bs4", BeautifulSoup=lambda *a, **k: None)
_stub("requests", Session=lambda *a, **k: None, get=lambda *a, **k: None,
      post=lambda *a, **k: None)

from app.main import app  # noqa: E402

# 源码里的 '/api/...' 字面量（含模板字符串内的 ${...} 插值）
_API_LITERAL = re.compile(r"""['"`](/api/[A-Za-z0-9_/\-{}.$\(\)]*)['"`]""")


def collect_frontend_paths() -> list[tuple[str, str]]:
    """扫描前端源码，返回 (相对文件路径, 规范化后的 API 路径)。"""
    found: list[tuple[str, str]] = []
    for f in sorted(WEB_SRC.rglob("*")):
        if f.suffix not in (".vue", ".ts", ".js") or not f.is_file():
            continue
        # 只扫描前端自身代码，跳过被塞进 src 的 Android 工程等无关目录
        rel = f.relative_to(WEB_SRC).as_posix()
        if rel.startswith("components/schedule/android"):
            continue
        for m in _API_LITERAL.finditer(f.read_text(encoding="utf-8", errors="ignore")):
            raw = m.group(1)
            # 模板插值 → 占位符，使其能被路由正则匹配
            path = re.sub(r"\$\{[^}]*\}", "sample", raw)
            path = path.split("?")[0]
            found.append((rel, path))
    return found


def iter_leaf_routes(routes):
    """递归展开路由表。

    starlette 1.x 引入了 `_IncludedRouter`，include_router 进来的路由不再平铺在
    app.routes 顶层（子路由挂在 `_IncludedRouter.original_router.routes`），
    直接遍历顶层会漏掉全部业务路由。
    """
    for route in routes:
        inner = getattr(route, "original_router", None)
        sub = getattr(inner, "routes", None) or getattr(route, "routes", None)
        if sub:
            yield from iter_leaf_routes(sub)
        else:
            yield route


def gateway_has_route(path: str) -> bool:
    for route in iter_leaf_routes(app.routes):
        regex = getattr(route, "path_regex", None)
        if regex and regex.match(path):
            return True
    return False


class RouteContractTest(unittest.TestCase):
    def test_frontend_api_paths_have_gateway_route(self):
        paths = collect_frontend_paths()
        self.assertTrue(paths, "未能从前端源码中扫描到任何 /api 路径，扫描逻辑可能失效")

        missing = [(f, p) for f, p in paths if not gateway_has_route(p)]
        self.assertEqual(
            [], missing,
            "以下前端调用的路径在 Gateway 上不存在路由（会导致 404）：\n"
            + "\n".join(f"  {f}: {p}" for f, p in missing),
        )

    def test_settings_path_is_under_ai_prefix(self):
        """设置接口的正确前缀是 /api/ai/settings（能力由 ai-service 提供）。"""
        self.assertTrue(gateway_has_route("/api/ai/settings"))
        self.assertFalse(
            gateway_has_route("/api/settings"),
            "/api/settings 不应被重新引入：它会让人误以为网关自带设置路由，"
            "而实际实现在 ai-service 侧",
        )


if __name__ == "__main__":
    unittest.main()
