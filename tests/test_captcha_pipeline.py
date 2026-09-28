# -*- coding: utf-8 -*-
"""验证码识别门控与教务会话池的回归测试。

不依赖 numpy / cv2 / ddddocr / torch：这些重依赖在本地 venv 里缺失，
测试通过桩模块注入 sys.modules，只验证本项目自己的判定与编排逻辑。

运行：
    cd D:\\project\\server
    .venv\\Scripts\\python.exe -m unittest tests.test_captcha_pipeline -v
"""
import contextlib
import sys
import threading
import threading
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "gateway"))


def _stub(name, **attrs):
    """注册一个空的桩模块，屏蔽未安装的重依赖。"""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return sys.modules[name]


_stub("numpy",
      ndarray=object, uint8="uint8", float32="float32",
      argmax=lambda seq: max(range(len(seq)), key=lambda i: seq[i]))
_stub("cv2", imdecode=lambda *a, **k: (True, None), imencode=lambda *a, **k: (True, None),
      threshold=lambda *a, **k: (0, None), bitwise_not=lambda x: x, INTER_AREA=3,
      COLOR_BGR2GRAY=6, IMREAD_COLOR=1, IMREAD_GRAYSCALE=0, THRESH_BINARY=0,
      THRESH_OTSU=8, ADAPTIVE_THRESH_GAUSSIAN_C=1, MORPH_CLOSE=2, MORPH_OPEN=3,
      MORPH_RECT=0, medianBlur=lambda *a, **k: None, GaussianBlur=lambda *a, **k: None,
      getStructuringElement=lambda *a, **k: None, morphologyEx=lambda *a, **k: None,
      resize=lambda *a, **k: None, connectedComponentsWithStats=lambda *a, **k: ([], None, None, None, None))

from app.schedule import recognize as R  # noqa: E402


class TestPlausibleCodeGate(unittest.TestCase):
    """recognize._is_plausible_code —— 整图 OCR 结果能否直接采信。"""

    def test_accepts_exact_four_alnum(self):
        for code in ("abcd", "a1b2", "23bc", "Xn3m"):
            self.assertTrue(R._is_plausible_code(code), code)

    def test_rejects_extra_character_instead_of_silently_truncating(self):
        """回归：旧实现 `len(code) >= 4` 会把 'abcde' 截成 'abcd' 并采信。"""
        self.assertFalse(R._is_plausible_code("abcde"))
        self.assertFalse(R._is_plausible_code("a1b2c3d4e5"))

    def test_rejects_too_short(self):
        self.assertFalse(R._is_plausible_code("abc"))
        self.assertFalse(R._is_plausible_code(""))

    def test_rejects_cjk_which_passes_str_isalnum(self):
        """回归：str.isalnum() 对 CJK 返回 True，会让 '一1b2' 蒙混过关。"""
        self.assertTrue("一".isalnum(), "前提：CJK 的 isalnum() 确实为 True")
        self.assertFalse(R._is_plausible_code("一1b2"))
        self.assertFalse(R._is_plausible_code("一234"))

    def test_rejects_punctuation_and_space(self):
        for code in ("ab3!", "ab d", "a-b2", "ab\n2"):
            self.assertFalse(R._is_plausible_code(code), code)


class TestSalvageCode(unittest.TestCase):
    """recognize._salvage_code —— 只剥离噪声，不做截断。"""

    def test_strips_noise_when_exactly_four_survive(self):
        self.assertEqual(R._salvage_code("a1!b2"), "a1b2")
        self.assertEqual(R._salvage_code("a b c d"), "abcd")

    def test_cjk_four_char_output_is_not_salvageable(self):
        """'一1b2' 去掉 CJK 只剩 3 位，凑不出 4 位验证码，必须返回空串。"""
        self.assertEqual(R._salvage_code("一1b2"), "")
        self.assertEqual(R._salvage_code("一2b3"), "")

    def test_returns_empty_when_length_disagrees(self):
        self.assertEqual(R._salvage_code("abc"), "")
        self.assertEqual(R._salvage_code("abcde"), "")
        self.assertEqual(R._salvage_code(""), "")

    def test_never_invents_characters(self):
        """长度不足时宁可返回空串让调用方换码，也不能补位凑数。"""
        for raw in ("a1b", "123", "a1b2c3"):
            self.assertEqual(len(R._salvage_code(raw)), 0, raw)


