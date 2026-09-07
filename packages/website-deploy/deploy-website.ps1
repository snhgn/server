# ============================================================
#  snhgn.me website deploy script (Windows side)
#
#  Flow: check build/static -> pscp upload dist -> server replace -> verify
#  Usage: powershell -File deploy-website.ps1
#  Dependencies: pscp / plink (PuTTY)
# ============================================================

param(
    [string]$Server     = "192.168.50.2",
    [string]$User       = "snhgn",
    [string]$Password   = "1",
    [string]$HostKey    = "SHA256:roEbdNCO4i18oR7yR1r9HY6kUcE9/hJJsELFJ2CI46I",
    [string]$SourceDir  = "$PSScriptRoot\deploy\web"
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

Write-Host "[1/4] Preparing website assets from: $SourceDir" -ForegroundColor Cyan
if (-not (Test-Path $SourceDir)) {
    # Fallback to local deploy/web if relative path
    $fallback = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "deploy\web"
    if (Test-Path $fallback) {
        $SourceDir = $fallback
    } else {
        throw "Source directory not found: $SourceDir"
    }
}

Write-Host "[2/4] Uploading assets to server /tmp/web/ ..." -ForegroundColor Cyan
Invoke-Remote "mkdir -p /tmp/web"
& $PSCP -batch -pw $Password -hostkey $HostKey -r "$SourceDir\*" "${User}@${Server}:/tmp/web/"
if ($LASTEXITCODE -ne 0) { throw "pscp upload failed" }

Write-Host "[3/4] Replacing website files on server..." -ForegroundColor Cyan
Invoke-Remote "echo $Password | sudo -S bash -c 'rm -rf /opt/website/web/* && cp -r /tmp/web/* /opt/website/web/'"

Write-Host "[4/4] Verifying..." -ForegroundColor Cyan
Invoke-Remote "curl -s -o /dev/null -w 'home -> HTTP %{http_code}`n' http://127.0.0.1:8080"

Write-Host "Deploy finished successfully! Access at: https://snhgn.me" -ForegroundColor Green
