#!/bin/bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
echo "======== sports list area ========"
html=$(curl -s -m 15 -A "$UA" "https://sports.bjfu.edu.cn/ygzp2/index.html")
echo "  SIZE=${#html}"
echo "$html" | python3 -c '
import sys, re
raw = sys.stdin.read()
# 找含日期 20xx-xx-xx 的片段上下文
for m in re.finditer(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", raw):
    s = max(0, m.start()-160); e = min(len(raw), m.end()+60)
    frag = re.sub(r"\s+", " ", raw[s:e]).strip()
    print("  ...", frag[:280])
    if frag.find("</li>") == -1: continue
'
