# -*- coding: utf-8 -*-
"""把「切分兜底链」的可观测性固化进评测器。

背景（全部为线上实测，非推断）
--------------------------------
- 整图识别在 39 张已验证样本上 100% 正确
- 切分 + 逐字符 ddddocr 单独跑只有 1/39 = 2.56%
- 但切分链**只在整图被判非法时**才触发，唯一一次触发（`cb32v`，
  整图多吐一个尾随字符）被切分链**正确修正**为 `cb32`
- 切分链每次触发要白烧约 22.9 ms CPU

所以要盯的不是「切分链准确率」，而是两个随规模增长的计数：
    触发次数（整图非法的次数）与 其中被救回的次数
它们才是判断「切分链该留还是该删」的依据。样本量小时任何比例都不可信。

本模块提供 fallback_report()，供 eval_captcha.py 与线上监控调用。
"""
import os
import statistics
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app.schedule import segment  # noqa: E402
from app.schedule.preprocess import preprocess  # noqa: E402
from app.schedule import recognize as R  # noqa: E402


def _classify_illegal(full):
    """把整图的非法输出归类，便于定位失效模式。"""
    if not full:
        return "空输出"
    if not all(c.isascii() for c in full):
        return "含非ASCII"
    if not all(c.isalnum() for c in full):
        return "含非法字符"
    if len(full) > 4:
        return "位数多"
    if len(full) < 4:
        return "位数少"
    return "其它"


def _run_fallback(raw, ocr):
    """复刻 recognize() 的切分兜底链。

    返回 (结果, 耗时ms, 切分段数, 错误原因)。异常**必须回传**而不是静默吞掉：
    早先的版本 `except: pass` 会把 nseg 标成 -1，看不出是「切不出 4 段」
    还是「抛异常」，两种情况对应完全不同的结论。
    """
    t0 = time.perf_counter()
    try:
        bw = preprocess(raw)
        chars, _boxes = segment.segment_chars(bw)
        if len(chars) != 4:
            return None, (time.perf_counter() - t0) * 1000, len(chars), \
                f"切出 {len(chars)} 段（需 4 段）"
        out = []
        for c in chars:
            ok, png = cv2.imencode(".png", c)
            if not ok:
                return None, (time.perf_counter() - t0) * 1000, len(chars), \
                    "cv2.imencode 失败"
            t = ocr.classification(png.tobytes())
            out.append((t or "?")[0])
        return "".join(out), (time.perf_counter() - t0) * 1000, len(chars), None
    except Exception as e:  # noqa: BLE001
        return None, (time.perf_counter() - t0) * 1000, -1, \
            f"{type(e).__name__}: {e}"


