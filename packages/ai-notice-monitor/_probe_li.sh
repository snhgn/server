#!/bin/bash
# 探查每个站点列表项结构（li/a/span 原始片段）
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
SITES=(
  "gxy_tz|https://gxy.bjfu.edu.cn/tongzhigonggao/"
  "gxy_jw|https://gxy.bjfu.edu.cn/benkejiaoxue/jiaowutongzhi/"
  "sports|https://sports.bjfu.edu.cn/ygzp2/index.html"
  "jwc_ksxx|https://jwc.bjfu.edu.cn/ksxx/index.html"
  "jwc_jwkx|https://jwc.bjfu.edu.cn/jwkx/index.html"
  "jwc_tkxx|https://jwc.bjfu.edu.cn/tkxx/index.html"
  "jwc_jgdt|https://jwc.bjfu.edu.cn/jgdt/index.html"
  "jwc_xzzq|https://jwc.bjfu.edu.cn/xzzq/index.html"
)
for entry in "${SITES[@]}"; do
  name="${entry%%|*}"
  url="${entry#*|}"
  echo "======== $name : $url ========"
  html=$(curl -s -m 15 -A "$UA" "$url")
  echo "$html" | python3 -c '
import sys, re
raw = sys.stdin.read()
# 找出含日期数字的 li 片段
blocks = re.findall(r"<li[^>]*>.*?</li>", raw, re.S)
cnt = 0
for b in blocks:
    if re.search(r"20[0-9]{2}", b):
        # 压缩空白
        b = re.sub(r"\s+", " ", b).strip()[:220]
        print("  LI:", b)
        cnt += 1
        if cnt >= 4: break
if cnt == 0:
    # 找含日期数字的任意小片段
    for b in re.findall(r"<[^>]*20[0-9]{2}[^>]*>.*?</[^>]+>", raw, re.S)[:4]:
        b = re.sub(r"\s+", " ", b).strip()[:200]
        print("  FRAG:", b)
'
  echo
done
