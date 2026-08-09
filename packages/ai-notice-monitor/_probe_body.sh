#!/bin/bash
cat <<'PY' | docker exec -i scheduler python3
import sys, re
sys.path.insert(0, '/data/scripts/notice-monitor')
import requests
from bs4 import BeautifulSoup
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def probe(url, label):
    print(f'==== {label} ====')
    r = requests.get(url, headers={'User-Agent': UA}, timeout=15)
    r.encoding = r.apparent_encoding or 'utf-8'
    soup = BeautifulSoup(r.text, 'html.parser')
    best = []
    for tag in soup.find_all(['div', 'article', 'section', 'td']):
        t = tag.get_text(' ', strip=True)
        if len(t) > 150:
            cls = ' '.join(tag.get('class') or [])
            sel = cls or (tag.get('id') or '')
            best.append((len(t), sel, t[:50]))
    best.sort(reverse=True)
    for l, sel, head in best[:6]:
        print(f'  len={l} sel={sel!r} head={head!r}')
    print()

probe('https://gxy.bjfu.edu.cn/xuegongtiandi/tzgg_xg/8289bf9bae0849679ab9400124805d40.html', 'gxy detail')
probe('https://jwc.bjfu.edu.cn/ksxx/ad4cac36045c4df29f900273ff78fd8f.html', 'jwc detail')
probe('https://sports.bjfu.edu.cn/ygzp2/372570.html', 'sports detail')
PY
