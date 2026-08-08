# -*- coding: utf-8 -*-
"""抓取验证码建立模板库 + 流程可行性测试。

子命令：
    fetch  <n>        抓取 n 张验证码到 samples/raw/
    segstats          对 raw 目录所有图片做预处理+切割，统计 4 字符切割成功率
    label             用 CNN 对切出的字符伪标注（需先 python train.py）
    sheet             生成标注拼图 samples/contact_sheet.png 供人工核对
    build [--max N]   把伪标注字符写入 models/templates/<标签>/（每标签最多 N 张）
    test   <n>        现场抓取 n 张新验证码，用模板库识别并统计
"""
import argparse
import os
import time

import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "samples", "raw")
CUT_DIR = os.path.join(BASE_DIR, "samples", "cuts")
TEMPLATE_DIR = os.path.join(BASE_DIR, "models", "templates")

from preprocess import preprocess, load_image
from segment import segment_chars


def get_session():
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"})
    return s


def fetch_captcha(session):
    for _ in range(2):  # 网络抖动重试
        try:
            r = session.get(
                "http://newjwxt.bjfu.edu.cn/verifycode.servlet",
                params={"t": __import__("random").random()}, timeout=6,
            )
            return r.content
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("验证码下载失败（重试 2 次）")


def fetch_many(n, workers=8):
    """并行下载 n 张验证码，返回 [(序号, bytes), ...]。"""
    from concurrent.futures import ThreadPoolExecutor

    def _one(i):
        try:
            return i, fetch_captcha(get_session())
        except Exception as e:
            print(f"[{i}] 下载失败: {e}", flush=True)
            return i, None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return [r for r in sorted(ex.map(_one, range(n))) if r[1] is not None]


def cmd_fetch(args):
    os.makedirs(RAW_DIR, exist_ok=True)
    t0 = time.time()
    items = fetch_many(args.n)
    for i, data in items:
        name = time.strftime("%Y%m%d_%H%M%S") + f"_{i:03d}"
        cv2.imwrite(os.path.join(RAW_DIR, name + ".png"), load_image(data))
    print(f"成功抓取 {len(items)}/{args.n} 张 -> {RAW_DIR}，"
          f"耗时 {time.time() - t0:.1f}s", flush=True)


def _raw_images():
    if not os.path.isdir(RAW_DIR):
        return []
    return sorted(
        os.path.join(RAW_DIR, f) for f in os.listdir(RAW_DIR)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    )


def cmd_segstats(_args):
    """统计切割成功率：能否稳定切出 4 个字符。"""
    paths = _raw_images()
    if not paths:
        print("samples/raw/ 为空，请先运行 fetch")
        return
    n4 = 0
    for p in paths:
        binary = preprocess(cv2.imread(p))
        chars, boxes = segment_chars(binary)
        widths = [b[2] for b in boxes]
        if len(chars) == 4:
            n4 += 1
        print(f"{os.path.basename(p)}: 切出{len(chars)}个字符 宽度={widths}")
    print(f"\n切割成功率(恰好4个): {n4}/{len(paths)} = {n4 / len(paths):.1%}")


def _cnn_predictor():
    from recognize import _load_cnn, _cnn_char
    if _load_cnn() is None:
        raise SystemExit("未找到 models/cnn.pth，请先运行: py train.py")
    return _cnn_char


