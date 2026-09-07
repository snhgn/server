$PLINK = "C:\Program Files\PuTTY\plink.exe"
$PSCP  = "C:\Program Files\PuTTY\pscp.exe"
$HostKey = "SHA256:roEbdNCO4i18oR7yR1r9HY6kUcE9/hJJsELFJ2CI46I"
$User = "snhgn"
$Server = "192.168.50.2"
$Password = "1"

function Remote([string]$c) {
    "`n" | & $PLINK -ssh -T -hostkey $HostKey -pw $Password "${User}@${Server}" $c
}

Write-Host "[1/3] Uploading updated notice monitor files to server /tmp/notice_update/ ..." -ForegroundColor Cyan
Remote "mkdir -p /tmp/notice_update"

$files = @(
    "d:\project\server\packages\ai-notice-monitor\config.py",
    "d:\project\server\packages\ai-notice-monitor\email_sender.py",
    "d:\project\server\packages\ai-notice-monitor\main.py"
)

foreach ($f in $files) {
    & $PSCP -batch -pw $Password -hostkey $HostKey $f "${User}@${Server}:/tmp/notice_update/"
}

Write-Host "[2/3] Moving files to /opt/snhgn/scripts/notice-monitor/ ..." -ForegroundColor Cyan
Remote "cp /tmp/notice_update/* /opt/snhgn/scripts/notice-monitor/"

Write-Host "[3/3] Running notice monitor on server to test email sending ..." -ForegroundColor Cyan
Remote "cd /opt/snhgn/scripts/notice-monitor && python3 main.py"

Write-Host "Done." -ForegroundColor Green