class TestRecognizeRouting(unittest.TestCase):
    """recognize.recognize 的分流：整图优先、不可信才降级。"""

    def setUp(self):
        self._real_full = R._full_image_ocr
        self._real_pre = R.preprocess
        self._real_seg = R.segment_chars
        self.calls = []

    def tearDown(self):
        R._full_image_ocr = self._real_full
        R.preprocess = self._real_pre
        R.segment_chars = self._real_seg

    def _patch(self, full_result, chars, confs=None):
        def fake_full(image):
            self.calls.append("full")
            return full_result, confs
        R._full_image_ocr = fake_full
        R.preprocess = lambda image: (self.calls.append("pre") or "BINARY")
        R.segment_chars = lambda binary, **kw: (
            self.calls.append("seg") or (chars, []))
        R._ocr_char = lambda img: None

    def test_trustworthy_full_image_skips_segmentation_entirely(self):
        """最高频路径：整图可信时不应做任何预处理/切割，省 CPU。"""
        self._patch("ab3d", [])
        self.assertEqual(R.recognize(b"png"), "ab3d")
        self.assertEqual(self.calls, ["full"], "整图可信时不应触发降级链")

    def test_five_char_output_falls_through_to_segmentation(self):
        """回归：'abcde' 旧实现直接截断采信，现在必须走降级链。"""
        self._patch("abcde", [])
        code = R.recognize(b"png")
        self.assertEqual(self.calls, ["full", "pre", "seg"], "应触发降级链")
        self.assertNotEqual(code, "abcd", "不得静默截断成前 4 位")

    def test_cjk_output_falls_through_and_yields_nothing_salvageable(self):
        """'一1b2' 整图不可信；切分链也无可用结果时返回空串让调用方换码。"""
        self._patch("一1b2", [])
        self.assertEqual(R.recognize(b"png"), "")

    def test_salvage_recovers_code_when_noise_can_be_stripped(self):
        """'a1!b2' 剥离噪声后正好 4 位，降级链末尾仍能抢救出可用结果。"""
        self._patch("a1!b2", [])
        self.assertEqual(R.recognize(b"png"), "a1b2")

    def test_unrecoverable_returns_empty_so_caller_retries_without_rounds(self):
        """整图与切分链都失败时返回空串，省掉必然失败的 2 次提交往返。"""
        self._patch("abcde", [])
        self.assertEqual(R.recognize(b"png"), "")

    def test_second_full_image_inference_is_not_repeated(self):
        """回归：切割失败分支曾再次对同一张图跑整图 OCR，纯属浪费。"""
        self._patch("ab!cde", [])
        R.recognize(b"png")
        self.assertEqual(self.calls.count("full"), 1, "整图 OCR 只应跑一次")


