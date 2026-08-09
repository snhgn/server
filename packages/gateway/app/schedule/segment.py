# -*- coding: utf-8 -*-
"""字符分割模块：字符区域检测、粘连字符处理、单字符切割与归一化。

所有定位基于竖直投影，对图片尺寸、字符间距变化自适应。
（迁移自 schedule-pipeline/captcha_solver/segment.py，逻辑未改动）
"""
import cv2
import numpy as np

EXPECTED_CHARS = 4
CHAR_SIZE = (28, 28)


def content_bbox(binary):
    """整幅图的前景内容外接框，返回 (x0, y0, x1, y1)，无前景返回 None。"""
    ys, xs = np.where(binary > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def vertical_projection(region):
    """每一列的前景像素数。"""
    return (region > 0).sum(axis=0)


def _split_points(proj, n_split):
    """在投影序列上选 n_split-1 个切分点。

    在每个等分理想位置附近的窗口内取投影最小值作为切点，
    对粘连字符块比全局谷底排序更稳健。
    """
    w = len(proj)
    if n_split <= 1 or w < n_split:
        return []
    pts = []
    for k in range(1, n_split):
        ideal = k * w / n_split
        half = w / (2 * n_split)
        lo = max(1, int(ideal - half))
        hi = min(w - 1, int(ideal + half) + 1)
        best = min(range(lo, hi), key=lambda x: (int(proj[x]), abs(x - ideal)))
        pts.append(best)
    return sorted(set(pts))


def _split_range(rx, rw, proj_seg, n):
    """把 [rx, rx+rw) 区间按投影切成 n 段，返回 [(x, w), ...]。"""
    if n <= 1:
        return [(rx, rw)]
    pts = _split_points(proj_seg, n)
    bounds = [0] + pts + [rw]
    return [(rx + bounds[i], bounds[i + 1] - bounds[i]) for i in range(n)]


def find_char_regions(binary, expected=EXPECTED_CHARS):
    """检测字符列区域：粘连拆分 + 噪点过滤 + 数量校正。

    返回按 x 排序的 [(x, w), ...]，坐标基于内容外接框所在的裁剪图。
    """
    bbox = content_bbox(binary)
    if bbox is None:
        return [], None
    x0, y0, x1, y1 = bbox
    core = binary[y0:y1 + 1, x0:x1 + 1]
    proj = vertical_projection(core)

    # 1. 连续墨迹列段
    runs, in_run, start = [], False, 0
    for i, v in enumerate(proj):
        if v > 0 and not in_run:
            start, in_run = i, True
        elif v == 0 and in_run:
            runs.append((start, i - start))
            in_run = False
    if in_run:
        runs.append((start, len(proj) - start))
    if not runs:
        return [], None

    # 1.5 碎片合并：宽度 < MIN_W 的列段是单字符内的笔画断裂，
    #     并入间隔更小的相邻列段（n/m 等字符的竖直投影常有 1px 零列）
    MIN_W = 4
    merged = True
    while merged:
        merged = False
        for idx, (x, w) in enumerate(runs):
            if w >= MIN_W or len(runs) == 1:
                continue
            left_gap = (x - (runs[idx - 1][0] + runs[idx - 1][1])) if idx > 0 else 10 ** 9
            right_gap = (runs[idx + 1][0] - (x + w)) if idx + 1 < len(runs) else 10 ** 9
            if idx > 0 and left_gap <= right_gap:
                px, _ = runs[idx - 1]
                runs[idx - 1] = (px, x + w - px)
                runs.pop(idx)
            elif idx + 1 < len(runs):
                nx, nw = runs[idx + 1]
                runs[idx] = (x, nx + nw - x)
                runs.pop(idx + 1)
            else:
                break
            merged = True
            break

    # 2. 粘连处理：单字符宽度用 总跨距/期望字符数 估计。
    #    用墨迹宽度会低估（run 之间的间隙也算字符占位），
    #    如 'bb2x' 整体粘连时墨迹宽 31/总跨距 37，unit 应≈9.25。
    x_min = min(x for x, _ in runs)
    x_max = max(x + w for x, w in runs)
    unit = float(x_max - x_min) / expected
    regions = []
    for i, (rx, rw) in enumerate(runs):
        start = rx
        end = rx + rw
        # 把与相邻 run 之间的间隙各分一半，纳入本段的占位范围
        if i > 0:
            start = (runs[i - 1][0] + runs[i - 1][1] + rx) // 2
        if i + 1 < len(runs):
            end = (end + runs[i + 1][0]) // 2
        n = max(1, int(round((end - start) / unit))) if unit > 0 else 1
        n = min(n, expected)
        regions.extend(_split_range(rx, rw, proj[rx:rx + rw], n))

    # 3. 噪点过滤：宽度远小于中位数的段视为噪声
    if len(regions) > 1:
        med = float(np.median([w for _, w in regions]))
        regions = [r for r in regions if r[1] >= max(2, med * 0.25)]

    # 4. 数量校正：不足 expected 个 -> 继续切最宽段；超出 -> 丢弃最窄段
    while len(regions) < expected:
        idx = max(range(len(regions)), key=lambda i: regions[i][1])
        rx, rw = regions[idx]
        if rw < 4:  # 太窄无法再切，放弃校正
            break
        new = _split_range(rx, rw, proj[rx:rx + rw], 2)
        regions[idx:idx + 1] = new
        regions.sort()
    while len(regions) > expected:
        idx = min(range(len(regions)), key=lambda i: regions[i][1])
        regions.pop(idx)
    return regions, (core, x0, y0)


def segment_chars(binary, expected=EXPECTED_CHARS, size=CHAR_SIZE):
    """完整切割流程：区域检测 -> 纵向裁剪 -> 归一化。

    返回 [28x28 二值 ndarray, ...]（字符为白），并返回区域框供调试。
    """
    regions, ctx = find_char_regions(binary, expected)
    if not regions or ctx is None:
        return [], []
    core, x0, y0 = ctx
    chars, boxes = [], []
    for rx, rw in regions:
        col = core[:, rx:rx + rw]
        ys, _ = np.where(col > 0)
        if len(ys) == 0:
            continue
        gy, gh = int(ys.min()), int(ys.max() - ys.min() + 1)
        char_img = col[gy:gy + gh, :]
        chars.append(normalize_char(char_img, size))
        boxes.append((x0 + rx, y0 + gy, rw, gh))  # 原图坐标，调试用
    return chars, boxes


def normalize_char(char_img, size=CHAR_SIZE):
    """单字符归一化：等比缩放到 size 内并居中，保证模板/CNN 输入一致。"""
    th, tw = size
    h, w = char_img.shape[:2]
    scale = min((tw - 4) / w, (th - 4) / h)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    resized = cv2.resize(char_img, (nw, nh), interpolation=cv2.INTER_AREA)
    _, resized = cv2.threshold(resized, 127, 255, cv2.THRESH_BINARY)
    canvas = np.zeros((th, tw), dtype=np.uint8)
    dy, dx = (th - nh) // 2, (tw - nw) // 2
    canvas[dy:dy + nh, dx:dx + nw] = resized
    return canvas
