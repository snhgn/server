---
title: "理解 systemd 依赖图与启动顺序"
date: 2026-07-12
tags:
  - "linux"
  - "systemd"
summary: "梳理 systemd 的 Wants/Requires/After/Before 语义。"
problems:
  - "服务启动顺序不确定,导致依赖服务未就绪。"
  - "Wants 和 Requires 的区别模糊。"
solutions:
  - "用 After= 明确顺序,Wants= 表达软依赖。"
  - "Requires= 是硬依赖,被依赖服务失败则本服务也失败。"
next_steps:
  - "学习 systemd timer 替代 cron。"
  - "研究 socket activation 机制。"
---

## 学习内容

systemd 的依赖关系分两层:

1. **依赖关系(Wants/Requires)**:决定"要不要启动"
2. **顺序关系(After/Before)**:决定"什么时候启动"

## 关键概念

- `Wants=`:软依赖,即使被依赖服务失败,本服务仍启动
- `Requires=`:硬依赖,被依赖服务失败则本服务也失败
- `After=`:本服务在被依赖服务之后启动
- `Before=`:本服务在被依赖服务之前启动

:::warning
Requires= 只表达依赖,不表达顺序。如果需要顺序,必须同时写 Requires= 和 After=。
:::

## 实战示例

```ini
[Unit]
Description=My Web App
Requires=network-online.target
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/app/main.py
```

## 总结

systemd 的依赖模型比传统 init 脚本清晰得多,但语义容易混淆。关键是区分"依赖"和"顺序"两个维度。
