import requests
from bs4 import BeautifulSoup

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://newjwxt.bjfu.edu.cn/jsxsd/kbxx/jsjy_query?Ves632DSdyV=NEW_XSD_PYGL"
})

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
r = s.post(url, data=data, timeout=15)
print("Unauthenticated jsjy_query2 status:", r.status_code, "len:", len(r.text))
soup = BeautifulSoup(r.text, "html.parser")
table = soup.find("table", id="dataList") or soup.find("table")
if table:
    print("Found table without login! Rows:", len(table.find_all("tr")))
else:
    print("No table without login! First 300 chars:")
    print(r.text[:300])
