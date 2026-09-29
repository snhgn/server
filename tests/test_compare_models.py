# -*- coding: utf-8 -*-
"""配对比较脚本的统计口径测试。

用**手算可验证**的小样本锁死行为，避免统计部分被静默改错：
McNemar 检验、Wilson 区间、只认 verified 标签等。

运行：
    cd D:\\project\\server
    .venv\\Scripts\\python.exe -m unittest tests.test_compare_models -v
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


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return sys.modules[name]


# 只需要 cv2/numpy 存在即可导入（不会真调用）
_stub("numpy", ndarray=object, uint8="uint8", float32="float32",
      argmax=lambda s: max(range(len(s)), key=lambda i: s[i]),
      mean=lambda a, axis=None: 0.0, median=lambda a: 0.0, asarray=lambda a: a)
_stub("cv2", imdecode=lambda *a, **k: (True, None), imencode=lambda *a, **k: (True, b"P"))

SPEC = importlib.util.spec_from_file_location(
    "compare_mod", ROOT / "packages" / "gateway" / "scripts" / "compare_captcha_models.py")
CMP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CMP)


class TestExactBinom(unittest.TestCase):
    """精确双侧二项检验。"""

    def test_no_disagreement_is_not_significant(self):
        self.assertEqual(CMP.binom_two_sided_p(0, 0), 1.0)

    def test_symmetric_split_is_not_significant(self):
        # 10 个不一致，5:5 -> p = 1.0
        self.assertAlmostEqual(CMP.binom_two_sided_p(5, 5), 1.0)

    def test_unanimous_small_is_significant(self):
        # 1:0 -> p = 1.0 (两边各 0.5)，不能算显著
        self.assertAlmostEqual(CMP.binom_two_sided_p(1, 0), 1.0)

    def test_6_0_is_significant(self):
        # P(X>=6 | n=6) = 2^-6, 双侧 = 2*2^-6 = 0.03125
        self.assertAlmostEqual(CMP.binom_two_sided_p(6, 0), 2 * (0.5 ** 6))
        self.assertLess(CMP.binom_two_sided_p(6, 0), 0.05)

    def test_10_0_very_significant(self):
        self.assertAlmostEqual(CMP.binom_two_sided_p(10, 0), 2 * (0.5 ** 10))
        self.assertLess(CMP.binom_two_sided_p(10, 0), 0.01)

    def test_asymmetry_is_detected(self):
        self.assertLess(CMP.binom_two_sided_p(9, 1), 0.05)
        self.assertGreater(CMP.binom_two_sided_p(9, 1), 0.0)

    def test_never_exceeds_one(self):
        for b in range(0, 12):
            for c in range(0, 12):
                p = CMP.binom_two_sided_p(b, c)
                self.assertGreaterEqual(p, 0.0)
                self.assertLessEqual(p, 1.0)

    def test_symmetric_in_arguments(self):
        self.assertAlmostEqual(CMP.binom_two_sided_p(3, 7), CMP.binom_two_sided_p(7, 3))


class TestWilson(unittest.TestCase):
    def test_zero_n(self):
        self.assertEqual(CMP.wilson(0, 0), (0.0, 1.0))

    def test_all_success_lower_bound_below_one(self):
        lo, hi = CMP.wilson(30, 30)
        self.assertLess(lo, 1.0)
        self.assertAlmostEqual(hi, 1.0, places=6)

    def test_brackets_point_estimate(self):
        lo, hi = CMP.wilson(27, 30)
        self.assertLess(lo, 0.9)
        self.assertGreater(hi, 0.9)

    def test_narrower_with_more_samples(self):
        lo1, hi1 = CMP.wilson(9, 10)
        lo2, hi2 = CMP.wilson(90, 100)
        self.assertLess((hi2 - lo2), (hi1 - lo1))

    def test_all_fail(self):
        lo, hi = CMP.wilson(0, 10)
        self.assertAlmostEqual(lo, 0.0, places=6)
        self.assertGreater(hi, 0.0)


class TestLoadLabels(unittest.TestCase):
    """只认 verified=True 的样本 —— 未通过的不是真值。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cmp_test_")
        self.path = os.path.join(self.tmp, "samples.jsonl")
        rows = [
            {"sha1": "a" * 40, "label": "ab3d", "verified": True, "result": "ok"},
            {"sha1": "b" * 40, "label": "xxxx", "verified": False,
             "result": "captcha_error"},
            {"sha1": "c" * 40, "label": None, "verified": True, "result": "ok"},
            {"sha1": "d" * 40, "label": "zzzz", "verified": True, "result": "ok"},
        ]
        with open(self.path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.write("{ 这行是坏的 JSON\n")   # 容错

    def test_only_verified_with_label(self):
        t = CMP.load_labels(self.tmp)
        self.assertEqual(set(t), {"a" * 40, "d" * 40})
        self.assertEqual(t["a" * 40], "ab3d")

    def test_survives_corrupt_line(self):
        CMP.load_labels(self.tmp)  # 不抛异常即通过


class TestPositionAgreement(unittest.TestCase):
    def test_counts_same_and_diff_per_position(self):
        truth = {"1" * 40: "ab3d", "2" * 40: "cd3e"}
        a = {"1" * 40: "ab3d", "2" * 40: "cd3x"}
        b = {"1" * 40: "ab3d", "2" * 40: "cd3e"}
        same, diff = CMP.position_agreement(truth, a, b)
        self.assertEqual(diff.get(3, 0), 1, "只有第 4 位分歧")
        self.assertEqual(sum(same.values()), 7)

    def test_skips_length_mismatch(self):
        truth = {"1" * 40: "abcd"}
        a = {"1" * 40: "ab"}      # 位数不对
        b = {"1" * 40: "abcd"}
        same, diff = CMP.position_agreement(truth, a, b)
        self.assertEqual(sum(same.values()) + sum(diff.values()), 0)

    def test_skips_missing_predictions(self):
        truth = {"1" * 40: "abcd"}
        a = {}
        b = {"1" * 40: "abcd"}
        same, diff = CMP.position_agreement(truth, a, b)
        self.assertEqual(sum(diff.values()), 0)


class TestConfusionByChar(unittest.TestCase):
    def test_counts_correct_and_wrong_pairs(self):
        truth = {"1" * 40: "nn", "2" * 40: "nz"}
        pred = {"1" * 40: "nn", "2" * 40: "nr"}
        ok, n = CMP.confusion_by_char(truth, pred)
        # 'nn' 全对 -> 4 个字符位里 3 个是 n(对) + 1 个 n(对)? 实为 3 个 n 对
        self.assertEqual(ok["n"], 3, "3 个 n 正确")
        # 'nz' 预测成 'nr'：错的是**该位真值 z**，不是 n
        self.assertEqual(ok[("z", "r")], 1, "错位应记在真值 z 上")
        self.assertEqual(n["n"], 3)
        self.assertEqual(n["z"], 1)

    def test_error_attributed_to_truth_char_not_pred(self):
        """混淆表的语义：键是「真值字符」的准确次数，tuple 键是 (真值, 预测)。"""
        truth = {"1" * 40: "z"}
        pred = {"1" * 40: "n"}
        ok, n = CMP.confusion_by_char(truth, pred)
        self.assertEqual(ok.get("z", 0), 0, "z 一次都没对")
        self.assertEqual(ok[("z", "n")], 1)
        self.assertEqual(n["z"], 1)
        self.assertNotIn("n", n, "总计数按真值字符，不按预测字符")

    def test_ignores_length_mismatch(self):
        truth = {"1" * 40: "abc"}
        pred = {"1" * 40: "ab"}
        ok, n = CMP.confusion_by_char(truth, pred)
        self.assertEqual(sum(n.values()), 0)


class TestBucketAccuracy(unittest.TestCase):
    def test_partitions_by_confidence(self):
        truth = {f"{i}": "abcd" for i in range(6)}
        pred = dict(truth)
        pred["0"] = "abxX"           # 低置信度桶里的错例
        confs = {"0": 0.5, "1": 0.85, "2": 0.97, "3": 0.995, "4": 0.999, "5": 0.999}
        h, n = CMP.bucket_accuracy(truth, pred, confs, 0.0, 0.8)
        self.assertEqual((h, n), (0, 1))
        h, n = CMP.bucket_accuracy(truth, pred, confs, 0.99, 1.01)
        self.assertEqual((h, n), (3, 3))
        h, n = CMP.bucket_accuracy(truth, pred, confs, 5.0, 6.0)
        self.assertEqual((h, n), (0, 0), "空桶返回 0,0 而不是除零")

    def test_none_confidence_excluded(self):
        truth = {"1": "abcd"}
        h, n = CMP.bucket_accuracy(truth, {"1": "abcd"}, {"1": None}, 0.0, 1.01)
        self.assertEqual((h, n), (0, 0))


class TestPct(unittest.TestCase):
    def test_formatting(self):
        self.assertEqual(CMP.pct(0.5), "50.00%")
        self.assertEqual(CMP.pct(1.0), "100.00%")


if __name__ == "__main__":
    unittest.main(verbosity=2)
