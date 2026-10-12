# ============================================================
#  snhgn.me 网站部署脚本 (Windows 侧)
#
#  Flow: 本地构建校验 -> pscp 上传 -> 服务器侧原子替换 -> 验证(失败自动回滚)
#  Usage:
#    $env:SNHGN_DEPLOY_PASSWORD = "<部署密码>"
#    powershell -ExecutionPolicy Bypass -File deploy-website.ps1 [-SkipBuild]
#  也可用 -Password 显式传密码；两者皆无则脚本在第 0 步直接失败。
#  Dependencies: pscp / plink (PuTTY)
#
#  默认以 web\dist 为载荷来源（唯一事实来源：vite 构建产物，
#  其中已包含 web\public 下的静态资源）。不再默认使用仓库里那份
#  历史遗留的 deploy\web 镜像 —— 它曾经与线上的实际内容不一致，
#  用它部署会把线上悄悄退回旧版。
# ============================================================

param(
    [string]$Server     = "192.168.50.2",
    [string]$User       = "snhgn",
    # 脱敏：密码不再硬编码进仓库。默认从环境变量 SNHGN_DEPLOY_PASSWORD 读取，
    # 需要时也可用 -Password 显式传入（显式传参优先）。
    [string]$Password   = $(if ($env:SNHGN_DEPLOY_PASSWORD) { $env:SNHGN_DEPLOY_PASSWORD } else { "" }),
    [string]$HostKey    = "SHA256:roEbdNCO4i18oR7yR1r9HY6kUcE9/hJJsELFJ2CI46I",
    # 留空则自动定位仓库根下的 web\dist
    [string]$SourceDir  = "",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$PLINK = "C:\Program Files\PuTTY\plink.exe"
$PSCP  = "C:\Program Files\PuTTY\pscp.exe"

# 仓库根 = 本脚本所在目录的上一级
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

# 执行一条远端命令，返回 [pscustomobject]@{ ExitCode; Output }
#
# 关键细节（2026-10-12 在 Windows PowerShell 5.1 上实测三条结论）：
#  1) $ErrorActionPreference="Stop" 时，原生命令一旦写 stderr 就会被升级成
#     终止性错误，且 2>file 重定向拦不住（实测：文件为空、直接 throw）；
#  2) sudo -S 即使成功读到密码，也会把 "[sudo] password for snhgn:" 写到 stderr
#     —— 这正是部署脚本在"其实已经成功了"的那一刻假失败的根因
#     （2026-10-03 的 f528069 用 2>&1 尝试修，无效：合并产生的是 ErrorRecord，
#      在 Stop 下照样 throw）；
#  3) 把 EAP 临时降为 Continue 后，用 2>&1 把 stderr 合并进输出流，再按对象类型
#     分流：String 是 stdout 原样透传，ErrorRecord 是 stderr、降级为信息打印。
#     退出码照常捕获，调用结束立即恢复 EAP。
function Invoke-Plink {
    param([string]$remoteCmd)
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        # -batch: 绝不让 plink 在本地抢着提示（主机密钥/口令），一旦远端失败要
        #         立刻拿退出码，而不是挂在那里等一个永远不会来的输入。
        $merged = "`n" | & $PLINK -ssh -T -batch -hostkey $HostKey -pw $Password "${User}@${Server}" $remoteCmd 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEap
    }
    $stdout = @($merged | Where-Object { $_ -is [string] })
    $stderr = @($merged | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] })
    if ($stdout) { $stdout | Write-Host }
    foreach ($e in $stderr) {
        if ("$e".Trim()) { Write-Host "  [remote stderr] $e" -ForegroundColor DarkGray }
    }
    return [pscustomobject]@{
        ExitCode = $code
        Output   = (($stdout | Where-Object { $_ -match '\S' }) -join "`n")
    }
}

function Invoke-Remote([string]$cmd) {
    $r = Invoke-Plink $cmd
    if ($r.ExitCode -ne 0) { throw "Remote command failed (exit $($r.ExitCode)): $cmd" }
    return $r.Output
}

function Step([string]$msg) { Write-Host $msg -ForegroundColor Cyan }

# ------------------------------------------------------------
# 0. 凭据与工具检查（缺密码立刻失败，不浪费一次远程部署）
# ------------------------------------------------------------
Step "[0/5] 检查工具"
if ([string]::IsNullOrWhiteSpace($Password)) {
    throw "未提供部署密码。请设置环境变量 SNHGN_DEPLOY_PASSWORD（推荐），或通过 -Password 参数显式传入。"
}
if ($Password.Contains("'")) {
    # 密码会作为第 4 参数拼进远端 bash 命令串（单引号包裹），含单引号会破坏命令
    throw "部署密码不能包含单引号（会被拼进远端命令串导致语法错误）。"
}
foreach ($tool in @($PLINK, $PSCP)) {
    if (-not (Test-Path $tool)) { throw "Not found: $tool (install PuTTY first)" }
}

