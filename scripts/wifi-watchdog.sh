#!/bin/bash
# Keep wlp3s0 connected to bjfu-wifi-office
IFACE="wlp3s0"
CON_NAME="bjfu-wifi-office"

IP=$(ip -4 addr show dev "$IFACE" 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
if [ -z "$IP" ]; then
    echo "$(date): $IFACE has no IPv4, reconnecting $CON_NAME..."
    nmcli con up "$CON_NAME"
fi
