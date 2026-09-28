import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app.schedule import captcha, toolbox

user = "260101208"
pwd = "Qq513512686@"

ok, sess, reason = captcha.login(user, pwd)
if not ok:
    print("Login failed:", reason)
    sys.exit(1)

for bld in ["", "001", "003", "014"]:
    rooms = toolbox.get_free_classrooms(sess, semester="2026-2027-1", building=bld, week=4, day=1, start_period=1, end_period=2)
    print(f"Building '{bld}': found {len(rooms)} free rooms")
    if rooms:
        print("  Sample rooms:", [r["name"] for r in rooms[:5]])
