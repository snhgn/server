# -*- coding: utf-8 -*-
"""字符识别模块，三级识别链（按优先级）：

1. CNN       models/cnn.pth（真实样本训练，准确率最高，首选）
2. 模板匹配  models/templates/<字符标签>/*.png（字符为白、黑底二值图）
3. OCR       优先 ddddocr，其次 pytesseract（单字符 psm=10）

切割结果数量异常时，降级为整图 OCR。
（迁移自 schedule-pipeline/captcha_solver/recognize.py，仅调整相对导入）
"""
import json
import os

import cv2
import numpy as np

from .preprocess import preprocess
from .segment import segment_chars, normalize_char, EXPECTED_CHARS, CHAR_SIZE

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "models", "templates")
CNN_MODEL = os.path.join(BASE_DIR, "models", "cnn.pth")
META_FILE = os.path.join(BASE_DIR, "models", "meta.json")

TEMPLATE_THRESHOLD = 0.55  # 模板匹配置信度阈值(IoU)，低于此值走 OCR/CNN

_matcher = None
_cnn = None  # (model, charset, device) 懒加载缓存
_ddddocr = None  # ddddocr 实例懒加载缓存（单次初始化 ~1s+，必须复用）


def _get_ddddocr():
    """获取 ddddocr 单例：模型加载仅一次，避免每次识别重建实例"""
    global _ddddocr
    if _ddddocr is None:
        import ddddocr

        _ddddocr = ddddocr.DdddOcr(show_ad=False)
    return _ddddocr


