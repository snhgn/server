#!/usr/bin/env bash
# ==========================================================
# Automated Campus DDNS for lan.snhgn.me
# Checks IPv4 on wlp3s0, updates Cloudflare DNS if changed
# ==========================================================
set -euo pipefail

ZONE_ID="ab9b417062d31d2237114d94a75a53f0"
RECORD_NAME="lan.snhgn.me"
RECORD_ID="94c7a17232796ff665e8e40b485e6a8b"
IP_FILE="/opt/snhgn/data/campus_ip.txt"
LOG_FILE="/opt/snhgn/logs/campus_ddns.log"
CF_INI="/opt/website/cf.ini"

if [ ! -f "$CF_INI" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Error: $CF_INI not found" >> "$LOG_FILE"
    exit 1
fi

CF_EMAIL=$(grep dns_cloudflare_email "$CF_INI" | awk -F '=' '{print $2}' | tr -d ' ')
CF_KEY=$(grep dns_cloudflare_api_key "$CF_INI" | awk -F '=' '{print $2}' | tr -d ' ')

CURRENT_IP=$(ip -4 addr show wlp3s0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1 || true)

if [ -z "$CURRENT_IP" ]; then
    exit 0
fi

LAST_IP=""
if [ -f "$IP_FILE" ]; then
    LAST_IP=$(cat "$IP_FILE")
fi

if [ "$CURRENT_IP" != "$LAST_IP" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Campus IP changed from '$LAST_IP' to '$CURRENT_IP'. Updating Cloudflare DNS..." >> "$LOG_FILE"
    
    RESPONSE=$(curl -s -X PUT "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records/${RECORD_ID}" \
        -H "X-Auth-Email: ${CF_EMAIL}" \
        -H "X-Auth-Key: ${CF_KEY}" \
        -H "Content-Type: application/json" \
        --data "{\"type\":\"A\",\"name\":\"${RECORD_NAME}\",\"content\":\"${CURRENT_IP}\",\"ttl\":60,\"proxied\":false}")
    
    SUCCESS=$(echo "$RESPONSE" | grep -o '"success":true' || true)
    if [ -n "$SUCCESS" ]; then
        echo "$CURRENT_IP" > "$IP_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cloudflare DNS update successful for ${RECORD_NAME} -> ${CURRENT_IP}" >> "$LOG_FILE"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cloudflare DNS update failed: $RESPONSE" >> "$LOG_FILE"
    fi
fi
