# 定时任务配置

本系统每天 09:00（北京时间）运行一次。以下提供 Windows 与 Linux 两种方案。

> 注意：Windows 任务计划程序默认使用**本地时间**。若你的系统时区是北京时间，09:00 即北京 09:00；若不是，需换算（系统时区 = 北京时间 + 8 小时，即 01:00 UTC）。

---

## 一、Windows 任务计划程序（推荐）

### 1. 创建脚本文件（可选但推荐）

新建 `run_monitor.bat`（放在项目目录，与 main.py 同级）：

```bat
@echo off
rem Notice monitor scheduled task entry
rem Logs are written by main.py FileHandler to notice_monitor.log
cd /d D:\ai_notice_monitor
py main.py
```

说明：用 `py` 而非 `python`（Windows 下 `python` 命令可能未加入 PATH）。不要用 `>>` 重定向日志（会与 Python 内部 FileHandler 冲突，Windows 文件锁）。bat 内**不要写中文注释**（bat 默认按 GBK 解析中文，可能导致整行命令被破坏）。

### 2. 注册任务（以管理员身份打开 PowerShell）

```powershell
# 创建每天 09:00 触发的计划任务
$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument '/c "D:\ai_notice_monitor\run_monitor.bat"'
$trigger = New-ScheduledTaskTrigger -Daily -At 09:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "BJFUCosNoticeMonitor" -Action $action -Trigger $trigger -Settings $settings -Description "北林理学院通知监控，每天09:00" -Force
```

> 若提示权限不足，请以**管理员身份**运行 PowerShell 再执行。
> 若希望"错过运行时间则补跑"（如电脑关机未触发），将 `$settings` 改为：
> `$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)`

### 3. 手动触发测试

```powershell
Start-ScheduledTask -TaskName "BJFUCosNoticeMonitor"
Get-ScheduledTask -TaskName "BJFUCosNoticeMonitor" | Get-ScheduledTaskInfo  # 查看上次运行时间/结果
```

### 4. 查看运行结果

- 运行结果：`0` 表示成功（任务计划程序界面"上次运行结果"）
- 程序日志：`D:\ai_notice_monitor\notice_monitor.log`

### 5. 删除任务（如需）

```powershell
Unregister-ScheduledTask -TaskName "BJFUCosNoticeMonitor" -Confirm:$false
```

---

## 二、Linux cron 方案

### 1. 编辑 crontab

```bash
crontab -e
```

### 2. 加入以下行（每天 09:00 北京时间）

```cron
# 假设服务器时区是 Asia/Shanghai
0 9 * * * cd /path/to/ai_notice_monitor && /usr/bin/python3 main.py >> notice_monitor.log 2>&1
```

若服务器是 UTC 时区，换算为：

```cron
0 1 * * * cd /path/to/ai_notice_monitor && /usr/bin/python3 main.py >> notice_monitor.log 2>&1
```

### 3. 确认时区

```bash
date  # 查看当前时区
```

### 4. 查看运行日志

```bash
tail -f /path/to/ai_notice_monitor/notice_monitor.log
```

---

## 三、常见问题

| 问题 | 排查 |
|------|------|
| 任务计划运行结果非 0 | 打开 `notice_monitor.log` 看具体报错；先用 `py main.py` 手动跑一遍 |
| 时间不对 | 检查系统时区是否是北京时间 |
| 电脑关机没跑 | 设置任务时勾选"如果错过计划启动时间则立即启动任务"（StartWhenAvailable） |
