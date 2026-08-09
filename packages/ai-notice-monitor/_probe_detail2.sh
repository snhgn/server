#!/bin/bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
probe() {
  url="$1"
  echo "======== $url ========"
  html=$(curl -s -m 15 -A "$UA" "$url")
  echo "$html" | python3 -c '
import sys, re
raw = sys.stdin.read()
# 打印所有 div/section/article 的 class 出现次数（正文区通常文字量大）
from collections import Counter
classes = Counter()
for m in re.finditer(r"<(div|section|article|table)[^>]*class=\"([^\"]+)\"", raw, re.I):
    classes[m.group(2)] += 1
for cls, cnt in classes.most_common(25):
    print(f"  class={cls!r} x{cnt}")
'
}
probe "https://jwc.bjfu.edu.cn/ksxx/ad4cac36045c4df29f900273ff78fd8f.html"
probe "https://gxy.bjfu.edu.cn/xuegongtiandi/tzgg_xg/8289bf9bae0849679ab9400124805d40.html"
