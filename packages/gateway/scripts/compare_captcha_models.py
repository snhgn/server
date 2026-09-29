# -*- coding: utf-8 -*-
"""验证码模型配对比较（McNemar）。

为什么必须配对比较
------------------
两个模型在同一批验证码上各跑一遍，评的是**同一批图**，所以样本之间是配对的。
配对设计能消掉「这张图本身难不难」的影响：只有「A 对 B 错」和「A 错 B ��」
这两类格子提供信息量。若准确率都在 98%+，靠各自的独立准确率去比，
需要的样本量会大一个数量级；McNemar 只看不一致计数。

用法
----
  # 1) 采集一份评测集（标签经服务端放行验证）
  python collect_captcha_samples.py --out /data/captcha_eval --total 600

  # 2) 在同一集合上分别跑两个模型，各自导出预测
  python eval_captcha.py --data /data/captcha_eval --rerun --dump-fail 20
  CAPTCHA_OCR_MODEL=beta python eval_captcha.py --data /data/captcha_eval --rerun

  # 3) 配对比较
  python compare_captcha_models.py --data /data/captcha_eval

统计口径
--------
- b = 仅 A 对、B 错（b 越大 A 越好）
- c = 仅 A 错、B 对（c 越大 B 越好）
- 精确二项检验：在「真实无差异」的零假设下，b+c 个不一致样本中
  每个落在任一侧的概率都是 0.5，因此 p 值 = 2·P(X>=max(b,c))，
  取 min(1, ·)。用精确法而非卡方，因为不一致样本通常很少（个位数到几十），
  卡方近似在这个量级不可靠。
- 同时给 Wilson 区间，不依赖正态近似。
"""
import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app.schedule import recognize as R  # noqa: E402


# ------------------------------------------------------------------ 统计工具
def wilson(k, n, z=1.96):
    """Wilson 得分区间：小样本下比正态近似稳健。"""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def binom_two_sided_p(b, c):
    """精确双侧二项检验 p 值（零假设 b~Bin(b+c, 0.5)）。"""
    n = b + c
    if n == 0:
        return 1.0
    k = max(b, c)
    tail = 0.0
    for i in range(k, n + 1):
        tail += math.comb(n, i) * (0.5 ** n)
    return min(1.0, 2.0 * tail)


def pct(x):
    return f"{x * 100:.2f}%"