def cmd_label(_args):
    """CNN 伪标注：切图保存到 samples/cuts/，标签写入 labels.txt。"""
    os.makedirs(CUT_DIR, exist_ok=True)
    predict = _cnn_predictor()
    paths = _raw_images()
    lines = []
    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        binary = preprocess(cv2.imread(p))
        chars, boxes = segment_chars(binary)
        if len(chars) != 4:
            print(f"{name}: 切出{len(chars)}个字符，跳过")
            continue
        labels = []
        for j, ch in enumerate(chars):
            cv2.imwrite(os.path.join(CUT_DIR, f"{name}_c{j}.png"), ch)
            label, prob = predict(ch)
            labels.append(label)
        code = "".join(labels)
        lines.append(f"{name} {code}")
        print(f"{name} -> {code}")
    with open(os.path.join(CUT_DIR, "labels.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n共标注 {len(lines)} 张，标签文件: {os.path.join(CUT_DIR, 'labels.txt')}")


def cmd_sheet(_args):
    """生成人工核对用的拼图：原图 + 4 个切图 + 预测标签。

    每 15 行一张拼图，输出 samples/contact_sheet_<k>.png。
    """
    label_file = args.labels
    if not os.path.isfile(label_file):
        raise SystemExit("请先运行 label")
    cut_dir = os.path.dirname(label_file)
    entries = []
    with open(label_file, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2:
                entries.append((parts[0], parts[1]))

    row_h, scale, per_sheet = 56, 2, 15
    for k in range(0, len(entries), per_sheet):
        chunk = entries[k:k + per_sheet]
        sheet = np.full((row_h * len(chunk) + 10, 500, 3), 255, np.uint8)
        for i, (name, code) in enumerate(chunk):
            y0 = i * row_h + 5
            raw = cv2.imread(os.path.join(RAW_DIR, name + ".png"))
            raw = cv2.resize(raw, (raw.shape[1] * scale, raw.shape[0] * scale),
                             interpolation=cv2.INTER_NEAREST)
            sheet[y0:y0 + raw.shape[0], 10:10 + raw.shape[1]] = raw
            x = 200
            for j in range(4):
                cpath = os.path.join(cut_dir, f"{name}_c{j}.png")
                if not os.path.isfile(cpath):
                    continue
                ch = cv2.imread(cpath, cv2.IMREAD_GRAYSCALE)
                ch = cv2.resize(ch, (40, 40), interpolation=cv2.INTER_NEAREST)
                ch = cv2.cvtColor(ch, cv2.COLOR_GRAY2BGR)
                sheet[y0 + 8:y0 + 48, x:x + 40] = ch
                cv2.putText(sheet, code[j] if j < len(code) else "?",
                            (x + 8, y0 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 0, 200), 2)
                x += 70
        out = os.path.join(BASE_DIR, "samples", f"contact_sheet_{k // per_sheet}.png")
        cv2.imwrite(out, sheet)
        print("拼图已保存:", out)


def cmd_build(args):
    """把伪标注字符写入模板库，每个标签最多 args.max 张。"""
    if args.clean:
        import shutil
        for d in os.listdir(TEMPLATE_DIR):
            p = os.path.join(TEMPLATE_DIR, d)
            if os.path.isdir(p):
                shutil.rmtree(p)
        print("已清空模板库")
    label_file = os.path.join(CUT_DIR, "labels.txt")
    with open(label_file, encoding="utf-8") as f:
        entries = [line.split() for line in f if len(line.split()) == 2]
    counts = {}
    skipped = 0
    for name, code in entries:
        # 重新分割拿切割框，宽度 < 4 的切图是笔画碎片，不入模板库
        raw = os.path.join(RAW_DIR, name + ".png")
        boxes = None
        if os.path.isfile(raw):
            _, boxes = segment_chars(preprocess(cv2.imread(raw)))
        for j, label in enumerate(code):
            if boxes is not None and (j >= len(boxes) or boxes[j][2] < 4):
                skipped += 1
                continue
            d = os.path.join(TEMPLATE_DIR, label)
            os.makedirs(d, exist_ok=True)
            if counts.get(label, 0) >= args.max:
                continue
            src = os.path.join(CUT_DIR, f"{name}_c{j}.png")
            if os.path.isfile(src):
                dst = os.path.join(d, f"{name}_c{j}.png")
                if not os.path.isfile(dst):
                    cv2.imwrite(dst, cv2.imread(src))
                    counts[label] = counts.get(label, 0) + 1
    print(f"跳过碎片切图 {skipped} 张")
    total = sum(len(os.listdir(os.path.join(TEMPLATE_DIR, d)))
                for d in os.listdir(TEMPLATE_DIR)
                if os.path.isdir(os.path.join(TEMPLATE_DIR, d)))
    print(f"模板库已建立: {TEMPLATE_DIR}，共 {total} 张模板，"
          f"覆盖 {sum(1 for d in os.listdir(TEMPLATE_DIR)
                      if os.path.isdir(os.path.join(TEMPLATE_DIR, d)))} 个字符类别")


def cmd_recut(args):
    """按已有 labels.txt 重新切割原图（预处理改进后刷新切图）。"""
    label_file = args.labels
    cut_dir = os.path.dirname(os.path.abspath(label_file))
    os.makedirs(cut_dir, exist_ok=True)
    bad = 0
    for line in open(label_file, encoding="utf-8"):
        parts = line.split()
        if len(parts) != 2:
            continue
        name, code = parts
        raw = os.path.join(RAW_DIR, name + ".png")
        if not os.path.isfile(raw):
            continue
        binary = preprocess(cv2.imread(raw))
        chars, boxes = segment_chars(binary)
        if len(chars) != 4:
            print(f"{name}: 切出{len(chars)}个字符，跳过", flush=True)
            bad += 1
            continue
        for j, ch in enumerate(chars):
            cv2.imwrite(os.path.join(cut_dir, f"{name}_c{j}.png"), ch)
        print(f"{name}: 宽度={[b[2] for b in boxes]}", flush=True)
    print(f"重切完成，异常 {bad} 张", flush=True)


def cmd_test(args):
    """现场抓取新验证码，用模板库识别，并保存评估数据供拼图核对。"""
    from recognize import TemplateMatcher
    matcher = TemplateMatcher()
    if not matcher.templates:
        raise SystemExit("模板库为空，请先运行 build")
    print(f"模板库: {len(matcher.templates)} 类，"
          f"{sum(len(v) for v in matcher.templates.values())} 张\n")

    eval_dir = os.path.join(BASE_DIR, "samples", "eval_cuts")
    os.makedirs(eval_dir, exist_ok=True)
    lines = []
    t0 = time.time()
    for i, data in fetch_many(args.n):
        name = f"eval_{i:03d}"
        img = load_image(data)
        cv2.imwrite(os.path.join(RAW_DIR, name + ".png"), img)
        binary = preprocess(img)
        chars, _ = segment_chars(binary)
        if len(chars) != 4:
            print(f"[{i}] 切割失败: {len(chars)} 个字符", flush=True)
            continue
        parts = []
        for j, ch in enumerate(chars):
            cv2.imwrite(os.path.join(eval_dir, f"{name}_c{j}.png"), ch)
            label, score = matcher.match(ch)
            parts.append(f"{label}({score:.3f})")
        lines.append(f"{name} {''.join(p[0] for p in parts)}")
        print(f"[{i}] " + " ".join(parts), flush=True)
    with open(os.path.join(eval_dir, "labels.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"耗时 {time.time() - t0:.1f}s。评估数据已保存，运行以下命令生成核对拼图：\n"
          f"  py build_templates.py sheet --labels {os.path.join(eval_dir, 'labels.txt')}",
          flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch"); p.add_argument("n", type=int)
    p.set_defaults(func=cmd_fetch)
    sub.add_parser("segstats").set_defaults(func=cmd_segstats)
    sub.add_parser("label").set_defaults(func=cmd_label)
    p = sub.add_parser("sheet")
    p.add_argument("--labels", default=os.path.join(CUT_DIR, "labels.txt"))
    p.set_defaults(func=cmd_sheet)
    p = sub.add_parser("build"); p.add_argument("--max", type=int, default=3)
    p.add_argument("--clean", action="store_true")
    p.set_defaults(func=cmd_build)
    p = sub.add_parser("recut")
    p.add_argument("--labels", default=os.path.join(CUT_DIR, "labels.txt"))
    p.set_defaults(func=cmd_recut)
    p = sub.add_parser("test"); p.add_argument("n", type=int)
    p.set_defaults(func=cmd_test)
    args = parser.parse_args()
    args.func(args)
