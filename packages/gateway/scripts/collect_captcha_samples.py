# -*- coding: utf-8 -*-
"""验证码评测集采集器 —— 用「登录接口」当作免费的标注器。

原理
----
每提交一次验证码，强智系统要么放行、要么报「验证码错误!」：
  - 放行    => top-1 预测即为**已验证真值**，得到一张 (整图, 标签) 样本
  - 报错    => top-1 一定错了，但**具体错在哪无从得知**（不产出标签）

已实测确认（2026-09-28，线上环境）：
  - 强智的验证码**一次性**：同一张图错码提交后再提交原码，响应既不是
    「验证码错误」也不是账号错误，而是「请输入完整的登陆信息」，
    即已作废且无法复用。
  - 因此**无法**对同一张图做 top-k 候选搜索来提高标签产出率。
  - 标签产出率 == 当前 top-1 准确率。

产出
----
  <out>/images/<sha1>.png     原始验证码整图（未经任何预处理）
  <out>/samples.jsonl         每行一条记录，含 标签/是否通过/置信度/模型

安全与礼貌
----------
  - 刻意限速（默认每样本间隔 2.5s，每样本 3 个请求）
  - 有 --max 硬上限；--duration 到点自动停
  - 可断点续采：已存在的图片 sha1 不重复采集
  - 只读配置里的凭据，不打印、不落盘
  - 遇到账号类错误立即停止（可能触发风控）
  - 建议在业务低峰运行（脚本会打印当前是否空闲由人工确认）

用法
----
  python collect_captcha_samples.py --out /opt/snhgn/data/captcha_eval --max 20
  python collect_captcha_samples.py --out ... --max 600 --gap 3.0
  # 后台跑
  nohup python collect_captcha_samples.py --out ... --max 600 > /tmp/collect.log 2>&1 &
"""
import argparse
import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.schedule import captcha, recognize as R  # noqa: E402

NET_RETRY = 3


def net(fn, *a, **kw):
    """带退避的网络调用。实测 强智 线路会偶发 ReadTimeout。"""
    last = None
    for i in range(NET_RETRY):
        try:
            return fn(*a, **kw)
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"    [网络抖动] {type(e).__name__}，{2.0 * (i + 1):.0f}s 后重试"
                  f" ({i + 1}/{NET_RETRY})", flush=True)
            time.sleep(2.0 * (i + 1))
    raise last


def get_scode(session):
    r = net(session.post,
            captcha.BASE_URL + "/Logon.do?method=logon&flag=sess", timeout=20)
    if "#" not in r.text:
        return None
    s, x = r.text.strip().split("#", 1)
    return s, x


def submit(session, code, account, password):
    """提交一次登录。返回 'ok' / 'captcha_error' / 'account_error' / 'unknown'。

    注意：验证码一次性，所以**这里绝不能对同一张图重试**。
    """
    sc = get_scode(session)
    if sc is None:
        return "no_scode"
    time.sleep(0.3)
    enc = captcha.encode_login(account, password, sc[0], sc[1])
    r = net(session.post, captcha.BASE_URL + "/Logon.do?method=logon",
            data={"encoded": enc, "RANDOMCODE": code, "useDogCode": ""},
            timeout=20, allow_redirects=True)
    r.encoding = "utf-8"
    t = r.text or ""
    if any(k in t for k in ("退出", "欢迎你", "frameset", "欢迎登录")):
        return "ok"
    if captcha._is_captcha_error(t):
        return "captcha_error"
    if captcha._is_account_error(t):
        return "account_error"
    return "unknown"


