$PLINK = "C:\Program Files\PuTTY\plink.exe"
$HostKey = "SHA256:roEbdNCO4i18oR7yR1r9HY6kUcE9/hJJsELFJ2CI46I"
$User = "snhgn"
$Server = "192.168.50.2"
$Password = "1"

function Remote([string]$c) {
    "`n" | & $PLINK -ssh -T -hostkey $HostKey -pw $Password "${User}@${Server}" $c
}

Write-Host "=== 1. SERVER NOTICE MONITOR FILES ==="
Remote "ls -la /opt/snhgn/scripts/notice-monitor/"

Write-Host "`n=== 2. SERVER SCRIPT ENTRY IN SCRIPTS DB ==="
Remote "docker exec scheduler sqlite3 /data/sqlite/scripts.db 'SELECT id, name, command, cron, enabled FROM scripts;'"
