"""初始化管理员账号

用法:
    # 交互式（推荐）
    python scripts/init_admin.py

    # 命令行指定
    python scripts/init_admin.py --username admin --password YOUR_PASS

    # 从 .env 的 ADMIN_PASSWORD_HASH 导入（兼容旧配置）
    python scripts/init_admin.py --from-env

环境变量:
    GATEWAY_DB_PATH  SQLite 路径（默认 /data/gateway.db）
"""
import argparse
import getpass
import os
import sqlite3
import sys
from pathlib import Path

import bcrypt

DB_PATH = os.getenv("SQLITE_DB_PATH", "/data/gateway.db")


def create_user(username: str, password_hash: str, role: str = "admin") -> None:
    """插入或更新用户（以 username 为唯一键）"""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    existing = conn.execute(
        "SELECT id FROM users WHERE username=?", (username,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE users SET password_hash=?, role=? WHERE username=?",
            (password_hash, role, username),
        )
        print(f"[init_admin] 已更新用户 '{username}' (role={role})")
    else:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
        )
        print(f"[init_admin] 已创建用户 '{username}' (role={role})")

    conn.commit()
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化管理员账号")
    parser.add_argument("--username", default="admin", help="用户名（默认 admin）")
    parser.add_argument("--password", help="明文密码（不指定则交互输入）")
    parser.add_argument("--role", default="admin", choices=["admin", "user"], help="角色（默认 admin）")
    parser.add_argument("--from-env", action="store_true", help="从 ADMIN_PASSWORD_HASH 环境变量导入哈希")
    args = parser.parse_args()

    if args.from_env:
        # 兼容旧配置：直接使用 .env 中的 bcrypt 哈希
        hash_val = os.getenv("ADMIN_PASSWORD_HASH", "")
        if not hash_val:
            print("[init_admin] 错误: ADMIN_PASSWORD_HASH 未设置", file=sys.stderr)
            sys.exit(1)
        # docker-compose 会把 $ 转义为 $$，这里还原
        hash_val = hash_val.replace("$$", "$")
        create_user(args.username, hash_val, args.role)
        return

    # 明文密码
    password = args.password
    if not password:
        password = getpass.getpass("请输入管理员密码: ")
        confirm = getpass.getpass("确认密码: ")
        if password != confirm:
            print("[init_admin] 错误: 两次密码不一致", file=sys.stderr)
            sys.exit(1)

    if len(password) < 6:
        print("[init_admin] 错误: 密码至少 6 位", file=sys.stderr)
        sys.exit(1)

    hash_val = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    create_user(args.username, hash_val, args.role)


if __name__ == "__main__":
    main()