# ------------------------------------------------------------------ 数据与预测
def load_labels(data_dir):
    """读采集记录，取 verified=True 的作为可信真值。"""
    p = os.path.join(data_dir, "samples.jsonl")
    truth = {}
    with open(p, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if r.get("verified") and r.get("label"):
                truth[r["sha1"]] = r["label"]
    return truth


def run_model(data_dir, shas, model):
    """在一个子进程里加载指定模型（通过环境变量）并对每张图出预测。

    ddddocr 的模型在进程初始化时选定，无法在同一进程内热切换，
    所以这里通过 os.environ + 就地重置单例来切换。
    """
    os.environ["CAPTCHA_OCR_MODEL"] = model
    import app.schedule.recognize as RR
    RR._ddddocr = None
    RR._pinned = False

    preds = {}
    confs = {}
    for i, sha in enumerate(shas):
        path = os.path.join(data_dir, "images", f"{sha}.png")
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            raw = f.read()
        code = RR.recognize(raw)
        st = RR.ocr_stats()
        preds[sha] = code
        confs[sha] = st["last_weakest"]
        if (i + 1) % 100 == 0:
            print(f"    [{model}] {i + 1}/{len(shas)}", flush=True)
    return preds, confs


# ------------------------------------------------------------------ 分析
def position_agreement(truth, pred_a, pred_b):
    """逐位看：两个模型在同一位置是否给出相同字符。定位分歧发生在哪一位。"""
    pos_same = Counter()
    pos_diff = Counter()
    for sha, t in truth.items():
        a, b = pred_a.get(sha), pred_b.get(sha)
        if not a or not b or len(a) != len(t) or len(b) != len(t):
            continue
        for i, (x, y) in enumerate(zip(a, b)):
            if x == y:
                pos_same[i] += 1
            else:
                pos_diff[i] += 1
    return pos_same, pos_diff


def confusion_by_char(truth, pred):
    """真值字符 -> 预测字符 的混淆统计（定位系统性错误模式）。

    返回 (命中计数, 字符位总数)：
      命中计数里，str 键是该字符的**正确**次数，tuple 键是 (真值, 预测) 的错误次数。
      两者分开是为了能分别按字符算准确率、又能列出混淆对。
    """
    correct = Counter()
    total = Counter()
    for sha, t in truth.items():
        p = pred.get(sha)
        if not p or len(p) != len(t):
            continue
        for a, b in zip(t, p):
            total[a] += 1
            if a == b:
                correct[a] += 1
            else:
                correct[(a, b)] = correct.get((a, b), 0) + 1
    return correct, total


def bucket_accuracy(truth, pred, confs, lo, hi):
    """置信度区间 [lo, hi) 内的准确率，返回 (命中数, 样本数)。

    置信度为 None 的样本必须排除，否则会被算进最低桶里。
    """
    sel = [s for s, c in confs.items() if c is not None and lo <= c < hi
           and s in truth and pred.get(s)]
    if not sel:
        return 0, 0
    hit = sum(1 for s in sel if pred[s] == truth[s])
    return hit, len(sel)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--min-n", type=int, default=30,
                    help="低于此样本量只提示不下结论")
    args = ap.parse_args()

    truth = load_labels(args.data)
    shas = sorted(truth)
    print("=" * 74)
    print(f"配对比较  数据: {args.data}")
    print(f"  可信真值 {len(truth)} 张")
    print("=" * 74)
    if not shas:
        print("没有可用样本，请先跑 collect_captcha_samples.py")
        return 1

    # ---- 两个模型在同一集合上出预测 ----
    print()
    print("[1] 跑模型 A（old，13MB）…")
    pa, ca = run_model(args.data, shas, "old")
    print("[2] 跑模型 B（beta，52MB）…")
    pb, cb = run_model(args.data, shas, "beta")

    # ---- 单模型表现 ----
    print()
    print("=" * 74)
    print("[3] 各自整体表现")
    print("=" * 74)
    for name, pred in (("old", pa), ("beta", pb)):
        both = [s for s in shas if pred.get(s)]
        hit = sum(1 for s in both if pred[s] == truth[s])
        lo, hi = wilson(hit, len(both))
        print(f"  {name:5} 整图准确率 {hit}/{len(both)} = {pct(hit / max(len(both),1))}"
              f"   95%CI [{pct(lo)}, {pct(hi)}]")
        # 门控拒绝（识别不出合法码）
        rej = len(both) - sum(1 for s in both if R._is_plausible_code(pred[s]))
        if rej:
            print(f"        其中 {rej} 张被接受门控判为不可信")

    # ---- McNemar 配对表 ----
    print()
    print("=" * 74)
    print("[4] McNemar 配对表（只有不一致样本提供信息）")
    print("=" * 74)
    b = c = both_right = both_wrong = 0
    for s in shas:
        if not pa.get(s) or not pb.get(s):
            continue
        oa = pa[s] == truth[s]
        ob = pb[s] == truth[s]
        if oa and ob:
            both_right += 1
        elif not oa and not ob:
            both_wrong += 1
        elif oa:
            b += 1
        else:
            c += 1

    print(f"  {'':>18}{'beta 对':>10}{'beta 错':>10}")
    print(f"  {'old 对':>18}{both_right:>10}{b:>10}")
    print(f"  {'old 错':>18}{c:>10}{both_wrong:>10}")
    print()
    print(f"  仅 old 对（old 更好）  b = {b}")
    print(f"  仅 beta 对（beta 更好）c = {c}")
    print(f"  不一致合计            {b + c}")
    if b + c:
        p = binom_two_sided_p(b, c)
        print(f"  精确双侧 p 值         {p:.4f}"
              f"   {'显著' if p < 0.05 else '不显著（无法判定优劣）'}")
        if b + c:
            print(f"  不一致率              {(b + c) / max(both_right + b + c + both_wrong, 1) * 100:.2f}%")
    else:
        print("  两模型在这批样本上完全一致，无法区分（需要更多难例）")

    # ---- 结论 ----
    print()
    print("=" * 74)
    print("[5] 结论")
    print("=" * 74)
    n_eval = both_right + b + c + both_wrong
    if n_eval < args.min_n:
        print(f"  样本量 {n_eval} < {args.min_n}，**不下结论**，只报告数字。")
        print("  建议继续采集到 300~600 张再判。")
    elif b + c == 0:
        print("  两模型预测完全一致。")
        print("  - 若两者准确率都已很高，说明当前瓶颈不在模型，换模型没有意义；")
        print("  - 建议把精力转向「更难样本」（见下面 [6] 的置信度分桶）。")
    else:
        p = binom_two_sided_p(b, c)
        if p >= 0.05:
            print(f"  差异不显著（p={p:.3f}，不一致 {b + c} 个）。")
            print("  换模型没有可测量的收益，不建议为此增加 39MB 内存占用。")
        else:
            better = "old" if b > c else "beta"
            print(f"  差异显著（p={p:.4f}）：**{better} 更好**。")
            gain = abs(b - c) / max(n_eval, 1)
            print(f"  净收益 {gain * 100:.2f} 个百分点。")
            if better == "beta":
                print("  切换方式：容器环境加 CAPTCHA_OCR_MODEL=beta 后重启 gateway。")
                print("  代价：模型 13MB -> 52MB，gateway 内存上限 384MB 需留意。")

    # ---- 分歧定位 ----
    print()
    print("=" * 74)
    print("[6] 分歧定位")
    print("=" * 74)
    pos_same, pos_diff = position_agreement(truth, pa, pb)
    if pos_diff:
        print("  逐位分歧次数（第 1/2/3/4 位）:")
        for i in range(4):
            same, diff = pos_same.get(i, 0), pos_diff.get(i, 0)
            if same + diff:
                print(f"    位{i+1}: 相同 {same:4}  分歧 {diff:3}")
    else:
        print("  逐位比较：无分歧")

    print()
    print("  置信度分桶（old 模型，判断低置信度是否真是难例）:")
    for lo, hi in ((0.0, 0.8), (0.8, 0.95), (0.95, 0.99), (0.99, 1.01)):
        h, n = bucket_accuracy(truth, pa, ca, lo, hi)
        if n:
            print(f"    [{lo:.2f},{hi:.2f})  n={n:4}  准确率 {h / n * 100:6.1f}%")
    print("  => 若低置信度桶准确率同样很高，说明置信度不能当拒识信号；")
    print("     反之则可以用来做「低置信度时重试」的门控。")

    print()
    print("  old 模型的字符混淆（真值 -> 预测，出现 >=2 次的）:")
    c_ok, c_n = confusion_by_char(truth, pa)
    rows = [(k, v) for k, v in c_ok.items()
            if isinstance(k, tuple) and v >= 2]
    if rows:
        for (a, b_), v in sorted(rows, key=lambda x: -x[1]):
            print(f"    {a} -> {b_}  x{v}")
    else:
        print("    无重复混淆模式")

    # ---- 落盘结果，便于复查 ----
    out = os.path.join(args.data, "compare.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "n": n_eval,
            "old_correct": both_right + b,
            "beta_correct": both_right + c,
            "b_only_old": b, "c_only_beta": c,
            "both_right": both_right, "both_wrong": both_wrong,
            "p_value": binom_two_sided_p(b, c) if (b + c) else None,
            "preds_old": pa, "preds_beta": pb,
        }, f, ensure_ascii=False, indent=1)
    print()
    print(f"明细已写入 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
