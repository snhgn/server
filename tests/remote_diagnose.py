import sys
import os

sys.path.insert(0, "/opt/bjfu-login/src")
import checker
import login
import main

print("=== 1. CHECK CURRENT STATUS ===")
print("checker.is_online():", checker.is_online())

cfg = main.load_config()
print("Config loaded. Username:", cfg.get("BJFU_USERNAME"))
url = cfg.get("LOGIN_URL", "http://10.1.1.10")

print("=== 2. ATTEMPTING LOGIN ===")
res = login.do_login(cfg["BJFU_USERNAME"], cfg["BJFU_PASSWORD"], url)
print("do_login result:", res)

print("=== 3. CHECK AFTER LOGIN ===")
print("checker.is_online():", checker.is_online())
