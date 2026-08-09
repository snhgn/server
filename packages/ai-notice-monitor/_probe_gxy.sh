#!/bin/bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
SITES=(
  "gxy_tz|https://gxy.bjfu.edu.cn/tongzhigonggao/"
  "gxy_jw|https://gxy.bjfu.edu.cn/benkejiaoxue/jiaowutongzhi/"
  "sports|https://sports.bjfu.edu.cn/ygzp2/index.html"
)
for entry in "${SITES[@]}"; do
  name="${entry%%|*}"
  url="${entry#*|}"
  echo "======== $name : $url ========"
  html=$(curl -s -m 15 -A "$UA" "$url")
  echo "  SIZE=${#html}"
  echo "$html" | python3 -c '
import sys, re
raw = sys.stdin.read()
blocks = re.findall(r"<li[^>]*>.*?</li>", raw, re.S)
cnt = 0
for b in blocks:
    if re.search(r"20[0-9]{2}|\.html", b):
        b = re.sub(r"\s+", " ", b).strip()[:260]
        print("  LI:", b)
        cnt += 1
        if cnt >= 5: break
if cnt == 0:
    for b in re.findall(r"<a[^>]+href=\"[^\"]+\"[^>]*>[^<]{2,40}</a>", raw, re.S)[:8]:
        b = re.sub(r"\s+", " ", b).strip()[:220]
        print("  A:", b)
'
  echo
done