class TestCtcConfidences(unittest.TestCase):
    """recognize._ctc_confidences —— 从 CTC 输出还原逐字符置信度。

    字符集布局与 ddddocr 一致：第 0 项是 blank，字符 c 位于 index(c)。
    """

    CHARSET = "_ab"  # 下标 0 = blank

    @staticmethod
    def _step(peak=1.0, idx=0):
        row = [0.0, 0.0, 0.0]
        row[idx] = peak
        return row

    def test_drops_blank_and_collapses_repeats(self):
        # a  b  a  b  -> 无相邻重复、无 blank 干扰，取两项
        arr = [self._step(0.9, 1), self._step(0.7, 2)]
        confs = R._ctc_confidences(arr, self.CHARSET)
        self.assertEqual(len(confs), 2)
        self.assertAlmostEqual(confs[0], 0.9)
        self.assertAlmostEqual(confs[1], 0.7)

    def test_consecutive_repeats_need_blank_separator(self):
        # 无 blank 隔开的重复字符按 CTC 规则应折叠成 1 个
        arr = [self._step(0.9, 1), self._step(0.8, 1)]
        self.assertEqual(len(R._ctc_confidences(arr, self.CHARSET)), 1)

    def test_repeats_separated_by_blank_both_survive(self):
        arr = [self._step(0.9, 1), self._step(0.99, 0), self._step(0.8, 1)]
        self.assertEqual(len(R._ctc_confidences(arr, self.CHARSET)), 2)

    def test_all_blank_yields_none(self):
        arr = [self._step(0.99, 0), self._step(0.98, 0)]
        self.assertIsNone(R._ctc_confidences(arr, self.CHARSET))

    def test_blank_is_index_zero_not_last(self):
        """回归：blank 曾被误当成最后一个下标，会把空白步解成字符。"""
        arr = [self._step(0.95, 2), self._step(0.99, 0)]
        self.assertEqual(len(R._ctc_confidences(arr, self.CHARSET)), 1)

    def test_degenerate_all_zero_step_is_skipped(self):
        """无信息量的时间步不得被 argmax 硬解成一个低置信度字符。"""
        arr = [[0.0, 0.0, 0.0], self._step(0.9, 1)]
        self.assertEqual(len(R._ctc_confidences(arr, self.CHARSET)), 1)

    def test_missing_inputs_return_none_not_crash(self):
        self.assertIsNone(R._ctc_confidences(None, self.CHARSET))
        self.assertIsNone(R._ctc_confidences([], self.CHARSET))
        self.assertIsNone(R._ctc_confidences([self._step(0.9, 1)], None))

    def test_low_confidence_step_is_reported_faithfully(self):
        arr = [self._step(0.99, 1), self._step(0.11, 2)]
        confs = R._ctc_confidences(arr, self.CHARSET)
        self.assertAlmostEqual(min(confs), 0.11)


class TestDecodeOcrResult(unittest.TestCase):
    """recognize._decode_ocr_result —— 兼容各版本 ddddocr 返回形态。"""

    def test_plain_string_passthrough(self):
        self.assertEqual(R._decode_ocr_result("ab3d"), ("ab3d", None))

    def test_extracts_confidences_from_dict(self):
        row = [0.0, 0.0, 0.0]
        row[1] = 0.9
        res = {"text": "a", "charset": "_ab", "probabilities": [[row]]}
        text, confs = R._decode_ocr_result(res)
        self.assertEqual(text, "a")
        self.assertEqual(confs, [0.9])

    def test_malformed_payload_degrades_gracefully(self):
        """拿不到置信度时退化为 (文本, None)，绝不能因缺字段而丢弃好结果。"""
        self.assertEqual(R._decode_ocr_result({"text": "ab3d"}), ("ab3d", None))
        self.assertEqual(R._decode_ocr_result({"text": "ab3d", "probabilities": "junk"}),
                         ("ab3d", None))
        self.assertEqual(R._decode_ocr_result(None), ("", None))
        self.assertEqual(R._decode_ocr_result(12345), ("", None))

    def test_ignores_ddddocr_own_blurred_confidence_field(self):
        """自带的 confidence 被 blank 稀释且无法定位问题位，不予采用。"""
        res = {"text": "ab", "charset": "ab_", "confidence": 0.99,
               "probabilities": "junk"}
        text, confs = R._decode_ocr_result(res)
        self.assertEqual(text, "ab")
        self.assertIsNone(confs)


