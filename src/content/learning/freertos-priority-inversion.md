---
title: "FreeRTOS queues & tasks — 优先级反转踩坑"
date: 2026-06-28
tags:
  - "freertos"
  - "rtos"
  - "embedded"
summary: "FreeRTOS 任务优先级反转问题与优先级继承 mutex 的使用。"
problems:
  - "高优先级任务被低优先级任务长时间阻塞。"
  - "使用普通 mutex 导致系统响应不稳定。"
solutions:
  - "改用带优先级继承的 mutex(xSemaphoreCreateMutex)。"
  - "临界区尽量短,避免长时间持锁。"
next_steps:
  - "研究 FreeRTOS 任务通知(task notification)替代队列。"
  - "学习时间片轮转与协作式调度的区别。"
---

## 学习内容

在智能运输小车项目中,三个 FreeRTOS 任务:

- **Task A(高)**:PID 控制,1ms 周期
- **Task B(中)**:传感器读取,10ms 周期
- **Task C(低)**:LCD 显示,100ms 周期

## 遇到的问题

Task A 偶发性延迟,导致 PID 控制周期不稳。用逻辑分析仪抓取发现,Task A 会被 Task C 阻塞长达 5ms。

## 原因分析

**优先级反转**:

1. Task C 获取了共享资源(串口)的锁
2. Task A 抢占 Task C,但要获取同一把锁 → 阻塞
3. Task B 抢占 Task C(因为 C 持锁不能释放)
4. 结果:高优先级 A 被低优先级 C 间接阻塞

## 解决方法

```c
// 错误:二值信号量,无优先级继承
SemaphoreHandle_t lock = xSemaphoreCreateBinary();

// 正确:互斥量,带优先级继承
SemaphoreHandle_t lock = xSemaphoreCreateMutex();
```

`xSemaphoreCreateMutex()` 创建的 mutex 会自动执行优先级继承:当高优先级任务等待锁时,持锁的低优先级任务会被临时提升到相同优先级。

## 总结

实时系统的核心不是"跑得快",而是"可预测"。优先级反转是 RTOS 最经典的坑,理解它才能真正理解实时调度。
