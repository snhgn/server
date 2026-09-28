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

# Let's inspect jsjy_query2 response table for week 4, day 1, periods 1-2
url = "http://newjwxt.bjfu.edu.cn/jsxsd/kbxx/jsjy_query2"
data = {
    "typewhere": "jszq",
    "xnxqh": "2026-2027-1",
    "jxlbh": "",
    "jsbh": "",
    "bjfh": "=",
    "rnrs": "",
    "jszt": "5",
    "zc": "4",
    "zc2": "4",
    "xq": "1",
    "xq2": "1",
    "jc": "01",
    "jc2": "02",
}
headers = {"Referer": "http://newjwxt.bjfu.edu.cn/jsxsd/kbxx/jsjy_query?Ves632DSdyV=NEW_XSD_PYGL"}
r = sess.post(url, data=data, headers=headers, timeout=15)
soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "html.parser")
table = soup.find("table", id="dataList") or soup.find("table")
if table:
    rows = table.find_all("tr")
    print(f"Table found with {len(rows)} rows.")
    for i, tr in enumerate(rows[:10]):
        tds = [td.text.strip() for td in tr.find_all(["td", "th"])]
        print(f"Row {i}: {tds}")
else:
    print("No table found!")
    print(r.text[:1000])

# Let's check toolbox.get_free_classrooms with these exact params:
rooms = toolbox.get_free_classrooms(sess, semester="2026-2027-1", building="", week=4, day=1, start_period=1, end_period=2)
print(f"toolbox.get_free_classrooms count: {len(rooms)}")
if rooms:
    print("First 3 rooms:", rooms[:3])

# What about building="014" (Xueyan)?
rooms_xueyan = toolbox.get_free_classrooms(sess, semester="2026-2027-1", building="014", week=4, day=1, start_period=1, end_period=2)
print(f"toolbox.get_free_classrooms Xueyan (014) count: {len(rooms_xueyan)}")
if rooms_xueyan:
    print("First 3 Xueyan:", rooms_xueyan[:3])
