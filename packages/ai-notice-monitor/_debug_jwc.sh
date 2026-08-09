#!/bin/bash
cat <<'PY' | docker exec -i scheduler python3
import sys
sys.path.insert(0, '/data/scripts/notice-monitor')
from config import load_config
from scraper import NoticeScraper, _DETAIL_SELECTORS
import requests
from bs4 import BeautifulSoup

cfg = load_config()
scraper = NoticeScraper(cfg.scraper, cfg.sites)
url = 'https://jwc.bjfu.edu.cn/ksxx/ad4cac36045c4df29f900273ff78fd8f.html'
r = scraper.session.get(url, timeout=15)
r.encoding = r.apparent_encoding or 'utf-8'
soup = BeautifulSoup(r.text, 'html.parser')
for sel in _DETAIL_SELECTORS:
    el = soup.select_one(sel)
    if el is not None:
        t = el.get_text(' ', strip=True)
        print(f'MATCH sel={sel!r} len={len(t)} head={t[:40]!r}')
    else:
        print(f'miss sel={sel!r}')
# 找 class 含 contents 的元素
print('--- class search ---')
for el in soup.find_all(class_='contents'):
    print('found class=contents, tag=', el.name, 'attrs=', el.get('class'))
    break
else:
    print('NO element with class contents')
PY