class TestOcrStats(unittest.TestCase):
    """recognize.ocr_stats —— 观测数据不得泄露验证码原文。"""

    def setUp(self):
        self._real_full = R._full_image_ocr
        self._real_pre = R.preprocess
        self._real_seg = R.segment_chars
        R.preprocess = lambda image: "BINARY"
        R.segment_chars = lambda binary, **kw: ([], [])
        with R._stats_lock:
            R._stats.update({"samples": 0, "no_confidence": 0,
                             "alignment_mismatch": 0, "last_mean": None,
                             "last_weakest": None, "last_len": 0})

    def tearDown(self):
        R._full_image_ocr = self._real_full
        R.preprocess = self._real_pre
        R.segment_chars = self._real_seg

    def test_records_mean_and_weakest_confidence(self):
        R._full_image_ocr = lambda image: ("ab3d", [0.99, 0.95, 0.90, 0.88])
        R.recognize(b"png")
        st = R.ocr_stats()
        self.assertEqual(st["samples"], 1)
        self.assertAlmostEqual(st["last_weakest"], 0.88)
        self.assertAlmostEqual(st["last_mean"], 0.93, places=3)

    def test_counts_missing_confidence(self):
        R._full_image_ocr = lambda image: ("ab3d", None)
        R.recognize(b"png")
        self.assertEqual(R.ocr_stats()["no_confidence"], 1)

    def test_detects_confidence_length_mismatch(self):
        R._full_image_ocr = lambda image: ("ab3d", [0.9, 0.8])
        R.recognize(b"png")
        self.assertEqual(R.ocr_stats()["alignment_mismatch"], 1)

    def test_stats_never_contain_the_captcha_text(self):
        R._full_image_ocr = lambda image: ("ab3d", [0.99] * 4)
        R.recognize(b"png")
        self.assertNotIn("ab3d", repr(R.ocr_stats()))

    def test_low_confidence_is_not_used_to_reject_the_code(self):
        """回归：低置信度不得否掉整图结果——切分链只会更差，等于白白多花一次验证码。"""
        R._full_image_ocr = lambda image: ("ab3d", [0.05, 0.04, 0.03, 0.02])
        self.assertEqual(R.recognize(b"png"), "ab3d")


class TestSegmentationFallback(unittest.TestCase):
    """整图非法时的切分降级链（原先只有死代码兜底，从未被测试覆盖）。"""

    def setUp(self):
        self._real_full = R._full_image_ocr
        self._real_pre = R.preprocess
        self._real_seg = R.segment_chars
        self._real_ocr = R._ocr_char
        self.chars = ["c1", "c2", "c3", "c4"]

    def tearDown(self):
        R._full_image_ocr = self._real_full
        R.preprocess = self._real_pre
        R.segment_chars = self._real_seg
        R._ocr_char = self._real_ocr

    def _wire(self, full_result, per_char):
        R._full_image_ocr = lambda image: (full_result, None)
        R.preprocess = lambda image: "BINARY"
        R.segment_chars = lambda binary, **kw: (self.chars, [])
        R._ocr_char = lambda img: per_char.get(img, "?")

    def test_uses_segmentation_when_full_image_is_wrong_length(self):
        self._wire("ab", {"c1": "a", "c2": "b", "c3": "c", "c4": "d"})
        self.assertEqual(R.recognize(b"png"), "abcd")

    def test_uses_segmentation_when_full_image_has_cjk(self):
        self._wire("一2b", {"c1": "a", "c2": "b", "c3": "c", "c4": "d"})
        self.assertEqual(R.recognize(b"png"), "abcd")

    def test_segmentation_result_wins_when_legal(self):
        self._wire("ab!cd", {"c1": "x", "c2": "y", "c3": "z", "c4": "w"})
        self.assertEqual(R.recognize(b"png"), "xyzw")

    def test_falls_back_to_salvage_when_segmentation_yields_illegible_code(self):
        # 整图 "a!b2c" 非法但剥离噪声后正好 4 位，切分链又全不可识别
        self._wire("a!b2c", {})
        self.assertEqual(R.recognize(b"png"), "ab2c")

    def test_falls_back_to_salvage_when_wrong_char_count_segmented(self):
        R._full_image_ocr = lambda image: ("a1!b2", None)
        R.preprocess = lambda image: "BINARY"
        R.segment_chars = lambda binary, **kw: (["c1", "c2"], [])  # 只切出 2 段
        self.assertEqual(R.recognize(b"png"), "a1b2")

    def test_returns_empty_when_nothing_is_recoverable(self):
        R._full_image_ocr = lambda image: ("一", None)
        R.preprocess = lambda image: "BINARY"
        R.segment_chars = lambda binary, **kw: (["c1", "c2", "c3", "c4"], [])
        R._ocr_char = lambda img: None
        self.assertEqual(R.recognize(b"png"), "")

    def test_detail_reports_per_char_source(self):
        self._wire("ab", {"c1": "a", "c2": "b", "c3": "c", "c4": "d"})
        code, detail = R.recognize(b"png", return_detail=True)
        self.assertEqual(code, "abcd")
        self.assertEqual(len(detail), 4)
        self.assertTrue(all(src == "ocr" for _, src, _ in detail))


