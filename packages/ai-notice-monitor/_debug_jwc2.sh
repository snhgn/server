#!/bin/bash
cat <<'PY' | docker exec -i scheduler python3
import sys
sys.path.insert(0, '/data/scripts/notice-monitor')
import requests
from bs4 import BeautifulSoup
url = 'https://jwc.bjfu.edu.cn/ksxx/ad4cac36045c4df29f900273ff78fd8f.html'
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}, timeout=15)
r.encoding = r.apparent_encoding or 'utf-8'
soup = BeautifulSoup(r.text, 'html.parser')
count = 0
for tag in soup.find_all(True):
    cls = tag.get('class') or []
    joined = ' '.join(cls) if isinstance(cls, list) else str(cls)
    if 'content' in joined.lower() or 'trbox' in joined.lower() or 'article' in tag.name:
        t = tag.get_text(' ', strip=True)
        print(f'tag={tag.name} class={joined!r} len={len(t)} head={t[:50]!r}')
        count += 1
        if count > 15: break
print('count shown =', count)
PY
