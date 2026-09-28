import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from bs4 import BeautifulSoup
from app.schedule import captcha, toolbox

user = "260101208"
pwd = "Qq513512686@"

ok, sess, reason = captcha.login(user, pwd)
if not ok:
    print("Login failed:", reason)
    sys.exit(1)

# Inspect jsjy_query selects
r = sess.get("http://newjwxt.bjfu.edu.cn/jsxsd/kbxx/jsjy_query?Ves632DSdyV=NEW_XSD_PYGL")
soup = BeautifulSoup(r.text, "html.parser")
jc_opts = [(o.get("value"), o.text.strip()) for o in soup.find("select", {"name": "jc"}).find_all("option")]
print("JC options:", jc_opts)

# Test 1-12 full day query
print("\nTesting full day 1-12:")
rooms_allday = toolbox.get_free_classrooms(sess, semester="2026-2027-1", building="", week=4, day=1, start_period=1, end_period=12)
print("1-12 full day free rooms count:", len(rooms_allday))
if rooms_allday:
    print("Sample:", [r["name"] for r in rooms_allday[:5]])

# Test periods 10-11 (evening)
print("\nTesting evening 10-11:")
rooms_evening = toolbox.get_free_classrooms(sess, semester="2026-2027-1", building="", week=4, day=1, start_period=10, end_period=11)
print("10-11 evening free rooms count:", len(rooms_evening))
