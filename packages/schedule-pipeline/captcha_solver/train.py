# -*- coding: utf-8 -*-
"""CNN 训练模块：合成训练数据自动生成 + PyTorch 单字符分类模型训练。

训练方法：
    1. （可选）把真实样本按字符放入 samples/real/<标签>/xxx.png，
       可用 main.py collect 下载验证码并自动切图，人工挪到对应标签目录；
    2. python3 train.py               # 自动生成合成数据并训练
       python3 train.py --epochs 15   # 指定轮数
    3. 产物：models/cnn.pth（权重）+ models/meta.json（字符集），
       recognize.py 会自动加载作为兜底识别器。
"""
import argparse
import json
import os
import random

import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(BASE_DIR, "samples")
MODEL_DIR = os.path.join(BASE_DIR, "models")
CNN_MODEL = os.path.join(MODEL_DIR, "cnn.pth")
META_FILE = os.path.join(MODEL_DIR, "meta.json")

# 字符集：50 张真实验证码人工核对后确认仅含这 10 类字符
# （若日后观察到新字符，加入此串并重训即可）
CHARSET = "123bcmnvxz"
IMG_SIZE = 28
FONT_DIRS = ["/usr/share/fonts", "C:/Windows/Fonts", os.path.join(SAMPLE_DIR, "fonts")]


def _find_fonts():
    """扫描系统字体目录，收集可用的 ttf/otf 用于合成数据。

    逐个尝试加载，过滤掉无法解析的字体文件（Windows 字体目录中常见）。
    """
    from PIL import ImageFont

    fonts = []
    for d in FONT_DIRS:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if not f.lower().endswith((".ttf", ".otf")):
                    continue
                path = os.path.join(root, f)
                try:
                    ImageFont.truetype(path, 24)
                    fonts.append(path)
                except Exception:
                    continue  # 非法/占位字体文件，跳过
    return fonts


_FONT_CACHE = {}


def render_char(ch, fonts, size=IMG_SIZE):
    """用随机字体渲染单个字符，输出 (size, size) 的 0/1 float 数组。"""
    from PIL import Image, ImageDraw, ImageFont

    if fonts:
        path = random.choice(fonts)
        px = random.randint(56, 72)
        key = (path, px)
        font = _FONT_CACHE.get(key)
        if font is None:
            try:
                font = ImageFont.truetype(path, px)
            except Exception:
                font = ImageFont.load_default()
            if len(_FONT_CACHE) < 1500:  # 防止缓存无限增长
                _FONT_CACHE[key] = font
    else:
        font = ImageFont.load_default()

    img = Image.new("L", (90, 90), 255)
    draw = ImageDraw.Draw(img)
    draw.text((20, 12), ch, font=font, fill=0)
    # 注意：getbbox() 取非零区域，白底黑字必须先反色再求包围盒
    arr0 = np.array(img)
    ys, xs = np.where(arr0 < 128)
    if len(xs) == 0:
        return None
    img = img.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    # 轻微旋转（题目说明无明显旋转，只做小幅扰动增强）
    if random.random() < 0.6:
        img = img.rotate(random.uniform(-10, 10), expand=True, fillcolor=255)

    arr = np.array(img)
    binary = ((arr < 128).astype(np.uint8)) * 255

    # 等比缩放并居中（与识别阶段 normalize_char 逻辑一致）
    h, w = binary.shape
    scale = min((size - 4) / w, (size - 4) / h)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    resized = cv2.resize(binary, (nw, nh), interpolation=cv2.INTER_AREA)
    _, resized = cv2.threshold(resized, 127, 255, cv2.THRESH_BINARY)
    canvas = np.zeros((size, size), dtype=np.uint8)
    dy, dx = (size - nh) // 2, (size - nw) // 2
    canvas[dy:dy + nh, dx:dx + nw] = resized

    # 随机轻微腐蚀/膨胀，模拟笔画粗细变化
    r = random.random()
    if r < 0.3:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        canvas = cv2.erode(canvas, k) if r < 0.15 else cv2.dilate(canvas, k)

    return canvas.astype(np.float32) / 255.0


def _augment_real(arr):
    """真实样本在线增强：随机平移 ±2px、腐蚀/膨胀，模拟切割偏差与笔画粗细变化。"""
    if random.random() < 0.7:
        dy, dx = random.randint(-2, 2), random.randint(-2, 2)
        arr = np.roll(arr, (dy, dx), axis=(0, 1))
    r = random.random()
    if r < 0.4:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        img = (arr * 255).astype(np.uint8)
        img = cv2.erode(img, k) if r < 0.2 else cv2.dilate(img, k)
        arr = img.astype(np.float32) / 255.0
    return arr


def _pick_fonts(max_fonts=40):
    """扫描并随机抽样一批字体，控制缓存规模。

    优先无衬线字体（验证码渲染风格接近 Verdana/DejaVu Sans），
    不足时回退到全部可用字体。
    """
    preferred_kw = ("arial", "verdana", "tahoma", "segoe", "calibri",
                    "trebuchet", "dejavu", "liberation", "comic", "opensans")
    fonts = _find_fonts()
    preferred = [f for f in fonts
                 if any(k in os.path.basename(f).lower() for k in preferred_kw)]
    pool = preferred if len(preferred) >= 8 else fonts
    if len(pool) > max_fonts:
        pool = random.sample(pool, max_fonts)
    return pool