class _FakeCharsetManager:
    """复刻 ddddocr CharsetManager 的 O(n^2) 索引重建语义。"""

    def __init__(self, charset):
        self.charset = list(charset)
        self.charset_range = list(charset)
        self.valid_charset_range_index = []
        self.rebuild_calls = 0
        self._update_valid_indices()

    def _update_valid_indices(self):
        self.rebuild_calls += 1
        self.valid_charset_range_index.clear()
        for item in self.charset_range:
            if item in self.charset:
                self.valid_charset_range_index.append(self.charset.index(item))

    def get_valid_indices(self):
        return self.valid_charset_range_index.copy()


class _FakeOcr:
    def __init__(self, n_charset=400):
        self.charset_manager = _FakeCharsetManager(
            [f"c{i}" for i in range(n_charset)])
        self.calls = 0

    def classification(self, data, probability=False):
        # 模拟真实 predict()：每次都先重跑一次索引重建
        self.charset_manager._update_valid_indices()
        self.calls += 1
        idx = self.charset_manager.get_valid_indices()
        return "ab3d" if len(idx) == len(self.charset_manager.charset) else "ab"


class TestCharsetIndexPin(unittest.TestCase):
    """recognize._pin_charset_index —— 消掉每次识别 336ms 的 O(n^2) 索引重建。"""

    def setUp(self):
        self._real_get = R._get_ddddocr
        self._real_pinned = R._pinned
        R._pinned = False
        self.ocr = _FakeOcr()

    def tearDown(self):
        R._get_ddddocr = self._real_get
        R._pinned = self._real_pinned

    def test_pin_succeeds_and_stops_rebuilding(self):
        self.assertTrue(R._pin_charset_index(self.ocr))
        before = self.ocr.charset_manager.rebuild_calls
        for _ in range(10):
            self.ocr.classification(b"x")
        self.assertEqual(self.ocr.charset_manager.rebuild_calls, before,
                         "钉住之后不应再重建索引")

    def test_pinned_index_is_byte_identical_to_original(self):
        cm = self.ocr.charset_manager
        expected = list(cm.valid_charset_range_index)
        R._pin_charset_index(self.ocr)
        cm._update_valid_indices()  # 触发被替换后的快路径
        self.assertEqual(cm.valid_charset_range_index, expected)

    def test_pin_refuses_when_index_is_not_full_charset(self):
        """范围受限时索引会随 charset_range 变化，快照会过期 -> 必须拒绝钉住"""
        cm = self.ocr.charset_manager
        cm.charset_range = cm.charset[:10]
        cm._update_valid_indices()
        self.assertFalse(R._pin_charset_index(self.ocr))

    def test_pin_declines_gracefully_on_unknown_structure(self):
        """ddddocr 内部结构变化时静默退回原实现，只损失性能不影响功能"""
        self.assertFalse(R._pin_charset_index(object()))

    def test_pin_declines_when_rebuild_raises(self):
        class Boom:
            class charset_manager:
                charset = ["a"]
                valid_charset_range_index = [0]

                @staticmethod
                def _update_valid_indices():
                    raise RuntimeError("boom")
        self.assertFalse(R._pin_charset_index(Boom()))

    def test_self_heals_if_index_gets_clobbered(self):
        """有人清空索引时，快路径要把它原样写回，不能留下半截状态"""
        cm = self.ocr.charset_manager
        expected = list(cm.valid_charset_range_index)
        R._pin_charset_index(self.ocr)
        cm.valid_charset_range_index.clear()
        cm._update_valid_indices()
        self.assertEqual(cm.valid_charset_range_index, expected,
                         "被清空后应被写回完整快照")

    def test_pinned_path_is_far_cheaper(self):
        """量化收益：钉住后每次识别的索引维护开销应远低于原实现"""
        import time
        self.ocr.classification(b"x")  # warm
        n = 20
        t0 = time.perf_counter()
        for _ in range(n):
            self.ocr.classification(b"x")
        t_orig = (time.perf_counter() - t0) / n
        R._pin_charset_index(self.ocr)
        t0 = time.perf_counter()
        for _ in range(n):
            self.ocr.classification(b"x")
        t_pinned = (time.perf_counter() - t0) / n
        self.assertLess(t_pinned, t_orig,
                        f"钉住后应更快：{t_pinned * 1000:.3f}ms vs {t_orig * 1000:.3f}ms")

    def test_concurrent_classification_never_yields_truncated_output(self):
        """回归：索引重建被并发打断时，另一线程会读到半截列表，
        解码出位数不足的验证码（静默错误）。钉住之后必须不再发生。"""
        R._get_ddddocr = lambda: self.ocr
        R._pin_charset_index(self.ocr)
        results, errors = [], []
        barrier = threading.Barrier(8)

        def worker():
            try:
                barrier.wait()
                for _ in range(40):
                    results.append(self.ocr.classification(b"x"))
            except Exception as e:  # pragma: no cover
                errors.append(repr(e))

        ts = [threading.Thread(target=worker) for _ in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 320)
        bad = [r for r in results if len(r) != 4]
        self.assertEqual(bad, [], f"出现 {len(bad)} 次位数不足的识别结果")


