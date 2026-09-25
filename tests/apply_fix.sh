#!/bin/bash
set -e

echo "=== 1. Backing up checker.py ==="
cp /opt/bjfu-login/src/checker.py /opt/bjfu-login/src/checker.py.bak_$(date +%s)

echo "=== 2. Applying new checker.py ==="
cp /tmp/checker.py /opt/bjfu-login/src/checker.py
chmod 644 /opt/bjfu-login/src/checker.py

echo "=== 3. Updating CHECK_INTERVAL to 60 ==="
sed -i 's/^CHECK_INTERVAL=.*/CHECK_INTERVAL=60/' /opt/bjfu-login/config/config.env

echo "=== 4. Testing checker ==="
/opt/bjfu-login/venv/bin/python /opt/bjfu-login/src/checker.py

echo "=== 5. Restarting bjfu-login service ==="
systemctl restart bjfu-login
sleep 2
systemctl status bjfu-login --no-pager

echo "=== 6. Checking log file ==="
tail -n 15 /opt/bjfu-login/logs/app.log
