# -*- coding: utf-8 -*-
"""第四阶段：接入强智教务系统（北京林业大学）。

对外接口：
    captcha = get_captcha()          # 获取验证码图片 bytes
    code = recognize(captcha)        # 识别验证码
    login(account, password)         # 完整登录（含验证码重试）
    get_timetable(session)           # 抓取个人课表 HTML

登录流程（还原 login.htm 中的 JS 逻辑）：
    1. GET 登录页，建立 cookie
    2. GET /verifycode.servlet 获取验证码
    3. POST /Logon.do?method=logon&flag=sess 获取 scode#sxh
    4. 用 encode_login() 把 "账号%%%密码" 与 scode 按 sxh 交织得到 encoded
    5. POST /Logon.do?method=logon 提交 encoded + RANDOMCODE
"""
import random

import requests

from recognize import recognize

BASE_URL = "http://newjwxt.bjfu.edu.cn"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": BASE_URL + "/",
}


def get_session():
    """创建会话并访问登录页，初始化 cookie。"""
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(BASE_URL + "/", timeout=10)
    return s


def get_captcha(session=None):
    """获取验证码图片，返回 bytes。"""
    session = session or get_session()
    r = session.get(
        BASE_URL + "/verifycode.servlet",
        params={"t": random.random()},
        timeout=10,
    )
    r.raise_for_status()
    return r.content


def encode_login(account, password, scode, sxh):
    """还原 login.htm 中 onSubmint() 的 encoded 编码算法。

    code = account + '%%%' + password；前 20 个字符逐个与 scode 片段交织，
    交织位置由 sxh 的每一位数字决定；第 20 位之后原样拼接。
    """
    code = f"{account}%%%{password}"
    encoded = ""
    for i, ch in enumerate(code):
        if i < 20:
            k = int(sxh[i])
            encoded += ch + scode[:k]
            scode = scode[k:]
        else:
            encoded += code[i:]
            break
    return encoded


def _extract_error_msgs(text):
    """提取响应中的错误提示（红字块 + alert 弹窗）。

    不能全页匹配关键词：登录页本身含“验证码:”“密码:”等标签，
    且“该账号不存在或已过期”里的“过期”会误判成验证码错误。
    """
    import re
    msgs = re.findall(r'<font[^>]*color=["\']?red[^>]*>([^<]+)</font>', text)
    msgs += re.findall(r'alert\(\s*["\']([^"\']+)["\']\s*\)', text)
    return [m.strip() for m in msgs if m.strip() and "请输入" not in m]


def _is_captcha_error(text):
    """服务端响应是否提示验证码错误（值得换码重试）。"""
    return any(
        "验证码" in m and any(k in m for k in ("不正确", "错误", "有误", "不对", "失效", "过期"))
        for m in _extract_error_msgs(text)
    )


def _is_account_error(text):
    """服务端响应是否提示账号/密码错误（重试无意义，立即失败）。"""
    return any(
        any(w in m for w in ("密码", "账号", "帐号")) and any(
            k in m for k in ("不正确", "错误", "有误", "不对", "不存在", "过期")
        )
        for m in _extract_error_msgs(text)
    )


def login(account, password, session=None, max_retry=10, verbose=True):
    """自动登录：获取验证码 -> 识别 -> 提交，验证码识别错自动换新码重试。

    单张识别准确率约 90% 时，10 次重试几乎必然成功。
    返回 (是否成功, session, 失败原因)；成功时原因为空串。
    """
    session = session or get_session()
    reason = ""
    unknown_streak = 0
    for attempt in range(1, max_retry + 1):
        captcha = get_captcha(session)
        code = recognize(captcha)
        if verbose:
            print(f"[尝试 {attempt}/{max_retry}] 验证码识别结果: {code}")

        # 1) 取加密因子 scode#sxh
        resp = session.post(
            BASE_URL + "/Logon.do?method=logon&flag=sess", timeout=10
        )
        if "#" not in resp.text:
            reason = "获取加密因子失败(网络异常)"
            continue
        scode, sxh = resp.text.strip().split("#", 1)
        encoded = encode_login(account, password, scode, sxh)

        # 2) 提交登录
        r = session.post(
            BASE_URL + "/Logon.do?method=logon",
            data={
                "encoded": encoded,
                "RANDOMCODE": code,
                "useDogCode": "",
            },
            timeout=10,
            allow_redirects=True,
        )
        r.encoding = "utf-8"  # 登录页声明为 utf-8，避免 requests 猜错编码
        text = r.text or ""

        # 3) 结果判定：成功 / 验证码错(重试) / 账号错(立即失败) / 未知
        if any(k in text for k in ("退出", "欢迎你", "frameset", "欢迎登录")):
            if verbose:
                print(f"[尝试 {attempt}] 登录成功")
            return True, session, ""
        if _is_captcha_error(text):
            reason = f"验证码识别错误({code})，自动重试"
            unknown_streak = 0
            if verbose:
                print(f"[尝试 {attempt}] {reason}")
            continue
        if _is_account_error(text):
            msgs = _extract_error_msgs(text)
            return False, session, (msgs[0] if msgs else "账号或密码错误")
        # 未知响应：可能是措辞变化的验证码错误，允许连续 2 次后判定为账号问题
        reason = "未知响应(可能账号密码错误或验证码错误)"
        unknown_streak += 1
        if unknown_streak >= 2:
            return False, session, reason
    return False, session, reason or "超过最大重试次数"


def get_timetable(session):
    """抓取个人课表（本人课表 xskb_list.do）HTML。"""
    r = session.get(BASE_URL + "/jsxsd/xskb/xskb_list.do", timeout=15)
    r.encoding = "utf-8"
    return r.text


if __name__ == "__main__":
    # 独立调试：下载一张验证码并识别
    s = get_session()
    img = get_captcha(s)
    print("验证码图片大小:", len(img), "bytes")
    result, detail = recognize(img, return_detail=True)
    print("识别结果:", result)
    print("逐字符详情:", detail)