def fallback_report(data_dir, truth, limit=None, verbose=True, ocr=None):
    """在评测集上统计切分兜底链的触发与救援情况。

    只在**整图被判非法**的样本上评估切分链 —— 这是它唯一会被触发的场景。
    在整图正确的样本上测切分链没有意义（那正是之前得出错误结论的原因）。

    ocr 允许外部注入，便于测试时替换；缺省时才加载真实模型。

    返回 dict，供调用方落盘或告警。total 只统计**图片确实存在**的样本，
    否则缺失文件会虚增分母。
    """
    if ocr is None:
        ocr = R._get_ddddocr()
    items = list(truth.items())
    if limit:
        items = items[:limit]

    total = 0
    legal = 0
    illegal_kinds = Counter()
    rescued = 0
    rescued_examples = []
    failed_examples = []
    costs = []
    seg_counts = Counter()
    mismatch_examples = []
    errors = []

    for sha, t in sorted(items):
        p = os.path.join(data_dir, "images", f"{sha}.png")
        if not os.path.exists(p):
            continue
        total += 1
        with open(p, "rb") as f:
            raw = f.read()
        full = ocr.classification(raw) or ""
        if R._is_plausible_code(full):
            legal += 1
            continue
        kind = _classify_illegal(full)
        illegal_kinds[kind] += 1
        got, dt, nseg, err = _run_fallback(raw, ocr)
        costs.append(dt)
        seg_counts[nseg] += 1
        if err:
            errors.append(err)
        if got == t:
            rescued += 1
            rescued_examples.append((t, full, got))
        else:
            failed_examples.append((t, full, got, nseg, err))
        if full[:4] == t and len(full) > 4:
            mismatch_examples.append((t, full, got))

    illegal = total - legal
    report = {
        "total": total,
        "whole_image_legal": legal,
        "whole_image_illegal": illegal,
        "illegal_kinds": dict(illegal_kinds),
        "fallback_rescued": rescued,
        "fallback_rescue_rate": (rescued / illegal) if illegal else None,
        "fallback_cost_ms_median": round(statistics.median(costs), 1) if costs else 0.0,
        "fallback_seg_counts": {str(k): v for k, v in sorted(seg_counts.items())},
        "fallback_errors": errors,
        "rescued_examples": rescued_examples,
        "failed_examples": failed_examples,
        "tail_hallucination_examples": mismatch_examples,
    }

    if verbose:
        print("=" * 72)
        print("[D] 切分兜底链观测（只在整图非法时评估）")
        print("=" * 72)
        print(f"  已验证样本        : {total}")
        print(f"  整图合法          : {legal}")
        print(f"  整图非法（触发点）: {illegal}")
        for k, v in illegal_kinds.most_common():
            print(f"      {k}: {v}")
        if illegal:
            print(f"  切分链救回        : {rescued}"
                  f"   救援率 {rescued / illegal * 100:.1f}%")
            print(f"  单次触发耗时      : {report['fallback_cost_ms_median']} ms (中位)")
            print(f"  切分段数分布      : {report['fallback_seg_counts']}")
            for t, full, got in rescued_examples[:5]:
                print(f"      救回: 真值 {t!r}  整图 {full!r}  切分 {got!r}")
            for t, full, got, ns, err in failed_examples[:5]:
                print(f"      未救回: 真值 {t!r}  整图 {full!r}  切分 {got!r}"
                      f" (段数 {ns})" + (f"  原因: {err}" if err else ""))
            if errors:
                print(f"  兜底链内部异常: {len(errors)} 次，样例 {errors[0]!r}")
            if mismatch_examples:
                print(f"  整图尾随幻觉（前4位正确但多吐字符）: {len(mismatch_examples)} 例")
                for t, full, got in mismatch_examples[:5]:
                    print(f"      {t!r} <- 整图 {full!r}  切分修正为 {got!r}")
        else:
            print("  本批样本中整图从未非法 -> 切分链从未被触发。")
        print()
        print("  判读（切分链留还是删）:")
        print("    - 整图非法长期为 0            -> 死代码，可删 preprocess/segment")
        print("    - 偶发且多数能救回            -> 保留，它是有效保险")
        print("    - 偶发但基本救不回            -> 删掉，平均省 "
              f"{report['fallback_cost_ms_median']}ms × 触发率")
        print("    - 当前平均成本 = 触发率 × 单次耗时 = "
              f"{(illegal / total * report['fallback_cost_ms_median']) if total else 0:.2f} ms/次")
        print("    注：单批样本量小，比例不可信，要看两个**绝对计数**随规模的变化。")
        print("=" * 72)
    return report


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/data/captcha_eval")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    truth = {}
    with open(os.path.join(args.data, "samples.jsonl"), encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if r.get("verified") and r.get("label"):
                truth[r["sha1"]] = r["label"]
    rep = fallback_report(args.data, truth, limit=args.limit or None)
    out = os.path.join(args.data, "fallback_report.json")
    rep_clean = {k: v for k, v in rep.items() if k != "failed_examples"}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep_clean, f, ensure_ascii=False, indent=1)
    print(f"\n已写入 {out}")
