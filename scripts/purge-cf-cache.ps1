# Cloudflare 全量缓存清除（部署新前端后运行）
# 用法1: .\scripts\purge-cf-cache.ps1
# 用法2: .\scripts\purge-cf-cache.ps1 -Email "xx@yy.com" -Key "cfk_xxx"
# 凭据优先级: 参数 > 环境变量 CF_API_EMAIL / CF_API_KEY
param(
  [string]$Email,
  [string]$Key
)

if (-not $Email) { $Email = $env:CF_API_EMAIL }
if (-not $Key)   { $Key   = $env:CF_API_KEY }

if (-not $Email -or -not $Key) {
  Write-Error "缺少凭据: 请传参或设置环境变量 CF_API_EMAIL / CF_API_KEY"
  exit 1
}

$zoneId = 'ab9b417062d31d2237114d94a75a53f0'  # snhgn.me
$headers = @{
  'X-Auth-Email' = $Email
  'X-Auth-Key'   = $Key
  'Content-Type' = 'application/json'
}
$body = '{"purge_everything":true}'

try {
  $r = Invoke-RestMethod -Method Post `
    -Uri "https://api.cloudflare.com/client/v4/zones/$zoneId/purge_cache" `
    -Headers $headers -Body $body -TimeoutSec 30
  if ($r.success) {
    Write-Host "PURGE_OK $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
  } else {
    Write-Error ($r.errors | ConvertTo-Json -Compress)
    exit 1
  }
} catch {
  $resp = $_.Exception.Response
  if ($resp) {
    Write-Error (New-Object IO.StreamReader($resp.GetResponseStream())).ReadToEnd()
  } else {
    Write-Error $_.Exception.Message
  }
  exit 1
}
