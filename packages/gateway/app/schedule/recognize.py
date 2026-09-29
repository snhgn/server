# -*- coding: utf-8 -*-
"""验证码识别模块。

生产路径只有一条：整图 ddddocr（Dr.COM 4 位字母数字验证码实测整图识别
准确率最高）。整体流程：

1. 整图 ddddocr + 逐字符置信度，位数/字符集合法即采信；
2. 整图结果非法（位数不对、含非 ASCII 字母数字）时降级到切分 + 逐字符 ddddocr；
3. 切分链也给不出合法结果时用整图结果抢救；仍失败返回空串，由调用方换码。

关于历史上被移除的两条分支（保留此说明以免再被"复活"）：
- **CNN**（models/cnn.pth）：训练脚本 train.py 已随旧目录一并删除，
  `from train import CharCNN` 必然 ImportError，且是绝对导入（包内应为
  .train），torch 也不在 requirements.txt —— 恒为死代码。该权重还是用
  PIL 随机字体合成数据训的，从未见过真实验证码。
- **模板匹配**（models/templates/）：字符集只有 "123bcmnvxz" 10 个符号，
  真实验证码含其他字符时必然误判。

这两条即使修好导入也只会更差：它们把整图问题拆成单字符问题，而逐字符
识别本就劣于整图。真正该做的是训一个整图 CRNN + CTC（见 docs）并配上
标注样本集做评测，而不是修补这两条兜底。
"""
import logging
import os
import threading

import cv2
import numpy as np

from .preprocess import preprocess
from .segment import segment_chars, EXPECTED_CHARS

logger = logging.getLogger("gateway.schedule.recognize")

_ddddocr = None  # ddddocr 实例懒加载缓存（单次初始化 ~1s+，必须复用）

# 只保护「一次性把字符集索引钉成只读」这个动作，热路径不加锁：
# 钉完之后 ddddocr 实例在 classification() 期间不再有任何共享可变状态
# （见 _pin_charset_index 的论证），onnxruntime 的 session.run() 本身线程安全。
_pin_lock = threading.Lock()
_pinned = False  # 字符集索引是否已钉住（False 表示退回原实现）

# 识别质量观测计数（进程内，仅统计量）
_stats_lock = threading.Lock()
_stats = {
    "samples": 0,
    "no_confidence": 0,
    "alignment_mismatch": 0,
    "last_mean": None,
    "last_weakest": None,
    "last_len": 0,
    "pin_applied": False,
}


def _find_charset_manager(ocr):
    """在 ddddocr 的各层封装里找到 CharsetManager 实例。

    1.6.1 的 DdddOcr 是门面类，charset_manager 挂在 ocr_engine 上；早期版本
    直接挂在 DdddOcr 上。这里逐个候选路径找，找不到就返回 None（放弃优化）。
    """
    for path in (("charset_manager",),
                 ("ocr_engine", "charset_manager"),
                 ("engine", "charset_manager"),
                 ("_ocr_engine", "charset_manager")):
        node = ocr
        for attr in path:
            node = getattr(node, attr, None)
            if node is None:
                break
        else:
            if callable(getattr(node, "_update_valid_indices", None)):
                return node
    return None


def _pin_charset_index(ocr) -> bool:
    """把 ddddocr 每次识别都会重跑的字符集索引，预计算成只读常量。

    背景：predict() 在 charset_range 为空时每次都调用
    CharsetManager._update_valid_indices()，而它的实现是 **先 clear() 掉共享的
    valid_charset_range_index，再重新赋值**。clear() 与重新赋值之间存在窗口，
    并发 classification 会在此刻 copy() 到空列表，解码出**位数不足的验证码**
    —— 是个静默的错误识别（本地负向测试可复现）。

    收益要说清楚：
    - 正确性：消掉上面这个竞态（主要价值）；
    - 性能：省下每次约 0.2ms 的重建（实测服务器 8210 字集，_update_valid_indices
      净耗时约 200µs）。**远小于**一次整图 ONNX 推理的几十毫秒，所以别把它当
      性能优化看，它是个正确性修复。

    我们从不传 charset_range、也不换自定义模型（import_onnx_path /
    load_custom_charset 都没用），charset_range 恒为空、charset 恒定，因此
    这个索引每次重算结果必然相同。这里在实例上把该方法替换成「校验 + 必要时
    原样写回」，热路径额外开销降到一次列表比较；写回用切片赋值，在 CPython
    的 GIL 内一次完成，不存在中间态。

    任何一步对不上（内部结构变化、找不到 charset_manager 等）都返回 False，
    静默退回原实现，只损失正确性保障不影响功能。
    """
    cm = _find_charset_manager(ocr)
    if cm is None:
        return False
    # 只在 charset_range 为空（全量）时钉：此时索引恒为 range(len(charset))，
    # 是真正不变的常量。范围受限时索引随 charset_range 变化，快照会过期。
    if list(getattr(cm, "charset_range", None) or []):
        return False
    try:
        cm._update_valid_indices()
        snapshot = list(getattr(cm, "valid_charset_range_index", None) or [])
        charset = list(getattr(cm, "charset", None) or [])
    except Exception:
        return False
    if not snapshot or snapshot != list(range(len(charset))):
        return False

    def _pinned_rebuild():
        # 正常路径只有一次 O(n) 列表比较（几十微秒）；被别处清空就原样写回
        if cm.valid_charset_range_index != snapshot:
            cm.valid_charset_range_index[:] = snapshot
        return None

    try:
        cm._update_valid_indices = _pinned_rebuild
    except Exception:
        return False
    return cm.valid_charset_range_index == snapshot


