#!/bin/bash
# 探查各目标网站列表页结构
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
SITES=(
  "https://gxy.bjfu.edu.cn/tongzhigonggao/"
  "https://gxy.bjfu.edu.cn/benkejiaoxue/jiaowutongzhi/"
  "https://sports.bjfu.edu.cn/ygzp2/index.html"
  "https://jwc.bjfu.edu.cn/ksxx/index.html"
  "https://jwc.bjfu.edu.cn/jwkx/index.html"
  "https://jwc.bjfu.edu.cn/tkxx/index.html"
  "https://jwc.bjfu.edu.cn/jgdt/index.html"
  "https://jwc.bjfu.edu.cn/xzzq/index.html"
)
for url in "${SITES[@]}"; do
  echo "======== $url ========"
  html=$(curl -s -m 15 -A "$UA" "$url")
  if [ -z "$html" ]; then echo "  (empty/blocked)"; continue; fi
  echo "  SIZE=${#html}"
  # 找所有 <a ... href="...">标题</a> 且 URL 含日期或 .html 的链接，打印 title 和 href
  echo "$html" | python3 -c '
import sys, re
from html.parser import HTMLParser
raw = sys.stdin.read()
# 简单提取：<a href="..." ...>text</a>，text 含汉字或年份数字
for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", raw, re.S):
    href, text = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
    if not text: continue
    if re.search(r"[0-9]{4}|通知|公告|关于|报名|公示|安排|招聘|比赛|竞赛", text) and len(text) < 60:
        print(f"  [{text[:45]}] -> {href[:80]}")
' 2>/dev/null | head -12
  echo
done
