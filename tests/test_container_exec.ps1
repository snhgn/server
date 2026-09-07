$PLINK = "C:\Program Files\PuTTY\plink.exe"
$HostKey = "SHA256:roEbdNCO4i18oR7yR1r9HY6kUcE9/hJJsELFJ2CI46I"
$User = "snhgn"
$Server = "192.168.50.2"
$Password = "1"

function Remote([string]$c) {
    "`n" | & $PLINK -ssh -T -hostkey $HostKey -pw $Password "${User}@${Server}" $c
}

Write-Host "Running notice monitor inside scheduler container..." -ForegroundColor Cyan
Remote "docker exec scheduler python /app/scripts/notice-monitor/main.py"