def _get_ddddocr():
    """获取 ddddocr 单例：模型加载仅一次，避免每次识别重建实例。

    模型选择由环境变量 CAPTCHA_OCR_MODEL 控制：
      - ``old``/``default``（默认）-> common_old.onnx（13MB），
        这是 DdddOcr(show_ad=False) 的隐式默认（load_ocr_model 的 else 分支）。
      - ``beta`` -> common.onnx（52MB）+ beta 字符集，是 ddddocr 里更新的一版。
    两者准确率孰高需要用采集到的评测集实测（见 scripts/collect_captcha_samples.py），
    不要凭直觉切。
    """
    global _ddddocr, _pinned
    if _ddddocr is None:
        import ddddocr

        choice = os.environ.get("CAPTCHA_OCR_MODEL", "").strip().lower()
        if choice == "beta":
            _ddddocr = ddddocr.DdddOcr(show_ad=False, beta=True)
        elif choice in ("old", "default", ""):
            _ddddocr = ddddocr.DdddOcr(show_ad=False)
        else:
            _ddddocr = ddddocr.DdddOcr(show_ad=False)
            logger.warning("未知的 CAPTCHA_OCR_MODEL=%r，回退到默认老版模型", choice)
    if not _pinned:
        with _pin_lock:
            if not _pinned:
                _pinned = _pin_charset_index(_ddddocr)
                with _stats_lock:
                    _stats["pin_applied"] = _pinned
    return _ddddocr


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
    """整图 OCR。返回 (文本, 逐字符置信度列表)；无置信度时后置为 None。"""
    if isinstance(image, (bytes, bytearray)):
        data = bytes(image)
    else:
        ok, png = cv2.imencode(".png", image)
        data = png.tobytes() if ok else None
    if data is None:
        return "", None
    try:
        ocr = _get_ddddocr()
        try:
            res = ocr.classification(data, probability=True)
        except TypeError:  # 旧版 ddddocr 无 probability 参数
            return ocr.classification(data), None
        return _decode_ocr_result(res)
    except ImportError:
        return "", None
    except Exception:
        return "", None


def _as_prob_steps(probs, n_classes):
    """把 ddddocr 的 probabilities 规整成按时间顺序的 [T][C] 列表。

    实际返回的形状不固定，线上实测是 (T, 1, C) = [23][1][8210]（时间步在前、
    batch 维在中间），而其他版本/模型可能是 (1, T, C)。按「哪一维长度等于
    字符集大小」来定位 C 轴，其余轴按顺序展开，这样两种布局都能拿到正确的时间
    步顺序 —— 之前假设固定的 [1][T][C] 会只取到 batch 维那一行，把 CTC blank
    当成字符，导致置信度永远是 None。
    """
    steps = []

    def walk(node):
        if not isinstance(node, list) or not node:
            return
        if not isinstance(node[0], list) and len(node) == n_classes:
            steps.append(node)          # 这就是一个时间步的 C 维概率
            return
        for child in node:
            walk(child)

    walk(probs)
    return steps


def _decode_ocr_result(res):
    """把 ddddocr probability=True 的返回拆成 (文本, 逐字符置信度)。

    ddddocr 自带的 confidence 字段是「所有时间步（含 CTC blank）argmax 的
    均值」，被 blank 稀释、且无法定位到底哪一位不可靠，所以这里自己按 CTC
    规则取「非 blank 时间步」上的最大概率作为每个字符的置信度。

    任何一步失败都退化为 (文本, None)，让调用方沿用长度/字符集门控，
    不因为拿不到置信度就丢弃一个本来正确的识别结果。
    """
    if isinstance(res, str):
        return res, None
    if not isinstance(res, dict):
        return "", None
    text = res.get("text") or ""
    probs = res.get("probabilities")
    charset = res.get("charset")
    try:
        if not probs or not charset:
            return text, None
        return text, _ctc_confidences(_as_prob_steps(probs, len(charset)), charset)
    except Exception:
        return text, None


