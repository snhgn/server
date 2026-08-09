#!/bin/bash
cat <<'PY' | docker exec -i scheduler python3
import sys
sys.path.insert(0, '/data/scripts/notice-monitor')
from config import load_config
from scraper import NoticeScraper
cfg = load_config()
print('sites count =', len(cfg.sites))
for s in cfg.sites:
    print('  -', s.name, s.url)
scraper = NoticeScraper(cfg.scraper, cfg.sites)
total = 0
for site in cfg.sites:
    ns = scraper.fetch_site(site)
    total += len(ns)
    print(f'[抓取] {site.name}: {len(ns)} 条')
    for n in ns[:3]:
        print(f'   - {n.publish_time} [{n.source}] {n.title[:40]} -> {n.url[:70]}')
print('TOTAL =', total)
# 测试详情提取（各站点取第一条）
print('=== detail probe ===')
import itertools
for site in cfg.sites:
    ns = scraper.fetch_site(site)
    if not ns: continue
    n = ns[0]
    text = scraper.fetch_detail_text(n.url)
    print(f'[详情] {site.name}: {len(text)} chars | head: {text[:60]!r}')
PY
