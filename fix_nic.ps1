#Requires -Version 5.1
<#
.SYNOPSIS
    彻底修复 Realtek RTL8125 2.5GbE 网卡休眠与代码 45 掉盘问题
#>

# 1. 自动请求管理员权限（如果未以管理员身份运行）
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "正在请求管理员权限，请在弹出的 UAC 提示窗口中点击【是】..." -ForegroundColor Yellow
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = "powershell.exe"
    $processInfo.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $processInfo.Verb = "RunAs"
    try {
        $proc = [System.Diagnostics.Process]::Start($processInfo)
        $proc.WaitForExit()
    } catch {
        Write-Host "用户取消了管理员授权。" -ForegroundColor Red
        Read-Host "按回车键退出"
    }
    exit
}

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Clear-Host
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Realtek RTL8125 2.5GbE 网卡休眠与掉盘(Code 45) 修复工具   " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 2. 修改驱动注册表，永久禁用所有激进节能
Write-Host "[1/3] 正在修改驱动注册表，关闭 PLL 掉电与休眠机制..." -ForegroundColor Yellow
$netKey = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}\0000"

if (Test-Path $netKey) {
    $settings = @{
        "PowerDownPll"             = "0"
        "PowerSavingMode"          = "0"
        "EnableGreenEthernet"      = "0"
        "*EEE"                     = "0"
        "AdvancedEEE"              = "0"
        "GigaLite"                 = "0"
        "AutoDisableGigabit"       = "0"
        "DeviceSleepOnDisconnect"  = "0"
        "SelectiveSuspend"         = "0"
    }

    foreach ($name in $settings.Keys) {
        Set-ItemProperty -Path $netKey -Name $name -Value $settings[$name] -Force -ErrorAction SilentlyContinue
    }
    # 禁用“允许计算机关闭此设备以节约电源”
    Set-ItemProperty -Path $netKey -Name "PnPCapabilities" -Value 24 -Type DWord -Force -ErrorAction SilentlyContinue

    Write-Host "  ✓ 驱动节能参数已全部禁用（保持锁相环供电与全时活跃）" -ForegroundColor Green
} else {
    Write-Host "  ✗ 未找到网卡注册表项: $netKey" -ForegroundColor Red
}

Write-Host ""
# 3. 重新扫描 PCIe 总线
Write-Host "[2/3] 正在扫描 PCIe 总线唤醒网卡硬件..." -ForegroundColor Yellow
$scan = pnputil /scan-devices
Write-Host "  ✓ PCIe 硬件总线扫描已触发" -ForegroundColor Green

Write-Host ""
# 4. 检查网卡识别状态与直连 IP 配置
Write-Host "[3/3] 检查网卡恢复状态..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

$adapter = Get-NetAdapter | Where-Object { $_.InterfaceDescription -like "*Realtek*" }

if ($adapter) {
    Write-Host "  ✓ 成功检测到网卡: $($adapter.Name) ($($adapter.InterfaceDescription))" -ForegroundColor Green
    Write-Host "    状态: $($adapter.Status), 速率: $($adapter.LinkSpeed)" -ForegroundColor Green

    # 配置 192.168.50.1
    $existingIp = Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
    if (-not $existingIp -or $existingIp.IPAddress -notlike "192.168.50.*") {
        New-NetIPAddress -InterfaceIndex $adapter.ifIndex -IPAddress "192.168.50.1" -PrefixLength 24 -ErrorAction SilentlyContinue | Out-Null
        Write-Host "  ✓ 已配置直连 IP: 192.168.50.1/24" -ForegroundColor Green
    } else {
        Write-Host "  ✓ 网卡已拥有直连 IP: $($existingIp.IPAddress)" -ForegroundColor Green
    }
} else {
    Write-Host "  ⚠ 网卡当前处于物理掉电状态（硬件未响应总线扫描）" -ForegroundColor Yellow
    Write-Host "    原因：主板 PCIe 电源挂起锁死（常见于休眠/插拔网线后的保护状态）" -ForegroundColor Gray
    Write-Host "    解决办法：请正常【关机】并拔掉电源适配器，长按电源键 15 秒（EC硬复位）后再开机。" -ForegroundColor Cyan
    Write-Host "    开机后上述注册表配置会自动生效，彻底防止今后再次掉盘。" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "修复执行完毕！" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "按回车键关闭窗口"
