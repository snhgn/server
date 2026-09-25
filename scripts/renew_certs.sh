#!/usr/bin/env bash
# ==========================================================
# Automated Let's Encrypt Certificate Renewal for lan.snhgn.me
# ==========================================================
set -euo pipefail

LOG_FILE="/opt/snhgn/logs/cert_renewal.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Checking certificate renewal..." >> "$LOG_FILE"

docker run --rm \
  -v /opt/website/cf.ini:/etc/letsencrypt/cf.ini:ro \
  -v /opt/website/certs:/etc/letsencrypt \
  certbot/dns-cloudflare renew \
  --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cf.ini >> "$LOG_FILE" 2>&1

chmod -R a+rX /opt/website/certs
docker exec caddy caddy reload --config /etc/caddy/Caddyfile >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Certificate renewal check completed." >> "$LOG_FILE"