def _ctc_confidences(steps, charset):
    """按 CTC 规则输出与 text 逐位对齐的置信度。

    blank 固定是字符集的第 0 项——ddddocr 自己的 _ctc_decode_indices 就是
    按「idx != 0 即为有效字符」解的码，这里必须与它保持一致，否则取到的
    概率和它解出的 text 会对不上位。

    另外跳过最大概率近于 0 的时间步：这种步不含信息量（异常/未归一化的
    输出），按 argmax 硬取会把噪声当成一个低置信度字符塞进结果。
    """
    if not steps or not charset:
        return None
    blank_idx = 0
    confs = []
    prev = -1
    for step in steps:
        idx = int(np.argmax(step))
        peak = float(step[idx])
        if peak < 1e-6:  # 无信息量的时间步，既不当字符也不更新 prev
            continue
        if idx != prev and idx != blank_idx:
            confs.append(peak)
        prev = idx
    return confs or None


def _is_plausible_code(code, expected=EXPECTED_CHARS):
    """OCR 输出是否可直接采信作为教务系统验证码。

    必须恰好 expected 位：多出来的位通常是幻觉字符（静默截断会把
    「前 4 位正确 + 末尾多一个错字符」误判为整体正确），少位则是漏识别。
    字符限定 ASCII 字母数字：str.isalnum() 对 CJK 也返回 True，
    会让「一1b2」这类垃圾输出直接通过。
    """
    if not code or len(code) != expected:
        return False
    return all(c.isascii() and c.isalnum() for c in code)


def _salvage_code(code, expected=EXPECTED_CHARS):
    """从不可信的整图输出里抢救出恰好 expected 位字母数字，全失败返回空串。

    仅移除噪声字符、不做截断：长度不足或超长都说明漏识别/幻觉，此时提交
    登录必定失败，直接返回空串让调用方立刻换码，省下 2 次无谓往返。
    """
    if not code:
        return ""
    kept = [c for c in code if c.isascii() and c.isalnum()]
    return "".join(kept) if len(kept) == expected else ""


def _mean_confidence(confs):
    """逐字符置信度的平均值；无置信度时返回 None。"""
    if not confs:
        return None
    return sum(confs) / len(confs)


def _weakest_confidence(confs):
    """最不可靠那一位的置信度；无置信度时返回 None。"""
    return min(confs) if confs else None


def _observe_confidence(code, confs):
    """记录一次整图识别的置信度，供标定阈值与排查识别质量。

    只记统计量，绝不记验证码原文（它与学号密码同属一次性凭据）。
    """
    if confs is None:
        with _stats_lock:
            _stats["no_confidence"] += 1
        return
    with _stats_lock:
        _stats["samples"] += 1
        _stats["last_mean"] = round(_mean_confidence(confs), 4)
        _stats["last_weakest"] = round(_weakest_confidence(confs), 4)
        _stats["last_len"] = len(code or "")
        if len(confs) != len(code or ""):
            _stats["alignment_mismatch"] += 1


def ocr_model_name():
    """当前生效的 OCR 模型名（old / beta），记录在样本里以便后续 A/B。"""
    choice = os.environ.get("CAPTCHA_OCR_MODEL", "").strip().lower()
    return "beta" if choice == "beta" else "old"


def ocr_stats():
    """识别质量观测数据（不含验证码内容）。

    有了标注样本集后，用 last_mean / last_weakest 的分布就能反推一个
    「低于此值则弃用整图结果」的阈值，而不必靠猜。
    """
    with _stats_lock:
        return dict(_stats)


def recognize(image, return_detail=False):
    """识别验证码图片，返回 4 位字符串。

    image: bytes / 文件路径 / ndarray
    return_detail=True 时额外返回每个字符的 (识别结果, 来源, 置信度)。

    注意：这里刻意**不**用置信度做拒绝门控。切分兜底链只剩逐字符 ddddocr，
    而逐字符识别本就劣于整图 —— 一旦因低置信度否掉整图结果，后面并没有更
    好的候选可用，只会让服务端多驳回一次、白白多花一次验证码。因此置信度
    只做采集与上报，等有了标注样本集把阈值标定之后再决定是否启用门控。
    """
    # 首选整图 ddddocr：Dr.COM 4 位字母数字验证码实测整图识别准确率最高
    raw, confs = _full_image_ocr(image)
    _observe_confidence(raw, confs)
    if _is_plausible_code(raw):
        detail = [(c, "full_ocr",
                   round(confs[i], 3) if confs and i < len(confs) else 0.0)
                  for i, c in enumerate(raw)]
        return (raw, detail) if return_detail else raw

    # 整图结果不可信（位数不对 / 含非 ASCII 字母数字），降级到切分 + 逐字符 OCR
    binary = preprocess(image)
    chars, _ = segment_chars(binary)

    if len(chars) == EXPECTED_CHARS:
        code_chars, details = [], []
        for ch_img in chars:
            label = _ocr_char(ch_img)
            if label:
                code_chars.append(label[0])
                details.append((label[0], "ocr", 0.0))
            else:
                code_chars.append("?")
                details.append(("?", "unresolved", 0.0))
        code = "".join(code_chars)
        if _is_plausible_code(code):
            return (code, details) if return_detail else code
        details = []

    # 切分链也给不出合法结果：用整图输出抢救（整图已推理过，不重复跑）
    code = _salvage_code(raw)
    details = [(code, "salvaged", 0.0)] if code else []
    return (code, details) if return_detail else code

