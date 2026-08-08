# -*- coding: utf-8 -*-
"""临时验证：接口数据正确性。"""
import requests

r = requests.get("http://127.0.0.1:8000/api/course", timeout=5)
data = r.json()
print("name[0]:", data[0]["name"])
print("teacher[0]:", data[0]["teacher"])
print("location[0]:", data[0]["location"])

types = {}
for c in data:
    types[c["week_type"]] = types.get(c["week_type"], 0) + 1
print("week_type 分布:", types)

for c in data:
    if c["name"].startswith("高等数学") and c["weekday"] == 2 and c["start_section"] == 3:
        print("高数(周二34节) weeks:", c["weeks"])
        break

r3 = requests.get("http://127.0.0.1:8000/api/course?week=3", timeout=5)
w3 = r3.json()
print("第3周课程数:", len(w3))
names3 = sorted(set(c["name"] for c in w3))
print("第3周课程:", names3)

r9 = requests.get("http://127.0.0.1:8000/api/course?week=9", timeout=5)
w9 = r9.json()
print("第9周课程数:", len(w9), "(高数1-8,10-14断裂，第9周应无高数)")
names9 = sorted(set(c["name"] for c in w9))
print("第9周课程:", names9)

# 单双周字段与 weeks 一致性
odd_courses = [c for c in data if c["week_type"] != "all"]
print("单双周课程示例:", [(c["name"], c["week_type"], c["weeks"][:5], c["weeks"][-3:]) for c in odd_courses[:3]])
