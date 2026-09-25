#!/usr/bin/env bash
set -euo pipefail

cd /tmp
tar -zxf /tmp/frp.tar.gz
cp /tmp/frp_*_linux_amd64/frpc /usr/local/bin/frpc
chmod +x /usr/local/bin/frpc
mkdir -p /etc/frp

cat << "EOF" > /etc/frp/frpc.toml
serverAddr = "47.114.63.37"
serverPort = 7000
auth.method = "token"
auth.token = "snhgn_frp_token_8899"

[[proxies]]
name = "web_https"
type = "tcp"
localIP = "127.0.0.1"
localPort = 443
remotePort = 443

[[proxies]]
name = "web_http"
type = "tcp"
localIP = "127.0.0.1"
localPort = 80
remotePort = 80

[[proxies]]
name = "web_https_alt"
type = "tcp"
localIP = "127.0.0.1"
localPort = 443
remotePort = 8443

[[proxies]]
name = "web_http_alt"
type = "tcp"
localIP = "127.0.0.1"
localPort = 80
remotePort = 8080

[[proxies]]
name = "ssh_relay"
type = "tcp"
localIP = "127.0.0.1"
localPort = 22
remotePort = 22022
EOF

cat << "EOF" > /etc/systemd/system/frpc.service
[Unit]
Description=Frp Client Service
After=network.target syslog.target
Wants=network.target

[Service]
Type=simple
Restart=always
RestartSec=5s
ExecStart=/usr/local/bin/frpc -c /etc/frp/frpc.toml

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable frpc
systemctl restart frpc
systemctl is-active frpc
