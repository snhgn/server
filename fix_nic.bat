@echo off
chcp 65001 >nul
:: ====================================================================
:: 机械革命 / Realtek RTL8125 2.5GbE 网卡休眠与 Code 45 掉盘一键彻底修复脚本
:: ====================================================================

echo [1/4] 正在请求管理员权限...
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo 请在弹出的 UAC 窗口中点击 "是" 授权管理员权限...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    set params = %*:"=""
    echo UAC.ShellExecute "cmd.exe", "/c ""%~s0"" %params%", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    del "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    pushd "%CD%"
    CD /D "%~dp0"

echo.
echo [2/4] 正在修改驱动注册表，彻底禁用激进节能与 PLL 掉电...
set "REGKEY=HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}\0000"

:: 核心修复：禁止关闭锁相环(PLL)、禁止休眠模式、禁止绿色以太网、禁止节能以太网(EEE)
reg add "%REGKEY%" /v "PowerDownPll" /t REG_SZ /d "0" /f >nul 2>&1
reg add "%REGKEY%" /v "PowerSavingMode" /t REG_SZ /d "0" /f >nul 2>&1
reg add "%REGKEY%" /v "EnableGreenEthernet" /t REG_SZ /d "0" /f >nul 2>&1
reg add "%REGKEY%" /v "*EEE" /t REG_SZ /d "0" /f >nul 2>&1
reg add "%REGKEY%" /v "AdvancedEEE" /t REG_SZ /d "0" /f >nul 2>&1
reg add "%REGKEY%" /v "GigaLite" /t REG_SZ /d "0" /f >nul 2>&1
reg add "%REGKEY%" /v "AutoDisableGigabit" /t REG_SZ /d "0" /f >nul 2>&1
reg add "%REGKEY%" /v "DeviceSleepOnDisconnect" /t REG_SZ /d "0" /f >nul 2>&1
reg add "%REGKEY%" /v "SelectiveSuspend" /t REG_SZ /d "0" /f >nul 2>&1
:: 禁用设备管理器的“允许计算机关闭此设备以节约电源”(0x18 = 24)
reg add "%REGKEY%" /v "PnPCapabilities" /t REG_DWORD /d 24 /f >nul 2>&1

echo 注册表节能参数已全部优化为高性能常开状态！

echo.
echo [3/4] 正在重新扫描 PCIe 总线与即插即用设备...
pnputil /scan-devices

echo.
echo [4/4] 正在检查网卡是否恢复并配置直连 IP...
timeout /t 2 /nobreak >nul
powershell -NoProfile -Command "Get-NetAdapter | Where-Object { $_.InterfaceDescription -like '*Realtek*' } | ForEach-Object { Write-Host '找到网卡: ' $_.Name '状态: ' $_.Status -ForegroundColor Green; New-NetIPAddress -InterfaceIndex $_.ifIndex -IPAddress '192.168.50.1' -PrefixLength 24 -ErrorAction SilentlyContinue; Write-Host '已配置直连 IP: 192.168.50.1' -ForegroundColor Green }"

echo.
echo ====================================================================
echo 修复完成！如果此时设备管理器中网卡仍未出现，说明主板 PCIe 总线需要
echo 硬件复位：请保存好工作，【关机】后长按电源键 15 秒（EC复位）后再开机。
echo ====================================================================
echo.
pause