class TemplateMatcher:
    """基于 XOR 距离的二值模板匹配。"""

    def __init__(self, template_dir=TEMPLATE_DIR, size=CHAR_SIZE):
        self.size = size
        self.templates = {}  # {label: [0/1 ndarray, ...]}
        if not os.path.isdir(template_dir):
            return
        for label in sorted(os.listdir(template_dir)):
            d = os.path.join(template_dir, label)
            if not os.path.isdir(d):
                continue
            mats = []
            for f in os.listdir(d):
                if not f.lower().endswith((".png", ".bmp", ".jpg")):
                    continue
                img = cv2.imread(os.path.join(d, f), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                _, img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
                if np.count_nonzero(img) > img.size * 0.5:  # 保证字符为白
                    img = cv2.bitwise_not(img)
                mats.append((normalize_char(img, size) > 0).astype(np.uint8))
            if mats:
                self.templates[label] = mats

    def match(self, char_img, max_shift=2):
        """返回 (最优标签, 相似度得分)。得分 = 前景 IoU（允许 ±max_shift 平移对齐，
        容忍切割边界 1~2px 偏差）。"""
        if not self.templates:
            return None, 0.0
        c = char_img > 0
        c_sum = c.sum()
        best_label, best_score = None, 0.0
        for label, mats in self.templates.items():
            for m in mats:
                t = m > 0
                t_sum = t.sum()
                for dy in range(-max_shift, max_shift + 1):
                    for dx in range(-max_shift, max_shift + 1):
                        tm = np.roll(t, (dy, dx), axis=(0, 1))
                        inter = np.count_nonzero(c & tm)
                        union = c_sum + t_sum - inter
                        score = inter / union if union else 0.0
                        if score > best_score:
                            best_label, best_score = label, score
        return best_label, best_score


def _get_matcher():
    global _matcher
    if _matcher is None:
        _matcher = TemplateMatcher()
    return _matcher if _matcher.templates else None


def _ocr_char(char_img):
    """单字符 OCR 兜底，未安装 OCR 库时返回 None。"""
    ok, png = cv2.imencode(".png", char_img)
    if not ok:
        return None
    data = png.tobytes()
    try:
        return _get_ddddocr().classification(data)
    except ImportError:
        pass
    except Exception:
        pass
    try:
        import pytesseract
        text = pytesseract.image_to_string(
            char_img,
            config="--psm 10 -c tessedit_char_whitelist=0123456789"
                   "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        ).strip()
        return text[0] if text else None
    except ImportError:
        return None
    except Exception:
        return None


def _full_image_ocr(image):
    """切割失败时的整图 OCR 降级。"""
    if isinstance(image, (bytes, bytearray)):
        data = bytes(image)
    else:
        ok, png = cv2.imencode(".png", image)
        data = png.tobytes() if ok else None
    if data is None:
        return ""
    try:
        return _get_ddddocr().classification(data)
    except ImportError:
        return ""
    except Exception:
        return ""


def _load_cnn():
    """懒加载 CNN 模型，未安装 torch 或模型不存在时返回 None。"""
    global _cnn
    if _cnn is not None:
        return _cnn
    if not os.path.isfile(CNN_MODEL) or not os.path.isfile(META_FILE):
        return None
    try:
        import torch
        from train import CharCNN
    except ImportError:
        return None
    with open(META_FILE, "r", encoding="utf-8") as f:
        meta = json.load(f)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = CharCNN(num_classes=len(meta["charset"])).to(device)
    try:
        # weights_only=True 禁止反序列化任意 Python 对象，防止恶意模型文件
        state = torch.load(CNN_MODEL, map_location=device, weights_only=True)
    except TypeError:  # 旧版 torch 不支持 weights_only 参数
        state = torch.load(CNN_MODEL, map_location=device)
    model.load_state_dict(state)
    model.eval()
    _cnn = (model, meta["charset"], device)
    return _cnn


def _cnn_char(char_img):
    """CNN 单字符预测，返回 (标签, 概率)。"""
    ctx = _load_cnn()
    if ctx is None:
        return None, 0.0
    import torch
    model, charset, device = ctx
    # 与训练一致：0/1 二值浮点（训练时 canvas/255 后为 0 或 1）
    x = torch.from_numpy((char_img > 0).astype(np.float32))
    x = x.view(1, 1, *char_img.shape).to(device)
    with torch.no_grad():
        prob = torch.softmax(model(x), dim=1)[0]
    idx = int(prob.argmax())
    return charset[idx], float(prob[idx])


def recognize(image, return_detail=False):
    """识别验证码图片，返回 4 位字符串。

    image: bytes / 文件路径 / ndarray
    return_detail=True 时额外返回每个字符的 (识别结果, 来源, 置信度)。
    """
    # 首选整图 ddddocr：Dr.COM 4 位字母数字验证码实测整图识别准确率远高于
    # 切分+模板匹配（模板库仅含 1,2,3,b,c,m,n,v,x,z，对含其他字符的验证码必错）
    code = _full_image_ocr(image)
    if code and len(code) >= 4 and all(c.isalnum() for c in code[:4]):
        code = code[:4]
        return (code, [(c, "full_ocr", 0.0) for c in code]) if return_detail else code

    # 回退：切割 + 单字符识别链（CNN → 模板 → OCR）
    binary = preprocess(image)
    chars, _ = segment_chars(binary)

    code_chars, details = [], []
    if len(chars) == EXPECTED_CHARS:
        matcher = _get_matcher()
        for ch_img in chars:
            # 1) CNN 首选（真实样本训练，实测准确率远高于模板匹配）
            cnn_label, prob = _cnn_char(ch_img)
            if cnn_label:
                code_chars.append(cnn_label)
                details.append((cnn_label, "cnn", round(prob, 3)))
                continue
            # 2) 模板匹配兑底
            label, score = matcher.match(ch_img) if matcher else (None, 0.0)
            if score >= TEMPLATE_THRESHOLD:
                code_chars.append(label)
                details.append((label, "template", round(score, 3)))
                continue
            # 3) OCR 兑底
            ocr_label = _ocr_char(ch_img)
            if ocr_label:
                code_chars.append(ocr_label[0])
                details.append((ocr_label[0], "ocr", round(score, 3)))
            else:
                code_chars.append(label or "?")
                details.append((label or "?", "guess", round(score, 3)))
        code = "".join(code_chars)
    else:
        # 切割异常：整图 OCR 降级
        code = _full_image_ocr(image)
        details.append((code, "full_ocr", 0.0))

    return (code, details) if return_detail else code
