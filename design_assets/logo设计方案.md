一、 品牌 Logo 系统 (Brand Logo System)

1. 独立图形 Logo (Symbol / Icon) —— 6 元素轴对称几何坐标系
将 6 个字符构成的品牌系统（左三 `s n h` 与右三 `g n .`）通过轴对称几何在空间上对等映射：
- 纵向主对称轴 (Vertical Symmetry Axis)：一条纤细的垂直线，代表中轴原点与持续向上的探索方向。
- 双翼对等弧线 (Bilateral Wings)：左右两侧各设一条对称圆弧，形成类似引力轨道与双向拓展的平衡张力。
- 6 节点坐标矩阵 (6 Coordinate Nodes)：
  - 左侧 3 节点：对应 `s`、`n`、`h`，采用克制冷灰/主色；
  - 右侧 3 节点：对应 `g`、`n`、`.`，其中第 4 字符 `g` 对应的右侧中心节点赋予【科技琥珀金 (#DE8C16 / #F6BE4F)】作为全系统的视觉破晓点。
- 中心原点 (Center Origin)：在中轴交汇处设立微型原点 $\bullet$，代表坐标基准与思考锚点。

         │
      ╭──●──╮  <-- 左右双翼对等对称
   •  │  │  │  [●] <-- 右侧金色 g 节点 (#DE8C16 / #F6BE4F)
      ╰──●──╯
         │

2. Wordmark 文字 Logo
全小写无衬线设计，采用高字宽与极宽的字间距（Letter Spacing: 0.35em），搭配结尾的句号（表示独立、确定与沉淀）。
`h` 恢复默认主文字色并去除底部下划点，保持纯净；将第 4 字符 `g` 设定为专属高质感科技琥珀金：

   s   n   h   g   n   .
               ↑
       #DE8C16 / #F6BE4F (科技琥珀金)

- `s, n, h, n, .` ：采用 `#111111`（深碳黑）/ Dark Mode `#F0F0F0`，字重 400 (Regular)。
- `g` ：单独填充科技琥珀金 `#DE8C16`（暗色下为 `#F6BE4F`），字重调为 500 (Medium)，在右半段形成精准明亮的视觉定焦点。
- 架构美学：左三字符 `[s n h]` 与右三字符 `[g n .]` 形成 3+3 的对等平衡。

3. Favicon & 社交头像 (Icon Design)
- Favicon (32x32px / 16x16px)：纯白/纯黑底下的轴对称双翼坐标线与金色 `g` 节点。
- GitHub / 社交头像 (400x400px)：背景 #FAFAFA / #121416，居中放置轴对称 6 节点 Symbol，四周保留 35% 留白。

二、 视觉规范 (Style Guide)

1. 色彩系统 (Color Palette)
[ Light Mode ]
■ Primary Background   : #FAFAFA (极淡烟灰白)
■ Surface / Cards      : #FFFFFF (纯白，带有 88% 半透明 + 12px Blur)
■ Primary Text         : #111111 (深碳黑)
■ Secondary Text       : #6B7280 (中性冷灰)
■ Border / Line        : rgba(0, 0, 0, 0.07)
■ Accent Color         : #DE8C16 (科技琥珀金 - 破晓定焦色)

[ Dark Mode ]
■ Primary Background   : #121416 (深邃灰黑，非纯黑)
■ Surface / Cards      : #1A1D20 (带有 88% 半透明 + 12px Blur)
■ Primary Text         : #F0F0F0 (柔和白)
■ Secondary Text       : #949AA1 (冷灰)
■ Border / Line        : rgba(255, 255, 255, 0.08)
■ Accent Color         : #F6BE4F (温润发光金)

2. 字体系统 (Typography)
- English / Numbers：Inter, -apple-system, Helvetica Neue
- Chinese：Noto Sans SC, PingFang SC
- Code / Mathematical Specs：JetBrains Mono

三、 Desktop 网站首页 UI 设计稿 (Homepage Mockup)

1. Navigation Bar (顶部导航)
+-------------------------------------------------------------------------------------------------------------------+
|  s n h g n .                   Home    Projects    Notes    Research    About             [🔍]  [🌙/☀️]          |
+-------------------------------------------------------------------------------------------------------------------+
Layout：固定顶部 position: fixed, 高度 72px，全宽。
Visual：背景色 rgba(250, 250, 250, 0.78)，搭配 backdrop-filter: blur(16px)。
Brand Mark：导航栏左侧采用【纯粹文字 Wordmark】（包含金色 `g`），不贴靠图形 Symbol，保持纯粹克制。

2. Hero Section (第一屏 - 两种分离式视觉层级)

【方案 A：垂直纵深分离 (Vertical Spatial Separation)】
+-------------------------------------------------------------------------------------------------------------------+
|                                                     │                                                             |
|                                                 ╭───●───╮   <-- 轴对称 6 节点 Symbol (双翼平衡)                   |
|                                                 │   │   │                                                         |
|                                                 ╰───●───╯                                                         |
|                                                     │                                                             |
|                                             (72px 宽裕留白空间)                                                    |
|                                       s   n   h   g   n   .  <-- 主品牌名 Wordmark (金色 g 定焦)                  |
|                                         Stay curious, keep building.                                              |
|                                                    ┌───┐                                                          |
|                                                    │ ↓ │  (Explore)                                               |
|                                                    └───┘                                                          |
+-------------------------------------------------------------------------------------------------------------------+
- 核心逻辑：上置 44px 极简轴对称坐标图腾，穿过 72px 留白呼吸带后，品牌名居中定格，形成自上而下的图腾引领感。

【方案 B：背景图腾空间氛围水印化 (Ambient Spatial Watermark)】
+-------------------------------------------------------------------------------------------------------------------+
|                                            . - ~ ~ ~ - .                                                          |
|                                        . '       │       ' .                                                      |
|                                      /       ╭───●───╮       \                                                    |
|                                     |    s n h   g   n .      |  <-- 前景纯品牌名，后方融入 6 节点坐标水印 (5%透明度)  |
|                                      \       ╰───●───╯       /                                                    |
|                                        . '       │       ' .                                                      |
|                                            ' - _ _ _ - '                                                          |
|                                         Stay curious, keep building.                                              |
|                                                    ┌───┐                                                          |
|                                                    │ ↓ │  (Explore)                                               |
|                                                    └───┘                                                          |
+-------------------------------------------------------------------------------------------------------------------+
- 核心逻辑：前景 100% 留给纯粹的品牌签名 `s n h g n .`，没有任何独立前景图标争夺视线；6 节点轴对称几何图形以极低透明度（5%~8%）作为大尺度空间背景水印静置于后方，营造出深邃安静的建筑层次感。

3. Four Entry Spaces (入口工坊矩阵 - 编排式网格)
按照《design-principles.md》原则，拒绝卡片堆砌与厚重阴影，采用极简 1px 细线分隔的编排式网格（Editorial Grid）：
+-------------------+-------------------+-------------------+-------------------+
| 01                | 02                | 03                | 04                |
| Projects          | Notes             | Research          | About             |
| 项目与实验         | 深度笔记与思考     | 研究方向与探索     | 关于我            |
| 嵌入式/机器人/硬件  | 论文解读/架构心得  | 半导体/AI 前沿     | 经历/连接/开源    |
|              [➔]  |              [➔]  |              [➔]  |              [➔]  |
+-------------------+-------------------+-------------------+-------------------+

四、 双模式界面代码及配色 (Light & Dark Mode Visual UI)
```css
:root {
  /* Light Mode (Default) */
  --bg-primary: #FAFAFA;
  --bg-surface: #FFFFFF;
  --text-main: #111111;
  --text-muted: #666666;
  --border-subtle: rgba(0, 0, 0, 0.08);
  --accent-g: #C87A11;
  --font-main: 'Inter', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

[data-theme="dark"] {
  /* Dark Mode */
  --bg-primary: #121416;
  --bg-surface: #181B1E;
  --text-main: #F2F2F2;
  --text-muted: #8E9399;
  --border-subtle: rgba(255, 255, 255, 0.09);
  --accent-g: #F5B738;
```

设计总结 (Design Summary)
整个 snhgn. 品牌视觉系统高度对齐《design-principles.md》：
- 留白（Whitespace as Philosophy）：为思考提供呼吸感，契合科研探索与独立构建的专注与安静。
- 空间解耦（Separation）：图形 Symbol 与品牌 Wordmark 分离呈现（方案 A 垂直纵深 / 方案 B 背景水印），让品牌签名占据绝对第一视觉焦点。
- 6 元素双翼轴对称：在中轴两侧形成完美的 3+3 几何平衡，右侧金色 `g` 成为克制的破晓定焦点。
- 精神主张：“Stay curious, keep building. (保持好奇，持续构建)” 完整表达了一个独立构建者在数字空间中的自我沉淀与持续创造。