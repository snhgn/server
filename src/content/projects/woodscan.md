---
title: "woodscan"
date: 2026-06-15
status: "shipped"
year: 2025
tech:
  - "PyTorch"
  - "EfficientNet"
  - "OpenCV"
  - "Streamlit"
github: "https://github.com/snhgn/woodscan"
demo: ""
featured: true
order: 2
description: "A CNN trained to classify Chinese wood species from cross-section photos. 12 species, 78% top-1 accuracy."
lessons:
  - "小数据集用迁移学习,从头训练根本不收敛。"
  - "数据增强比模型结构调整更有效。"
  - "Streamlit 部署比 Flask 快十倍,适合个人项目。"
---

## 项目背景

林学专业出身,想用 AI 识别木材种类。现有方法依赖显微镜和经验,希望能用手机拍照就识别。

## 技术方案

- **数据集**:12 种中国常见木材,每种 80-150 张横截面照片,共约 1200 张
- **模型**:EfficientNet-B0 迁移学习(ImageNet 预训练)
- **训练**:PyTorch,5-fold 交叉验证
- **部署**:Streamlit Web 界面

## 结果

| 指标 | 值 |
|------|-----|
| Top-1 Accuracy | 78% |
| Top-3 Accuracy | 92% |
| 模型大小 | 20MB(量化后) |

## 总结

作为学习项目,达到了预期。78% 的准确率离生产级还有差距,主要瓶颈是数据量。下一步计划用合成数据增强。
