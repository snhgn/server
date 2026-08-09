#!/bin/bash
cat <<'PY' | docker exec -i scheduler python3
import sys
sys.path.insert(0, '/data/scripts/notice-monitor')
from config import load_config
import requests
from bs4 import BeautifulSoup
cfg = load_config()
print('CFG UA =', repr(cfg.scraper.user_agent))
url = 'https://jwc.bjfu.edu.cn/ksxx/ad4cac36045c4df29f900273ff78fd8f.html'
UA2 = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
for label, headers in [
    ('cfg-ua', {'User-Agent': cfg.scraper.user_agent}),
    ('chrome120', {'User-Agent': UA2}),
    ('no-ua', {}),
]:
    r = requests.get(url, headers=headers, timeout=15)
    r.encoding = r.apparent_encoding or 'utf-8'
    soup = BeautifulSoup(r.text, 'html.parser')
    has = soup.find_all(class_='contents')
    print(f'{label}: status={r.status_code} size={len(r.text)} class_contents={len(has)}')
PY
