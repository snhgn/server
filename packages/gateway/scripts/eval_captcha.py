# -*- coding: utf-8 -*-
"""验证码评测器：读 samples.jsonl，算准确率 / 逐位准确率 / 置信度分桶。

这是「把准确率变成可测量数字」的那一步。数据由
scripts/collect_captcha_samples.py 用登录接口当标注器采集而来
（标签经过服务端放行验证，因此是可信真值）。

用法：
  python eval_captcha.py --data /data/captcha_eval
  python eval_captcha.py --data /data/captcha_eval --model beta   # 跑 beta 模型对比
  python eval_captcha.py --data /data/captcha_eval --dump-fail 5   # 导出错例
"""
import argparse
import glob
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app.schedule import recognize as R  # noqa: E402


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def load(data_dir):
    """读记录；verified=True 的才是可信真值。"""
    p = os.path.join(data_dir, "samples.jsonl")
    rows = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:  # noqa: BLE001
                continue
    return rows


def predict_all(rows, data_dir, batch_every=1):
    """在评测集上重新跑一遍当前模型，得到逐样本预测。"""
    out = []
    for i, r in enumerate(rows):
        img_path = os.path.join(data_dir, "images", f"{r['sha1']}.png")
        if not os.path.exists(img_path):
            continue
        with open(img_path, "rb") as f:
            raw = f.read()
        code = R.recognize(raw)
        st = R.ocr_stats()
        out.append({
            "sha1": r["sha1"], "truth": r.get("label"),
            "pred": code, "verified": r.get("verified", False),
            "conf_mean": st["last_mean"], "conf_weakest": st["last_weakest"],
            "collect_conf_mean": r.get("conf_mean"),
        })
        if (i + 1) % 100 == 0:
            print(f"    ...已重跑 {i + 1}/{len(rows)}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--rerun", action="store_true",
                    help="重新跑当前模型（否则直接用采集时记录的标签算准确率）")
    ap.add_argument("--dump-fail", type=int, default=0,
                    help="导出 N 个错例图片到 <data>/fails/")
    ap.add_argument("--no-fallback", action="store_true",
                    help="跳过切分兜底链观测（该步骤较慢）")
    args = ap.parse_args()

    rows = load(args.data)
    verified = [r for r in rows if r.get("verified") and r.get("label")]
    unverified = [r for r in rows if not r.get("verified")]

    print("=" * 72)
    print(f"评测集: {args.data}")
    print(f"  总记录 {len(rows)}   已验证真值 {len(verified)}   未通过 {len(unverified)}")
    print(f"  当前模型: {R.ocr_model_name()}   pin={R.ocr_stats().get('pin_applied')}")
    print("=" * 72)

    # ---- 采集时的通过率 = 当次 top-1 准确率（服务端验证过）----
    n = len(verified)
    rej = [r for r in unverified if r.get("result") == "captcha_error"]
    no_code = [r for r in unverified if r.get("result") == "no_code"]
    if n:
        lo, hi = wilson(n, n + len(rej))
        print()
        print(f"[A] 采集时 top-1 准确率: {n}/{n + len(rej)} = "
              f"{n / (n + len(rej)) * 100:.2f}%   95%CI [{lo * 100:.1f}%, {hi * 100:.1f}%]")
    if no_code:
        print(f"    另有 {len(no_code)} 张识别不出合法码（门控拒绝，占 "
              f"{len(no_code) / max(len(rows), 1) * 100:.1f}%）")

    if args.rerun and verified:
        print()
        print("[B] 用当前模型重跑评测集…")
        R._get_ddddocr()
        items = predict_all(verified, args.data)
        hit = sum(1 for t in items if t["pred"] == t["truth"])
        lo, hi = wilson(hit, len(items))
        print(f"    整图准确率: {hit}/{len(items)} = {hit / max(len(items),1) * 100:.2f}%"
              f"   95%CI [{lo*100:.1f}%, {hi*100:.1f}%]")

        # 逐位准确率
        pos_hit = pos_n = 0
        pos_conf = defaultdict(lambda: [0, 0])
        for t in items:
            for i, (a, b) in enumerate(zip(t["truth"], t["pred"] or "")):
                pos_n += 1
                good = a == b
                pos_hit += good
                pos_conf[i][0] += good
                pos_conf[i][1] += 1
        if pos_n:
            print(f"    逐位准确率: {pos_hit}/{pos_n} = "
                  f"{pos_hit / pos_n * 100:.2f}%  (整图错一位也会拉低此值)")

        # 逐字符（按真值字符）
        ch_hit, ch_n = Counter(), Counter()
        for t in items:
            for a, b in zip(t["truth"], t["pred"] or ""):
                ch_n[a] += 1
                ch_hit[a] += (a == b)
        print()
        print("    按字符:")
        for ch in sorted(ch_n, key=lambda c: ch_hit[c] / ch_n[c]):
            h, k = ch_hit[ch], ch_n[ch]
            flag = "  <-- 最弱" if h / k < 0.95 else ""
            print(f"      {ch}  {h:4}/{k:<4} {h / k * 100:6.1f}%{flag}")

        # 置信度 vs 正确性
        print()
        print("    置信度分桶（最低位置信度）:")
        buckets = [(0.0, 0.7), (0.7, 0.9), (0.9, 0.99), (0.99, 1.01)]
        for lo_c, hi_c in buckets:
            sel = [t for t in items
                   if t["conf_weakest"] is not None and lo_c <= t["conf_weakest"] < hi_c]
            if not sel:
                continue
            h = sum(1 for t in sel if t["pred"] == t["truth"])
            print(f"      [{lo_c:.2f},{hi_c:.2f})  n={len(sel):4}  准确率 {h/len(sel)*100:6.1f}%")

        fails = [t for t in items if t["pred"] != t["truth"]]
        print()
        print(f"    错例 {len(fails)} 个")
        for t in fails[:10]:
            print(f"      真值 {t['truth']}  预测 {t['pred']}  "
                  f"weakest={t['conf_weakest']}")
        if args.dump_fail and fails:
            fd = os.path.join(args.data, "fails")
            os.makedirs(fd, exist_ok=True)
            for t in fails[:args.dump_fail]:
                src = os.path.join(args.data, "images", f"{t['sha1']}.png")
                if os.path.exists(src):
                    with open(src, "rb") as a, \
                            open(os.path.join(fd, f"{t['sha1']}_"
                                                 f"{t['truth']}_{t['pred']}.png"), "wb") as b:
                        b.write(a.read())
            print(f"    已导出 {min(args.dump_fail, len(fails))} 个错例到 {fd}")

    # ---- 字符分布：这决定了该训多少类的模型 ----
    if verified:
        print()
        print("=" * 72)
        print("[C] 已验证样本的字符分布")
        print("=" * 72)
        cnt = Counter()
        for r in verified:
            cnt.update(r["label"])
        chars = sorted(cnt)
        print(f"  出现过的不同字符: {len(chars)}")
        print(f"  {' '.join(chars)}")
        print(f"  频次: {'  '.join(f'{c}:{cnt[c]}' for c in chars)}")
        letters = [c for c in chars if c.isalpha()]
        digits = [c for c in chars if c.isdigit()]
        print(f"  字母 {len(letters)} 个，数字 {len(digits)} 个")
        print()
        print("  => 真实字符集是「小写字母 + 数字」的子集，不是 8210 类 Unicode。")
        print("     这就是「训练 63 类专用模型」的依据（见 analyze 结论）。")

    # ---- 切分兜底链观测：判断它是有效保险还是死代码 ----
    # 固化在这里而不是每次手动跑探针，是因为要盯的是**绝对计数随规模的变化**，
    # 而不是某个小样本下的比例（n=1 时「救援率 100%」毫无意义）。
    if verified and not args.no_fallback:
        from captcha_fallback_report import fallback_report
        truth = {r["sha1"]: r["label"] for r in verified}
        print()
        rep = fallback_report(args.data, truth)
        out = os.path.join(args.data, "fallback_report.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in rep.items() if k != "failed_examples"},
                      f, ensure_ascii=False, indent=1)
        print(f"  已写入 {out}")


if __name__ == "__main__":
    main()