def already_collected(out_dir):
    """断点续采：读回已有记录的 sha1。"""
    p = os.path.join(out_dir, "samples.jsonl")
    seen = set()
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    seen.add(json.loads(line)["sha1"])
                except Exception:  # noqa: BLE001
                    continue
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True,
                    help="宿主机上的输出目录（需真实存在）。"
                         "容器内以 <宿主机路径> 同名路径读写；若该目录未挂载进"
                         "容器，宿主机将看不到产物（目录属主会变成 root）。")
    ap.add_argument("--max", type=int, default=20, help="本次最多采集多少张")
    ap.add_argument("--total", type=int, default=0,
                    help="累计目标总数（达到就停，用于多次运行累积）")
    ap.add_argument("--gap", type=float, default=2.5, help="每个样本之间的间隔秒数")
    ap.add_argument("--beta", action="store_true",
                    help="用 ddddocr 的 beta 模型（52MB）而非默认老版（13MB）")
    ap.add_argument("--max-net-fail", type=int, default=8,
                    help="连续网络失败多少次就判定链路不可用并停止")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    out = args.out
    img_dir = os.path.join(out, "images")
    os.makedirs(img_dir, exist_ok=True)
    jsonl = os.path.join(out, "samples.jsonl")

    account, password = settings.BJFU_USERNAME, settings.BJFU_PASSWORD
    if not account or not password:
        print("未配置 BJFU_USERNAME / BJFU_PASSWORD，无法采集")
        return 1

    R._get_ddddocr()   # 触发预热 + 索引钉住
    model = R.ocr_model_name()
    if args.beta and model != "beta":
        print("!! --beta 需要环境变量 CAPTCHA_OCR_MODEL=beta（模型在进程启动时选定）。"
              "请用 CAPTCHA_OCR_MODEL=beta 重新运行。")
        return 2
    seen = already_collected(out)
    if not args.quiet:
        print("=" * 70)
        print(f"采集目标目录: {out}")
        print(f"模型: {model}   本次上限: {args.max}   间隔: {args.gap}s")
        print(f"已有记录: {len(seen)} 条（断点续采）")
        print("=" * 70, flush=True)

    session = net(captcha.get_session)
    added = 0
    ok_n = rej_n = unknown_n = 0
    net_fail = 0
    started = time.time()

    for i in range(args.max):
        if args.total and len(seen) + added >= args.total:
            print(f"已达到累计目标 {args.total}，停止")
            break
        if i:
            time.sleep(args.gap)

        # ---- 取图（可安全重试：重试只是换一张图）----
        try:
            img = net(captcha.get_captcha, session)
        except Exception as e:  # noqa: BLE001
            net_fail += 1
            print(f"  取图失败({net_fail}): {type(e).__name__}，退避 10s 后继续", flush=True)
            time.sleep(10.0)
            if net_fail >= args.max_net_fail:
                print("  !!! 网络连续失败次数过多，判定链路不可用，停止")
                break
            continue

        sha1 = hashlib.sha1(img).hexdigest()
        if sha1 in seen:
            continue

        code = R.recognize(img)
        st = R.ocr_stats()

        # 识别不出可信验证码时，这张图无法产出标签，但值得存下来做难例分析
        if not code:
            res = "no_code"
        else:
            # ---- 提交（**绝不能对同一张图重试**：验证码一次性，
            #      且网络失败时服务端可能已经处理过，重提会产生歧义）----
            try:
                res = submit(session, code, account, password)
            except Exception as e:  # noqa: BLE001
                res = "network_error"
                net_fail += 1
                print(f"  提交网络失败({net_fail}): {type(e).__name__}"
                      f"（该图作废，不重试）", flush=True)
                time.sleep(10.0)
                if net_fail >= args.max_net_fail:
                    print("  !!! 网络连续失败次数过多，判定链路不可用，停止")
                    break

        # ---- 写盘落账 ----
        with open(os.path.join(img_dir, f"{sha1}.png"), "wb") as f:
            f.write(img)
        rec = {
            "sha1": sha1,
            "label": code or None,
            "result": res,
            "verified": res == "ok",
            "conf_mean": st["last_mean"],
            "conf_weakest": st["last_weakest"],
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": model,
        }
        with open(jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        seen.add(sha1)
        added += 1

        if res == "ok":
            ok_n += 1
            tag = f"✓ {code}  mean={st['last_mean']} weakest={st['last_weakest']}"
        elif res == "captcha_error":
            rej_n += 1
            tag = f"✗ {code}  识别错  mean={st['last_mean']} weakest={st['last_weakest']}"
        elif res == "account_error":
            print("  !!! 出现账号类错误，立即停止（可能触发风控）", flush=True)
            break
        else:
            unknown_n += 1
            tag = f"? {code}  {res}"

        if not args.quiet:
            print(f"  #{added:<3} {tag}", flush=True)

    el = time.time() - started
    print()
    print("=" * 70)
    print(f"本次采集 {added} 张，用时 {el:.0f}s   网络失败 {net_fail} 次")
    print(f"  通过(已验证标签) : {ok_n}")
    print(f"  识别错(硬负样本) : {rej_n}")
    print(f"  未知/无法识别   : {unknown_n}")
    if ok_n + rej_n:
        print(f"  top-1 准确率     : {ok_n / (ok_n + rej_n) * 100:.1f}%"
              f"  (n={ok_n + rej_n})")
    print(f"  累计记录         : {len(seen)}")
    print(f"  输出             : {jsonl}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
