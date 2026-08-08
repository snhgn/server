# -*- coding: utf-8 -*-
"""图像预处理模块：灰度化、二值化、去噪、形态学处理。

输出约定：二值图中字符为 255(白)，背景为 0(黑)。
"""
import os

import cv2
import numpy as np


def load_image(src):
    """支持 文件路径 / bytes / ndarray 三种输入，返回 BGR ndarray。"""
    if isinstance(src, np.ndarray):
        img = src
    elif isinstance(src, (bytes, bytearray)):
        img = cv2.imdecode(np.frombuffer(bytes(src), np.uint8), cv2.IMREAD_COLOR)
    elif isinstance(src, str) and os.path.isfile(src):
        img = cv2.imread(src, cv2.IMREAD_COLOR)
    else:
        raise ValueError(f"不支持的输入类型: {type(src)}")
    if img is None:
        raise ValueError("图像解码失败，请检查输入数据")
    return img


def to_gray(img):
    """灰度化。"""
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def binarize(gray, method="otsu"):
    """二值化并反色，使字符为白色前景。

    method='otsu'      全局大津法，适合背景干净的验证码（默认）
    method='adaptive'  自适应阈值，应对光照不均
    """
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    if method == "otsu":
        _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        binary = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 8
        )
    # 字符一定是少数像素：若白色超过一半说明极性反了
    if np.count_nonzero(binary) > binary.size * 0.5:
        binary = cv2.bitwise_not(binary)
    return binary


def clear_border(binary, width=1):
    """清除图片边框线，防止边框干扰投影分析。"""
    h, w = binary.shape[:2]
    binary[:width, :] = 0
    binary[h - width:, :] = 0
    binary[:, :width] = 0
    binary[:, w - width:] = 0
    return binary


def denoise(binary, min_area=2):
    """中值滤波去椒盐噪声 + 剔除面积过小的连通域。"""
    binary = cv2.medianBlur(binary, 3)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    out = np.zeros_like(binary)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            out[labels == i] = 255
    return out


def morphology(binary):
    """形态学处理：闭运算填补字符笔画断点，开运算去除细小毛刺。"""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
    return opened


def preprocess(src):
    """完整预处理流水线，返回字符为白色的二值图。"""
    img = load_image(src)
    gray = to_gray(img)
    binary = binarize(gray)
    binary = clear_border(binary)
    binary = morphology(binary)
    binary = denoise(binary)
    return binary
