# -*- coding: utf-8 -*-
r"""登录 Session + 双通道鉴权测试（本地 venv 可运行，只依赖 gateway 的 app 包）。

覆盖：
1. 登录成功设置 HttpOnly Cookie（名称/HttpOnly/SameSite=lax/Max-Age=30d/非 Secure）
2. Cookie 访问 GET /api/auth/me 恢复当前用户
3. 未登录访问 /me → 401
4. Bearer JWT 兼容通道（旧客户端平滑过渡）
5. logout：服务端 Session 立即失效 + Cookie 清除 + 旧 sid 不可再用
6. Session 旋转：重新登录后旧 sid 失效（防 Session Fixation）
7. 过期 Session 被拒绝
8. 错误密码 401
9. require_user 下游依赖通过 Cookie 通道拿到完整 payload（uid/username/role）

运行（在 d:\project\server 下）：
    .venv/Scripts/python.exe -m unittest tests.test_auth_session -v
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="gw_session_")
os.environ.update({
    "SQLITE_DB_PATH": str(Path(_TMP) / "gateway.db"),
    "JWT_SECRET": "test-secret-for-unittest",
    "SESSION_COOKIE_SECURE": "false",
})

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "gateway"))

import bcrypt
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import sessions
from app.auth import require_user
from app.routers import auth as auth_router

COOKIE = "snhgn_session"

# ---- 测试 app：只挂 auth 路由 + 一个 require_user 假路由（不触发 schedule/lifespan）----
_app = FastAPI()
_app.include_router(auth_router.router)


@_app.get("/api/__test/user")
async def _probe(user: dict = Depends(require_user)):
    return user


client = TestClient(_app)

USERNAME = "alice"
PASSWORD = "pw-123456"


def _login(username: str = USERNAME, password: str = PASSWORD, cookie: str | None = None):
    client.cookies.clear()  # 全部用显式 headers 控制 Cookie，避免客户端自动携带串扰
    headers = {"Cookie": cookie} if cookie else {}
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers=headers,
    )
    client.cookies.clear()
    sid = None
    for c in resp.headers.get_list("set-cookie"):
        if c.startswith(f"{COOKIE}=") and "Max-Age=0" not in c:
            sid = c.split("=", 1)[1].split(";")[0]
    return resp, sid


class AuthSessionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = sqlite3.connect(os.environ["SQLITE_DB_PATH"])
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        sessions.init()
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (USERNAME, bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode(), "user"),
        )
        conn.commit()
        conn.close()

    def setUp(self):
        # 每个用例前清 user/session 缓存与测试客户端 Cookie，保证隔离
        client.cookies.clear()
        from app import auth as auth_mod
        auth_mod.invalidate_user_cache()

    # ---- 1. 登录设置 HttpOnly Cookie ----
    def test_login_sets_httponly_cookie(self):
        resp, sid = _login()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(sid and len(sid) > 30, "sid 应为高强度随机串")
        raw = "; ".join(resp.headers.get_list("set-cookie")).lower()
        self.assertIn("httponly", raw)
        self.assertIn("samesite=lax", raw)
        self.assertIn("max-age=2592000", raw)  # 30 天
        self.assertNotIn("secure", raw)        # 开发环境不设 Secure
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["token"])         # JWT 兼容通道保留
        self.assertEqual(body["user_id"], 1)

    # ---- 2. Cookie 访问 /me 恢复用户 ----
    def test_me_with_cookie(self):
        _, sid = _login()
        r = client.get("/api/auth/me", headers={"Cookie": f"{COOKIE}={sid}"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["authenticated"])
        self.assertEqual(data["user"]["username"], USERNAME)
        self.assertEqual(data["user"]["role"], "user")
        self.assertEqual(data["user"]["id"], 1)

    # ---- 3. 未登录 → 401 ----
    def test_me_without_auth_401(self):
        r = client.get("/api/auth/me")
        self.assertEqual(r.status_code, 401)

    # ---- 4. Bearer JWT 兼容通道（不带 cookie）----
    def test_me_with_bearer_jwt(self):
        resp, _ = _login()
        token = resp.json()["token"]
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["username"], USERNAME)

    # ---- 5. logout 立即失效 ----
    def test_logout_invalidates_session(self):
        _, sid = _login()
        r = client.post("/api/auth/logout", headers={"Cookie": f"{COOKIE}={sid}"})
        self.assertEqual(r.status_code, 200)
        raw = "; ".join(r.headers.get_list("set-cookie"))
        self.assertIn("Max-Age=0", raw)  # 清除客户端 Cookie
        # 旧 sid 不能再访问受保护 API
        r2 = client.get("/api/auth/me", headers={"Cookie": f"{COOKIE}={sid}"})
        self.assertEqual(r2.status_code, 401)

    # ---- 6. Session 旋转（防 fixation）----
    def test_session_rotation_on_relogin(self):
        _, sid1 = _login()
        _, sid2 = _login(cookie=f"{COOKIE}={sid1}")
        self.assertNotEqual(sid1, sid2)
        r = client.get("/api/auth/me", headers={"Cookie": f"{COOKIE}={sid1}"})
        self.assertEqual(r.status_code, 401, "重新登录后旧 Session 必须失效")
        r2 = client.get("/api/auth/me", headers={"Cookie": f"{COOKIE}={sid2}"})
        self.assertEqual(r2.status_code, 200)

    # ---- 7. 过期 Session 被拒绝 ----
    def test_expired_session_rejected(self):
        _, sid = _login()
        conn = sqlite3.connect(os.environ["SQLITE_DB_PATH"])
        conn.execute("UPDATE sessions SET expires_at='2000-01-01 00:00:00' WHERE sid=?", (sid,))
        conn.commit()
        conn.close()
        from app import auth as auth_mod
        auth_mod.invalidate_session_cache()  # 绕过 TTL 缓存
        r = client.get("/api/auth/me", headers={"Cookie": f"{COOKIE}={sid}"})
        self.assertEqual(r.status_code, 401)

    # ---- 8. 错误密码 401，且不设置 Cookie ----
    def test_wrong_password(self):
        resp, sid = _login(password="wrong-password")
        self.assertEqual(resp.status_code, 401)
        self.assertIsNone(sid)

    # ---- 9. 下游 require_user 依赖（Cookie 通道 payload 完整）----
    def test_require_user_via_cookie(self):
        _, sid = _login()
        r = client.get("/api/__test/user", headers={"Cookie": f"{COOKIE}={sid}"})
        self.assertEqual(r.status_code, 200)
        user = r.json()
        self.assertEqual(user["sub"], USERNAME)  # ai.py 等下游用 user["sub"]/["uid"]/["role"]
        self.assertEqual(user["uid"], 1)
        self.assertEqual(user["role"], "user")


if __name__ == "__main__":
    unittest.main(verbosity=2)
