# -*- coding: utf-8 -*-
"""公网 HTTPS 完整登录流验证(浏览器 → Cloudflare → 隧道 → Caddy → gateway)
等价于:登录 → 刷新页面 → 重开浏览器 → logout → 旧 Cookie 失效
"""
import httpx

BASE = "https://snhgn.me"

with httpx.Client(base_url=BASE, timeout=30.0) as c:
    print("== 1. 公网登录 ==")
    r = c.post("/api/auth/login", json={"username": "__s_test__", "password": "s-test-123"})
    print("   status:", r.status_code)
    for sc in r.headers.get_list("set-cookie"):
        print("   set-cookie:", sc[:110])
    assert r.status_code == 200 and r.json()["success"], "login failed"

    print("== 2. 仅凭 Cookie 访问 /me(等价刷新页面/重开浏览器,新连接) ==")
    r2 = c.get("/api/auth/me")
    print("   /me:", r2.status_code, r2.json())
    assert r2.status_code == 200 and r2.json()["user"]["username"] == "__s_test__"

    print("== 3. 仅凭 Cookie 访问受保护 AI API ==")
    r3 = c.get("/api/ai/conversations")
    print("   ai/conversations:", r3.status_code, r3.text[:80])
    assert r3.status_code == 200

    print("== 4. logout 后旧 Cookie 必须失效 ==")
    r4 = c.post("/api/auth/logout")
    print("   logout:", r4.status_code, r4.text)
    r5 = c.get("/api/auth/me")
    print("   logout后 /me:", r5.status_code, "(期望 401)")
    assert r5.status_code == 401

    print("== ALL PASS ==")
