#!/bin/bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
probe_detail() {
  url="$1"
  echo "======== $url ========"
  html=$(curl -s -m 15 -A "$UA" "$url")
  echo "  SIZE=${#html}"
  echo "$html" | python3 -c '
import sys, re
raw = sys.stdin.read()
# 找主要正文容器：常见的 content class/id
for pat in [r"class=\"[^\"]*(content|article|detail|newsCont|v_news_content|TRS_Editor|read)[^\"]*\"", r"id=\"[^\"]*(content|article|detail|newsCont|read)[^\"]*\""]:
    for m in re.finditer(pat, raw, re.I):
        s = max(0, m.start()-40); e = min(len(raw), m.end()+60)
        frag = re.sub(r"\s+", " ", raw[s:e]).strip()
        print("  HIT:", frag[:200])
        break
    break
# 标题
m = re.search(r"<title>(.*?)</title>", raw, re.S)
if m: print("  TITLE:", m.group(1).strip()[:80])
'
}
probe_detail "https://gxy.bjfu.edu.cn/xuegongtiandi/tzgg_xg/8289bf9bae0849679ab9400124805d40.html"
probe_detail "https://jwc.bjfu.edu.cn/ksxx/ad4cac36045c4df29f900273ff78fd8f.html"
probe_detail "https://sports.bjfu.edu.cn/ygzp2/372570.html"
