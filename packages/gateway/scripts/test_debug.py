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

print(f"Logging in with {user}...")
ok, sess, reason = captcha.login(user, pwd)
if not ok:
    print(f"Login failed: {reason}")
    sys.exit(1)

print("Login successful! Session cookies:", sess.cookies.get_dict())

# 1. Test Grades Query Page
print("\n--- Testing Grades ---")
query_url = "http://newjwxt.bjfu.edu.cn/jsxsd/kscj/cjcx_query?Ves632DSdyV=NEW_XSD_XJCJ"
r_query = sess.get(query_url, timeout=15)
print("cjcx_query status:", r_query.status_code, "len:", len(r_query.text))
soup_q = BeautifulSoup(r_query.text, "html.parser")
form = soup_q.find("form")
if form:
    print("Found form action:", form.get("action"))
    inputs = {inp.get("name"): inp.get("value", "") for inp in form.find_all("input") if inp.get("name")}
    selects = {sel.get("name"): [opt.get("value") for opt in sel.find_all("option")] for sel in form.find_all("select") if sel.get("name")}
    print("Form inputs:", inputs)
    print("Form selects:", selects)
else:
    print("No form found in cjcx_query!")

# Try POST cjcx_list
list_url = "http://newjwxt.bjfu.edu.cn/jsxsd/kscj/cjcx_list"
data = {"kksj": "", "kcxz": "", "kcmc": "", "xsfs": "all"}
r_list = sess.post(list_url, data=data, timeout=15)
print("cjcx_list status:", r_list.status_code, "len:", len(r_list.text))
soup_l = BeautifulSoup(r_list.text, "html.parser")
table = soup_l.find("table", id="dataList") or soup_l.find("table")
if table:
    print("Found table in cjcx_list, rows:", len(table.find_all("tr")))
    for tr in table.find_all("tr")[:5]:
        print("  ROW:", [td.text.strip() for td in tr.find_all(["td", "th"])])
else:
    print("No table found in cjcx_list! Sample text:")
    print(r_list.text[:800])

# Try toolbox.get_grades
res_grades = toolbox.get_grades(sess)
print("toolbox.get_grades result:", res_grades)

# 2. Test Classrooms Query Page
print("\n--- Testing Classrooms ---")
js_query_url = "http://newjwxt.bjfu.edu.cn/jsxsd/kbxx/jsjy_query?Ves632DSdyV=NEW_XSD_PYGL"
r_jsq = sess.get(js_query_url, timeout=15)
print("jsjy_query status:", r_jsq.status_code, "len:", len(r_jsq.text))
soup_jq = BeautifulSoup(r_jsq.text, "html.parser")
jform = soup_jq.find("form")
if jform:
    print("Found form action in jsjy_query:", jform.get("action"))
    jinputs = {inp.get("name"): inp.get("value", "") for inp in jform.find_all("input") if inp.get("name")}
    jselects = {sel.get("name"): [(opt.get("value"), opt.text.strip()) for opt in sel.find_all("option")] for sel in jform.find_all("select") if sel.get("name")}
    print("Form inputs:", jinputs)
    print("Form selects keys:", list(jselects.keys()))
    for k, v in jselects.items():
        print(f"  select {k}: {v[:5]}")
else:
    print("No form found in jsjy_query!")
    print(r_jsq.text[:800])

# Test toolbox.get_free_classrooms with building=''
print("\nTesting get_free_classrooms with building=''...")
try:
    rooms_all = toolbox.get_free_classrooms(sess, semester="2026-2027-1", building="", week=3, day=2, start_period=1, end_period=2)
    print("get_free_classrooms building='' result count:", len(rooms_all))
    if rooms_all:
        print("Sample room:", rooms_all[0])
except Exception as e:
    print("get_free_classrooms building='' EXCEPTION:", type(e), e)

# Test toolbox.get_free_classrooms with building='001'
print("\nTesting get_free_classrooms with building='001'...")
try:
    rooms_001 = toolbox.get_free_classrooms(sess, semester="2026-2027-1", building="001", week=3, day=2, start_period=1, end_period=2)
    print("get_free_classrooms building='001' result count:", len(rooms_001))
    if rooms_001:
        print("Sample room:", rooms_001[0])
except Exception as e:
    print("get_free_classrooms building='001' EXCEPTION:", type(e), e)
