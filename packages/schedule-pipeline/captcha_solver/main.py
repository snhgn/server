# -*- coding: utf-8 -*-
"""验证码识别项目主入口（CLI）。

用法：
    python3 main.py solve  <图片路径>       识别一张本地验证码图片
    python3 main.py collect <数量>          从教务系统下载验证码并自动切图，用于建模板库
    python3 main.py synthgen <数量>         生成合成训练样本到 samples/synthetic/
    python3 main.py train [--epochs N]      训练 CNN 兜底模型
    python3 main.py login --user xx --pwd xx   完整登录并抓取课表
"""
import argparse
import os
import time

from preprocess import preprocess
from segment import segment_chars

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def cmd_solve(args):
    from recognize import recognize
    code, details = recognize(args.image, return_detail=True)
    print("识别结果:", code)
    for d in details:
        print("  ", d)


def cmd_collect(args):
    """下载验证码 -> 保存原图 -> 自动切图保存到 samples/unlabeled/。

    后续人工把切好的字符图片挪到 samples/real/<标签>/ 或
    models/templates/<标签>/ 即可用于训练/模板匹配。
    """
    import cv2
    import numpy as np
    from captcha import get_session, get_captcha

    raw_dir = os.path.join(BASE_DIR, "samples", "raw")
    cut_dir = os.path.join(BASE_DIR, "samples", "unlabeled")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(cut_dir, exist_ok=True)

    session = get_session()
    for i in range(args.count):
        try:
            img_bytes = get_captcha(session)
        except Exception as e:
            print(f"[{i}] 下载失败: {e}")
            continue
        stamp = time.strftime("%H%M%S") + f"_{i:03d}"
        raw_path = os.path.join(raw_dir, f"{stamp}.png")
        buf = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        cv2.imwrite(raw_path, buf)

        binary = preprocess(buf)
        chars, boxes = segment_chars(binary)
        for j, ch in enumerate(chars):
            cv2.imwrite(os.path.join(cut_dir, f"{stamp}_c{j}.png"), ch)
        print(f"[{i}] 原图 -> {raw_path}，切出 {len(chars)} 个字符(框: {boxes})")
        time.sleep(0.5)
    print(f"\n请人工核对 {cut_dir} 中的切图，将字符图片按标签移动到 samples/real/<标签>/")


def cmd_synthgen(args):
    from train import generate_synthetic_samples
    n = generate_synthetic_samples(args.count)
    print(f"已生成 {n} 张合成样本")


def cmd_train(args):
    from train import train
    train(epochs=args.epochs, batch_size=args.batch, n_synth=args.synth)


def cmd_login(args):
    import captcha as cap
    user = args.user or os.environ.get("JWXT_USER")
    pwd = args.pwd or os.environ.get("JWXT_PWD")
    if not user or not pwd:
        print("缺少凭据：请传 --user/--pwd，或设置环境变量 JWXT_USER / JWXT_PWD")
        print('  PowerShell: setx JWXT_USER "学号"; setx JWXT_PWD "密码"  (用后 setx 删除)')
        return
    ok, session, reason = cap.login(user, pwd)
    if not ok:
        print(f"登录失败：{reason}")
        return
    print("登录成功，正在抓取课表...")
    html = cap.get_timetable(session)
    out = os.path.join(BASE_DIR, "timetable.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"课表已保存: {out} ({len(html)} 字符)")


def main():
    parser = argparse.ArgumentParser(description="教务系统验证码识别工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("solve", help="识别本地验证码图片")
    p.add_argument("image")
    p.set_defaults(func=cmd_solve)

    p = sub.add_parser("collect", help="下载验证码并自动切图")
    p.add_argument("count", type=int)
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("synthgen", help="生成合成训练样本")
    p.add_argument("count", type=int)
    p.set_defaults(func=cmd_synthgen)

    p = sub.add_parser("train", help="训练 CNN 模型")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch", type=int, default=128)
    p.add_argument("--synth", type=int, default=20000)
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("login", help="登录教务系统并抓取课表")
    p.add_argument("--user", help="学号，缺省读环境变量 JWXT_USER")
    p.add_argument("--pwd", help="密码，缺省读环境变量 JWXT_PWD")
    p.set_defaults(func=cmd_login)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