# ------------------------------------------------------------
# 1. 定位并构建载荷
# ------------------------------------------------------------
if (-not $SourceDir) { $SourceDir = Join-Path $RepoRoot "web\dist" }
if (-not (Test-Path $SourceDir)) { throw "Source directory not found: $SourceDir" }

if (-not $SkipBuild) {
    Step "[1/5] 构建前端 (npm run build)"
    Push-Location (Join-Path $RepoRoot "web")
    try {
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
    } finally { Pop-Location }
} else {
    Step "[1/5] 跳过构建，使用现有产物 (-SkipBuild)"
}

# ------------------------------------------------------------
# 2. 本地载荷自检：缺东西就别浪费一次远程部署
# ------------------------------------------------------------
Step "[2/5] 本地载荷自检: $SourceDir"
$files = Get-ChildItem $SourceDir -Recurse -File
Write-Host "  文件数: $($files.Count)"
if ($files.Count -lt 50) {
    throw "载荷只有 $($files.Count) 个文件，明显不完整。构建可能没成功，请先检查。"
}
foreach ($required in @("index.html", "sw.js", "schedule-app.apk", "assets")) {
    $p = Join-Path $SourceDir $required
    if (-not (Test-Path $p)) { throw "载荷缺少: $required" }
    if ((Test-Path $p -PathType Leaf) -and (Get-Item $p).Length -eq 0) {
        throw "载荷存在但为空: $required"
    }
}
# APK 必须是新构建的：历史事故里 dist 里长期躺着一个旧包，
# 每次 build 都会把它带上去，导致线上 APK 静默回退。
$apk = Get-Item (Join-Path $SourceDir "schedule-app.apk")
Write-Host "  schedule-app.apk: $([math]::Round($apk.Length/1MB,2)) MB, 修改于 $($apk.LastWriteTime)"
if ($apk.LastWriteTime -lt (Get-Date).AddDays(-30)) {
    Write-Warning "  ! APK 已超过 30 天未更新，确认 web\public\schedule-app.apk 是否忘了同步新构建"
}

# ------------------------------------------------------------
# 3. 上传到唯一暂存目录
#    唯一化是为了避免并发部署互相覆盖，也让脚本可以安全地
#    只读暂存、绝不删除它
# ------------------------------------------------------------
$TS  = Get-Date -Format "yyyyMMdd-HHmmss"
$Stage = "/tmp/webdeploy-$TS"

Step "[3/5] 上传到 $Stage"
Invoke-Remote "rm -rf $Stage; mkdir -p $Stage"
# pscp 的 -r 不会自动创建目标目录，目录必须先建好（上面已建）
& $PSCP -batch -pw $Password -hostkey $HostKey -r "$SourceDir\*" "${User}@${Server}:${Stage}/"
if ($LASTEXITCODE -ne 0) { throw "pscp upload failed" }
& $PSCP -batch -pw $Password -hostkey $HostKey "$PSScriptRoot\deploy-web.sh" "${User}@${Server}:/tmp/deploy-web.sh"
if ($LASTEXITCODE -ne 0) { throw "pscp upload deploy-web.sh failed" }
$stageCount = Invoke-Remote "find $Stage -type f | wc -l"
Write-Host "  服务器端计数: $stageCount"

# ------------------------------------------------------------
# 4. 服务器侧替换 + 验证（脚本自带断言、备份、自动回滚）
# ------------------------------------------------------------
Step "[4/5] 服务器侧替换并验证"
# 走 Invoke-Plink：远端 stderr（sudo 的密码提示）落盘后作为信息打印，
# 不会再被升级成终止性错误；退出码照常捕获，失败仍会走下面的回滚提示。
# 密码作为第 4 个参数传给 deploy-web.sh，由它用 `echo "$PW" | sudo -S` 消费，
# 不走 plink 的 stdin —— 那个管道只用来跳过 banner。
$r = Invoke-Plink "bash /tmp/deploy-web.sh '$Stage' '/opt/website' '/opt/snhgn/backups' '$Password'"
$rc = $r.ExitCode

# 清理暂存（部署脚本自身从不删它，这里收尾）
Invoke-Remote "rm -rf $Stage /tmp/deploy-web.sh"

# ------------------------------------------------------------
# 5. 结果
# ------------------------------------------------------------
if ($rc -ne 0) {
    Write-Host ""
    Write-Host "部署未成功（已自动回滚，线上保持部署前状态）。" -ForegroundColor Red
    Write-Host "查备份: ssh ${User}@${Server} 'ls -dt /opt/snhgn/backups/website-* | head -3'" -ForegroundColor DarkGray
    exit $rc
}

Step "[5/5] 完成"
Write-Host "Deploy finished successfully! Access at: https://snhgn.me" -ForegroundColor Green
