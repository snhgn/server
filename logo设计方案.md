一、 品牌 Logo 系统 (Brand Logo System)1. 独立图形 Logo (Symbol / Icon)设计理念与几何构造将字母 h 作为视觉中心拆解。h 的结构包含一条竖线（探索的方向/轴线）与一个向下延伸的拱形（节点的连接）。结构由三部分极简几何元素构成：纵向主轴 (Vertical Axis)：一条极其纤细的垂直线，代表坐标轴、生长方向与持续探索。中心节点 (Central Node)：在 h 的交汇处放一个正圆形实心点 $\bullet$，代表坐标原点、当前关注的研究节点。横向探索弧线 (Horizontal Arc)：一个向右下弧形发散的微小圆弧，与中心点相切，形成类似坐标映射、引力轨道或无线数据节点相连的抽象视觉。拒绝雷区：无任何芯片脚、电路走线、机器人轮廓或医疗十字感。它纯粹是一个抽象的数学与空间坐标系统。       │
   ────●───╮  <-- 低饱和灰蓝 Accent (#7C96A8)
       │   │
       │   ↓
2. Wordmark 文字 Logo全小写无衬线设计，采用高字宽与极宽的字间距（Letter Spacing: 0.35em），搭配结尾的句号（表示独立、确定与沉淀）。s  n  h  g  n  .
      ↑
  #7C96A8 (低饱和灰蓝)
s, n, g, n, . ：采用 #111111（深碳黑），字重 Font-Weight: 400 (Regular)。h ：单独填充低饱和灰蓝 #7C96A8，字重略调为 Font-Weight: 500 (Medium)，在视觉中心形成自然聚焦。3. Favicon & 社交头像 (Icon Design)Favicon (32x32px / 16x16px)：纯白背景下的 #111111 深色中心点与 #7C96A8 极细交叉坐标线，在极小尺寸下依然具备高辨识度。GitHub / 社交头像 (400x400px)：背景：#FAFAFA图形：居中放置 Symbol，四周保留 35% 以上的留白空间（White Space）。二、 视觉规范 (Style Guide)1. 色彩系统 (Color Palette)[ Light Mode ]
■ Primary Background   : #FAFAFA (极淡烟灰白)
■ Surface / Cards      : #FFFFFF (纯白，带有 80% 半透明 + 12px Blur)
■ Primary Text         : #111111 (深碳黑)
■ Secondary Text       : #777777 (中性灰)
■ Border / Line        : #E5E5E5 (极淡灰)
■ Accent Color         : #7C96A8 (低饱和灰蓝 - 静谧科技感)

[ Dark Mode ]
■ Primary Background   : #121416 (深邃灰黑，非纯黑)
■ Surface / Cards      : #1A1D20 (带有 80% 半透明 + 12px Blur)
■ Primary Text         : #F0F0F0 (柔和白)
■ Secondary Text       : #888888 (冷灰)
■ Border / Line        : #2A2E33 (深灰边框)
■ Accent Color         : #94ACC0 (略微提亮的低饱和灰蓝)
2. 字体系统 (Typography)English / Numbers：Inter, -apple-system, Helvetica NeueChinese：Noto Sans SC, PingFang SCCode / Mathematical Specs：JetBrains Mono三、 Desktop 网站首页 UI 设计稿 (Homepage Mockup)以下为 Desktop 视图（1440px 宽度）的 CSS/HTML 结构化渲染描述与视效组合：1. Navigation Bar (顶部导航)+-------------------------------------------------------------------------------------------------------------------+
|  [●] s n h g n .            Home    Projects    Notes    Research    About             [🔍]  [🌙/☀️]          |
+-------------------------------------------------------------------------------------------------------------------+
Layout：固定顶部 position: fixed, 高度 72px，全宽。Visual：背景色 rgba(250, 250, 250, 0.75)，搭配 backdrop-filter: blur(16px)。底部带有 1px 极淡边框 border-bottom: 1px solid rgba(0,0,0,0.05)。Typography：导航项字号 14px，颜色 #777777，Hover 时变为 #111111 并附带 2px 灰蓝色小圆点指示器。2. Hero Section (第一屏)画面中央不再是复杂的 3D 粒子或代码库，而是一幅高广角、沉静的极简自然意象。+-------------------------------------------------------------------------------------------------------------------+
|                                                                                                                   |
|                                                     │                                                             |
|                                                 ───●───                                                           |
|                                                     │                                                             |
|                                                                                                                   |
|                                             s  n  h  g  n  .                                                      |
|                                                                                                                   |
|                                       Stay curious, keep building.                                                |
|                                                                                                                   |
|                                                  ┌───┐                                                            |
|                                                  │ ↓ │  (Scroll Down)                                             |
|                                                  └───┘                                                            |
+-------------------------------------------------------------------------------------------------------------------+
背景视觉 (Background Canvas)：动态/静态高质感纹理：远山在淡雾（Mist/Fog）中隐现，平整如镜的湖面，大面积柔和的淡灰色渐变。画面整体色调为哑光灰、灰蓝与奶白，传达“独自在天地与未知中探索”的专注感。Central Visual：居中放大的 Symbol 图形（尺寸 64x64px）。下方居中 Wordmark：s n h g n .（字号 32px，letter-spacing: 0.3em）。Slogan：Stay curious, keep building.（字号 14px，Inter 字体，字重 400 Regular，颜色 #777777，letter-spacing: 0.04em，与品牌名称自然呼应，留白克制）。3. Four Entry Cards (入口卡片区)Hero 下方自然过渡至四个核心模块卡片，采用 2x2 或 1x4 网格布局（Grid Layout）。+-------------------+  +-------------------+  +-------------------+  +-------------------+
| 01                |  | 02                |  | 03                |  | 04                |
| Projects          |  | Notes             |  | Research          |  | About             |
| 项目与实验         |  | 学习笔记与思考     |  | 研究方向与探索     |  | 关于我            |
|                   |  |                   |  |                   |  |                   |
| 嵌入式/机器人/硬件  |  | 论文解读/架构心得  |  | 半导体/AI 前沿     |  | 个人经历与 Contact|
|                   |  |                   |  |                   |  |                   |
|              [➔]  |  |              [➔]  |  |              [➔]  |  |              [➔]  |
+-------------------+  +-------------------+  +-------------------+  +-------------------+
卡片 Visual StyleBackground：#FFFFFF（在 Dark Mode 下为 #1A1D20），透明度 80%。Border：1px solid rgba(0, 0, 0, 0.06)，微弱圆角 border-radius: 12px。Shadow：柔和弥散阴影 box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03)。Interaction (Hover)：鼠标悬停时，卡片整体上移 4px (transform: translateY(-4px))。边框颜色平滑过渡至灰蓝色 #7C96A8。右下角的箭头 [➔] 从 #777777 变为 #7C96A8 并向右上微偏移。四、 双模式界面代码及配色比对 (Light & Dark Mode Visual UI)为了直观呈现该品牌视觉在代码与实操层面的落地效果，以下为网站主排版框架 CSS 代码参考：CSS/* snhgn. Brand Design Tokens */
:root {
  /* Light Mode (Default) */
  --bg-primary: #FAFAFA;
  --surface-card: rgba(255, 255, 255, 0.85);
  --text-main: #111111;
  --text-muted: #777777;
  --border-subtle: rgba(0, 0, 0, 0.06);
  --accent-blue: #7C96A8;
  --font-main: 'Inter', 'Noto Sans SC', sans-serif;
}

[data-theme="dark"] {
  /* Dark Mode */
  --bg-primary: #121416;
  --surface-card: rgba(26, 29, 32, 0.85);
  --text-main: #F0F0F0;
  --text-muted: #888888;
  --border-subtle: rgba(255, 255, 255, 0.08);
  --accent-blue: #94ACC0;
}

/* Global Reset & Quiet Aesthetics */
body {
  background-color: var(--bg-primary);
  color: var(--text-main);
  font-family: var(--font-main);
  transition: background-color 0.4s ease, color 0.4s ease;
}

/* Logo Focus Element */
.logo-wordmark .accent-h {
  color: var(--accent-blue);
  font-weight: 500;
}
设计总结 (Design Summary)整个 snhgn. 品牌视觉系统平衡了学者的严谨与年轻人的灵动：留白（White Space） 为思考提供呼吸感，契合科研探索需要的专注与安静。坐标 Symbol 与灰蓝色 映射出他在嵌入式、AI、机器人与半导体交叉领域的精准定位。“Stay curious, keep building. (保持好奇，持续构建)” 完整表达了一个独立构建者在数字空间中的自我沉淀与持续创造。