class TestConcurrency(unittest.TestCase):
    """热路径已无全局锁：并发调用必须各自拿到独立且完整的结果。"""

    def setUp(self):
        self._real_full = R._full_image_ocr
        self._real_get = R._get_ddddocr
        self._real_pinned = R._pinned

    def tearDown(self):
        R._full_image_ocr = self._real_full
        R._get_ddddocr = self._real_get
        R._pinned = self._real_pinned

    def test_no_global_lock_on_the_hot_path(self):
        """热路径不得再持有全局锁：onnxruntime run() 线程安全，
        索引已钉成只读，串行化只会把吞吐压死。"""
        import inspect
        for fn in (R._full_image_ocr, R._ocr_char):
            self.assertNotIn("_pin_lock", inspect.getsource(fn), fn.__name__)
        self.assertFalse(hasattr(R, "_ocr_lock"),
                         "旧的全局串行锁应已移除")

    def test_parallel_calls_all_succeed(self):
        def fake_full(image):
            return "ab3d", [0.9, 0.9, 0.9, 0.9]
        R._full_image_ocr = fake_full
        out, errs = [], []
        barrier = threading.Barrier(8)

        def worker():
            try:
                barrier.wait()
                for _ in range(50):
                    out.append(R.recognize(b"x"))
            except Exception as e:
                errs.append(repr(e))

        ts = [threading.Thread(target=worker) for _ in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(errs, [])
        self.assertEqual(len(out), 400)
        self.assertTrue(all(c == "ab3d" for c in out))


if __name__ == "__main__":
    unittest.main(verbosity=2)