def generate_synthetic_samples(n, out_dir=None, fonts=None):
    """把合成样本保存为 samples/synthetic/<标签>/xxx.png（便于人工检查）。"""
    from PIL import Image

    out_dir = out_dir or os.path.join(SAMPLE_DIR, "synthetic")
    fonts = fonts if fonts is not None else _pick_fonts()
    os.makedirs(out_dir, exist_ok=True)
    count = 0
    for i in range(n):
        ch = random.choice(CHARSET)
        arr = render_char(ch, fonts)
        if arr is None:
            continue
        d = os.path.join(out_dir, ch)
        os.makedirs(d, exist_ok=True)
        img = Image.fromarray((arr * 255).astype(np.uint8))
        img.save(os.path.join(d, f"s_{i:06d}.png"))
        count += 1
    return count


class CharDataset:
    """数据集：合成数据(在线生成) + 真实样本(samples/real/<标签>/)。

    real_repeat: 真实样本重复倍数（配合在线数据增强，小样本时提高权重）。
    """

    def __init__(self, n_synth, fonts=None, real_repeat=1):
        self.fonts = fonts if fonts is not None else _find_fonts()
        self.n_synth = n_synth
        self.real_repeat = max(1, real_repeat)
        self.real = []  # [(path, label_idx), ...]
        real_dir = os.path.join(SAMPLE_DIR, "real")
        if os.path.isdir(real_dir):
            for label in os.listdir(real_dir):
                if label not in CHARSET:
                    continue
                d = os.path.join(real_dir, label)
                for f in os.listdir(d):
                    if f.lower().endswith((".png", ".bmp", ".jpg")):
                        self.real.append((os.path.join(d, f), CHARSET.index(label)))

    def __len__(self):
        return self.n_synth + len(self.real) * self.real_repeat

    def __getitem__(self, idx):
        import torch
        if idx < self.n_synth:
            label = random.randrange(len(CHARSET))
            while True:
                arr = render_char(CHARSET[label], self.fonts)
                if arr is not None:
                    break
        else:
            path, label = self.real[(idx - self.n_synth) % len(self.real)]
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            _, img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
            if np.count_nonzero(img) > img.size * 0.5:
                img = cv2.bitwise_not(img)
            from segment import normalize_char
            arr = normalize_char(img).astype(np.float32) / 255.0
            arr = _augment_real(arr)  # 在线增强：平移/腐蚀/膨胀
        return torch.from_numpy(arr).unsqueeze(0), label


try:
    import torch.nn as nn

    class CharCNN(nn.Module):
        """小型 CNN 单字符分类器：输入 1x28x28，输出字符类别。"""

        def __init__(self, num_classes=len(CHARSET)):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
                nn.MaxPool2d(2),                                    # 28 -> 14
                nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
                nn.MaxPool2d(2),                                    # 14 -> 7
                nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
                nn.MaxPool2d(2),                                    # 7 -> 3
            )
            self.classifier = nn.Sequential(
                nn.Flatten(),
                nn.Linear(128 * 3 * 3, 128), nn.ReLU(), nn.Dropout(0.3),
                nn.Linear(128, num_classes),
            )

        def forward(self, x):
            return self.classifier(self.features(x))
except ImportError:  # 未安装 torch 时保持模块可导入
    pass


def train(epochs=10, batch_size=128, n_synth=20000, lr=1e-3, real_repeat=1):
    """训练流程：合成+真实数据 -> 9:1 划分 -> Adam 训练 -> 保存权重。"""
    import torch
    from torch.utils.data import DataLoader, random_split

    os.makedirs(MODEL_DIR, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    fonts = _pick_fonts()
    if not fonts:
        print("警告: 未找到系统字体，合成数据将使用 PIL 默认字体，效果会打折扣。")
        print("      建议: sudo apt install fonts-dejavu-core")
    ds = CharDataset(n_synth, fonts, real_repeat=real_repeat)
    print(f"数据集大小: {len(ds)} (合成 {n_synth} + 真实 {len(ds.real)}x{real_repeat})")

    n_val = max(1, int(len(ds) * 0.1))
    train_ds, val_ds = random_split(ds, [len(ds) - n_val, n_val])
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=batch_size, num_workers=2)

    model = CharCNN(num_classes=len(CHARSET)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(1, epochs + 1):
        model.train()
        total, correct, loss_sum = 0, 0, 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            loss_sum += loss.item() * x.size(0)
            correct += int((logits.argmax(1) == y).sum())
            total += x.size(0)

        # 验证集准确率
        model.eval()
        v_total, v_correct = 0, 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                v_correct += int((model(x).argmax(1) == y).sum())
                v_total += x.size(0)
        print(f"epoch {epoch:2d}/{epochs}  "
              f"loss={loss_sum / total:.4f}  "
              f"train_acc={correct / total:.4f}  "
              f"val_acc={v_correct / v_total:.4f}")

    torch.save(model.state_dict(), CNN_MODEL)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump({"charset": CHARSET, "img_size": IMG_SIZE}, f)
    print(f"模型已保存: {CNN_MODEL}")
    print(f"元信息已保存: {META_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="验证码 CNN 训练")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch", type=int, default=128)
    parser.add_argument("--synth", type=int, default=20000, help="合成样本数量")
    parser.add_argument("--real-repeat", type=int, default=1, help="真实样本重复倍数")
    parser.add_argument("--real-only", action="store_true", help="只用真实样本训练")
    parser.add_argument("--gen", type=int, default=0, help="只生成 n 张合成样本到磁盘，不训练")
    args = parser.parse_args()

    if args.gen > 0:
        n = generate_synthetic_samples(args.gen)
        print(f"已生成 {n} 张合成样本到 {os.path.join(SAMPLE_DIR, 'synthetic')}")
    else:
        train(epochs=args.epochs, batch_size=args.batch,
              n_synth=0 if args.real_only else args.synth,
              real_repeat=args.real_repeat)
