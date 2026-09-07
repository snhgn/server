$PLINK = "C:\Program Files\PuTTY\plink.exe"
$HostKey = "SHA256:roEbdNCO4i18oR7yR1r9HY6kUcE9/hJJsELFJ2CI46I"
$User = "snhgn"
$Server = "192.168.50.2"
$Password = "1"

function Remote([string]$c) {
    "`n" | & $PLINK -ssh -T -hostkey $HostKey -pw $Password "${User}@${Server}" $c
}

Write-Host "=== 1. NOTICE MONITOR DIRECTORY ==="
Remote "ls -la /opt/snhgn/scripts/notice-monitor"

Write-Host "`n=== 2. ROOT CRONTAB ==="
Remote "echo $Password | sudo -S crontab -l"

Write-Host "`n=== 3. SCHEDULER CONTAINER LOGS (LAST 50 LINES) ==="
Remote "docker logs --tail 50 scheduler"

Write-Host "`n=== 4. NOTICE MONITOR LOGS ==="
Remote "ls -la /opt/snhgn/logs/; tail -n 50 /opt/snhgn/scripts/notice-monitor/notice_monitor.log 2>/dev/null || tail -n 50 /opt/snhgn/logs/notice_monitor.log 2>/dev/null"

Write-Host "`n=== 5. CHECK RUNNING CRON OR SCHEDULER JOBS ==="
Remote "docker exec scheduler python -c 'import urllib.request; print(urllib.request.urlopen(\"http://127.0.0.1:8002/api/scheduler/jobs\").read().decode())' 2>/dev/null || curl -s http://127.0.0.1:8002/api/scheduler/jobs"
