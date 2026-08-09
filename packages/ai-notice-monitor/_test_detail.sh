#!/bin/bash
cat <<'PY' | docker exec -i scheduler python3
import sys
sys.path.insert(0, '/data/scripts/notice-monitor')
from config import load_config
from scraper import NoticeScraper
cfg = load_config()
scraper = NoticeScraper(cfg.scraper, cfg.sites)
for site in cfg.sites:
    ns = scraper.fetch_site(site)
    if not ns: continue
    n = ns[0]
    text = scraper.fetch_detail_text(n.url)
    print(f'[{site.name}] len={len(text)} | head={text[:70]!r}')
PY
