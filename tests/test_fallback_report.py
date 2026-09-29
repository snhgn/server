# -*- coding: utf-8 -*-
"""切分兜底链观测的单元测试。

重点锁两件事（都是曾经踩过的坑）：
  1. 非法输出分类要覆盖全部分支
  2. **只在整图非法时评估切分链** —— 之前正是因为在整图正确的样本上
     评估，得出「切分链 2.56%、是负资产」的错误结论。

运行：
    cd D:\\project\\server
    .venv\\Scripts\\python.exe -m unittest tests.test_fallback_report -v
"""
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "gateway"))
sys.path.insert(0, str(ROOT / "packages" / "gateway" / "scripts"))


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return sys.modules[name]


class _Buf:
    """模拟 cv2.imencode 返回的 numpy 数组（切分链会调 .tobytes()）。"""

    def tobytes(self):
        return b"PNG"


def _make_mod(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


# 必须**强制**写入 sys.modules，不能用 _stub 的 setdefault。
# 同一批次里 test_captcha_pipeline / test_compare_models 会先放入自己的
# numpy/cv2 桩（它们的 imencode 返回 bytes），setdefault 不会覆盖，
# 于是本模块的切分链会拿到别人的桩、抛
# "AttributeError: 'bytes' object has no attribute 'tobytes'"，
# 表现为「单跑通过、整批失败」这种顺序相关的假象。
sys.modules["numpy"] = _make_mod(
    "numpy", ndarray=object, uint8="uint8", float32="float32",
    argmax=lambda s: max(range(len(s)), key=lambda i: s[i]),
    count_nonzero=lambda a: 0, asarray=lambda a: a)
sys.modules["cv2"] = _make_mod(
    "cv2", imdecode=lambda *a, **k: (True, None),
    imencode=lambda *a, **k: (True, _Buf()))

# 造可控的 app.schedule.* 桩：让识别结果与切分结果都能被测试指定
import app.schedule as sched_pkg  # noqa: E402

_sched = types.ModuleType("app.schedule.preprocess")
_sched.preprocess = lambda raw: raw
sched_pkg.preprocess = _sched

_seg = types.ModuleType("app.schedule.segment")
_seg.segment_chars = lambda bw, **kw: ([1, 2, 3, 4], [])
sched_pkg.segment = _seg

_rec = types.ModuleType("app.schedule.recognize")
_rec._is_plausible_code = lambda c: bool(c) and len(c) == 4 and all(
    x.isascii() and x.isalnum() for x in c)
_rec._get_ddddocr = lambda: _FakeOcr([])
_rec.ocr_stats = lambda: {"last_weakest": None}


class _FakeOcr:
    """按调用顺序返回预设结果。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def classification(self, data, probability=False):
        self.calls.append(data)
        if self.script:
            return self.script.pop(0)
        return ""


def _install_fake(ocr, whole_out):
    """让 R._is_plausible_code 走真实逻辑、R._get_ddddocr 返回假 OCR。"""
    def plausible(code, expected=4):
        if not code or len(code) != expected:
            return False
        return all(c.isascii() and c.isalnum() for c in code)

    _rec._is_plausible_code = plausible
    _rec._get_ddddocr = lambda: ocr
    sched_pkg.recognize = _rec
    return plausible


SPEC = importlib.util.spec_from_file_location(
    "fb_mod", ROOT / "packages" / "gateway" / "scripts" / "captcha_fallback_report.py")
FB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FB)
# 让 FB 模块引用我们的桩（它内部 `from app.schedule import recognize as R`）
FB.preprocess = _sched.preprocess
FB.segment = _seg
FB.R = _rec

# 记录「未被任何用例污染过」的桩，作为 setUp/tearDown 的还原基准
_PRISTINE_PRE = _sched.preprocess
_PRISTINE_SEG = _seg.segment_chars


class TestClassifyIllegal(unittest.TestCase):
    def test_covers_all_kinds(self):
        c = FB._classify_illegal
        self.assertEqual(c(""), "空输出")
        self.assertEqual(c("一1b2"), "含非ASCII")
        self.assertEqual(c("ab-d"), "含非法字符")
        self.assertEqual(c("abcde"), "位数多")
        self.assertEqual(c("abc"), "位数少")
        self.assertEqual(c("abcd"), "其它", "4位合法串不应走到这里")

    def test_non_ascii_check_precedes_alnum(self):
        """CJK 的 isalnum() 为 True，所以必须先判 isascii()。"""
        self.assertEqual(FB._classify_illegal("一1b2"), "含非ASCII")


class TestOnlyEvaluatesOnIllegal(unittest.TestCase):
    """核心回归：不得在整图合法的样本上评估切分链。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fb_test_")
        os.makedirs(os.path.join(self.tmp, "images"), exist_ok=True)
        self.p = os.path.join(self.tmp, "samples.jsonl")
        # 记录模块级原值：这些桩是全局共享的，若不在 setUp 里重置，
        # 前一个用例替换掉 preprocess 会泄漏到后一个（曾经踩过）。
        self._real_pre = _PRISTINE_PRE
        self._real_seg = _PRISTINE_SEG
        self._reset_stubs()

    def _reset_stubs(self):
        _sched.preprocess = self._real_pre
        _seg.segment_chars = self._real_seg
        FB.preprocess = self._real_pre
        FB.segment = _seg
        FB.R = _rec

    def tearDown(self):
        self._reset_stubs()

    def _make(self, shas):
        with open(self.p, "w", encoding="utf-8") as f:
            for s, label in shas:
                f.write(json.dumps({"sha1": s, "label": label,
                                    "verified": True, "result": "ok"}) + "\n")
                with open(os.path.join(self.tmp, "images", f"{s}.png"), "wb") as g:
                    g.write(b"PNG")

    def test_skips_legal_whole_image_entirely(self):
        """3 张整图全部合法 -> 切分链一次都不该被调用。"""
        self._make([(f"{i:040d}", "abcd") for i in range(3)])
        ocr = _FakeOcr(["abcd"] * 3)          # 整图输出合法
        _install_fake(ocr, None)
        called = []
        FB.preprocess = lambda raw: called.append(1) or raw
        _sched.preprocess = FB.preprocess

        rep = FB.fallback_report(self.tmp, {f"{i:040d}": "abcd" for i in range(3)},
                                 verbose=False, ocr=ocr)
        self.assertEqual(rep["whole_image_legal"], 3)
        self.assertEqual(rep["whole_image_illegal"], 0)
        self.assertEqual(called, [], "整图合法时不得触发 preprocess")
        self.assertEqual(len(ocr.calls), 3, "只应做 3 次整图识别")

    def test_illegal_sample_triggers_fallback(self):
        """整图 5 位（尾随幻觉）-> 触发切分链并正确修正。"""
        sha = "a" * 40
        self._make([(sha, "cb32")])
        ocr = _FakeOcr(["cb32v", "c", "b", "3", "2"])   # 整图5位 + 4个单字符
        _install_fake(ocr, None)

        rep = FB.fallback_report(self.tmp, {sha: "cb32"}, verbose=False, ocr=ocr)
        self.assertEqual(rep["whole_image_illegal"], 1)
        self.assertEqual(rep["fallback_rescued"], 1)
        self.assertEqual(rep["illegal_kinds"], {"位数多": 1})
        self.assertEqual(rep["fallback_rescue_rate"], 1.0)
        self.assertEqual(rep["rescued_examples"], [("cb32", "cb32v", "cb32")])

    def test_fallback_failure_is_reported_not_raised(self):
        sha = "b" * 40
        self._make([(sha, "cb32")])
        ocr = _FakeOcr(["cb32v", "x", "y", "z", "w"])   # 逐字符认错
        _install_fake(ocr, None)
        rep = FB.fallback_report(self.tmp, {sha: "cb32"}, verbose=False, ocr=ocr)
        self.assertEqual(rep["fallback_rescued"], 0)
        self.assertEqual(len(rep["failed_examples"]), 1)
        self.assertEqual(rep["failed_examples"][0][:3], ("cb32", "cb32v", "xyzw"))

    def test_exception_in_fallback_is_surfaced_not_swallowed(self):
        """回归：早先 `except: pass` 会把 nseg 标成 -1 且不给任何原因，
        无法区分「切不出 4 段」和「抛了异常」—— 两者结论完全不同。"""
        sha = "e" * 40
        self._make([(sha, "cb32")])
        ocr = _FakeOcr(["cb32v"])
        _install_fake(ocr, None)

        def boom(raw):
            raise ValueError("预处理炸了")
        FB.preprocess = boom
        try:
            rep = FB.fallback_report(self.tmp, {sha: "cb32"}, verbose=False, ocr=ocr)
        finally:
            FB.preprocess = self._real_pre
        self.assertEqual(rep["fallback_rescued"], 0)
        self.assertEqual(len(rep["fallback_errors"]), 1)
        self.assertIn("ValueError", rep["fallback_errors"][0])
        self.assertIn("预处理炸了", rep["fallback_errors"][0])
        self.assertEqual(rep["failed_examples"][0][4],
                         rep["fallback_errors"][0], "失败原因要能对得上")

    def test_tail_hallucination_is_flagged(self):
        """前 4 位正确但多吐字符 —— 切分链最典型的可修正场景。"""
        sha = "c" * 40
        self._make([(sha, "ab12")])
        ocr = _FakeOcr(["ab12z", "a", "b", "1", "2"])
        _install_fake(ocr, None)
        rep = FB.fallback_report(self.tmp, {sha: "ab12"}, verbose=False, ocr=ocr)
        self.assertEqual(len(rep["tail_hallucination_examples"]), 1)
        self.assertEqual(rep["tail_hallucination_examples"][0],
                         ("ab12", "ab12z", "ab12"))

    def test_missing_image_is_skipped(self):
        truth = {"d" * 40: "abcd"}
        rep = FB.fallback_report(self.tmp, truth, verbose=False,
                                 ocr=_FakeOcr([]))
        self.assertEqual(rep["total"], 0, "图片缺失不应计入分母")

    def test_empty_dataset(self):
        rep = FB.fallback_report(self.tmp, {}, verbose=False, ocr=_FakeOcr([]))
        self.assertEqual(rep["total"], 0)
        self.assertIsNone(rep["fallback_rescue_rate"])
        self.assertEqual(rep["fallback_cost_ms_median"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
