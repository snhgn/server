---
title: "Smart Transport Cart"
date: 2026-07-01
status: "shipped"
year: 2026
tech:
  - "STM32"
  - "FreeRTOS"
  - "C"
  - "PID"
github: "https://github.com/snhgn/smart-cart"
demo: ""
featured: true
order: 1
description: "A line-following + obstacle-avoiding cart for the 2026 Beijing Engineering Training Competition."
lessons:
  - "PID 调参先 P 后 I 后 D,大振荡减 P,稳态误差加 I。"
  - "FreeRTOS 任务优先级反转要用优先级继承 mutex。"
  - "超声波传感器多探头交替触发,避免串扰。"
---

## 项目背景

2026 北京市工程训练竞赛智能运输小车项目。要求在指定赛道上完成循迹、避障、定点运输。

## 技术方案

### 硬件

- **主控**:STM32F103C8T6
- **循迹**:TCRT5000 红外模块 ×5(数字量)
- **避障**:HC-SR04 超声波 ×3(前/左/右)
- **驱动**:L298N + TT 电机 ×2
- **电源**:18650 锂电池组 7.4V

### 软件架构

FreeRTOS 三任务模型:

```c
// PID 核心循环
void pid_update(PID_t *pid, float error) {
    pid->integral += error;
    pid->derivative = error - pid->prev_error;
    pid->output = pid->kp * error
                + pid->ki * pid->integral
                + pid->kd * pid->derivative;
    pid->prev_error = error;
}
```

:::note
实际调试时发现,积分项需要限幅,否则小车在起步时会因积分饱和而冲出赛道。
:::

## 开发过程

1. 原型搭建(面包板验证传感器)
2. PCB 打样(双层板,手工焊接)
3. 固件开发(FreeRTOS + HAL 库)
4. 现场调试(PID 参数整定)

## 总结

竞赛成绩超出预期。最大的收获不是名次,而是对实时系统的理解 — 任务调度、优先级、临界区,这些概念只有动手实现才真正懂。
