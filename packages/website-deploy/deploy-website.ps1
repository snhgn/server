# ============================================================
#  snhgn.me website deploy script (Windows side)
#
#  Flow: npm build -> pscp upload dist -> server replace -> verify
#  Usage: powershell -File deploy-website.ps1
#  Dependencies: npm / pscp / plink (PuTTY)
# ============================================================

param(
    [string]$Server     = "192.168.50.2",
    [string]$User       = "snhgn",
    [string]$Password   = "1",
    [string]$HostKey    = "SHA256:roEbdNCO4i18oR7yR1r9HY6kUcE9/hJJsELFJ2CI46I",
    [string]$ProjectDir = "d:\project\snhgn.me"
)

$ErrorActionPreference = "Stop"
$PLINK = "C:\Program Files\PuTTY\plink.exe"
$PSCP  = "C:\Program Files\PuTTY\pscp.exe"

function Invoke-Remote([string]$cmd) {
    # plink needs a leading Enter when no TTY to skip the banner
    "`n" | & $PLINK -ssh -T -hostkey $HostKey -pw $Password "${User}@${Server}" $cmd
    if ($LASTEXITCODE -ne 0) { throw "Remote command failed: $cmd" }
}

# 0. check tools
foreach ($tool in @($PLINK, $PSCP)) {
    if (-not (Test-Path $tool)) { throw "Not found: $tool (install PuTTY first)" }
}

Write-Host "[1/4] Building frontend..." -ForegroundColor Cyan
Push-Location $ProjectDir
try {
    npm run build
} finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) { throw "npm build failed" }

$dist = Join-Path $ProjectDir "dist"

Write-Host "[2/4] Uploading dist to server /tmp/web/ ..." -ForegroundColor Cyan
Invoke-Remote "mkdir -p /tmp/web"
& $PSCP -batch -pw $Password -hostkey $HostKey -r "$dist\*" "${User}@${Server}:/tmp/web/"
if ($LASTEXITCODE -ne 0) { throw "pscp upload failed" }

Write-Host "[3/4] Replacing website files on server..." -ForegroundColor Cyan
Invoke-Remote "echo $Password | sudo -S bash -c 'rm -rf /opt/website/web/* && cp -r /tmp/web/* /opt/website/web/'"

Write-Host "[4/4] Verifying..." -ForegroundColor Cyan
Invoke-Remote "curl -s -o /dev/null -w 'home -> HTTP %{http_code}`n' https://snhgn.me; curl -s -o /dev/null -w 'dashboard -> HTTP %{http_code}`n' https://snhgn.me/dashboard"

Write-Host "Deploy finished." -ForegroundColor Green
