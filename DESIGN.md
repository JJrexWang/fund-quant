# fund-quant 设计规范（v2 · 2026-11-13 用户指定）

风格与布局由用户 2026-11-13 指定，来源 StyleKit：
- 风格：macOS Vibrancy（暗色毛玻璃）https://www.stylekit.top/zh/styles/macos-vibrancy
- 布局：Fixed Sidebar（固定侧边栏）https://www.stylekit.top/zh/styles/sidebar-fixed
- 图标：金毛猎犬大头（design/icon-source.webp 为源图，前端派生 favicon.ico / favicon-32.png / apple-touch-icon.png / icons/brand.png 等）

## 令牌（Vibrancy）
- 三层深灰：--deepest #1c1c1e（页面底/侧边栏基色）、--mid #2c2c2e（内容面板）、--light #3a3a3c（工具栏/次级按钮）
- 通透层：rgba(28,28,30,.8) + backdrop-blur 40px（侧边栏/登录卡）；工具栏 rgba(58,58,60,.92) + blur 20px
- 系统色：蓝 #0a84ff、绿 #30d158、橙 #ff9f0a、红 #ff453a（全站仅此四色做强调）
- 文字：rgba(255,255,255,.92) / .62 / .4 三档；分隔线一律 1px 白 8%–12%，不加粗
- 无渐变、无发光；阴影仅浮层使用（面板 0 20px 48px rgba(0,0,0,.5) + 内顶 1px 白 8%）
- 字体：标题衬线 Georgia/'New York'/'Songti SC'/'STSong'（页面大标题、顶栏居中标题、弹窗标题、品牌名）；正文 SF Pro Text/PingFang；数值 SF Mono/ui-monospace
- 字级：页面标题 32/400 衬线、正文 13.5、标签 11、行高 44px（桌面密度）
- 圆角：卡片 10、按钮 6、输入 6、面板 14、胶囊 999；不得超过 14（胶囊除外）
- 动效：200ms ease-out、只改颜色（含 filter brightness），不位移不缩放（抽屉/收起为布局功能除外）
- A 股惯例：红涨绿跌 → 涨用系统红 #ff453a、跌用系统绿 #30d158

## 布局（Fixed Sidebar）
- 侧边栏 fixed 256px（布局规范统一宽 w-64，上限 280；Vibrancy 原规范 240，本项目从布局规范取 256），主区 margin-left 等宽、独立滚动
- 侧边栏结构：品牌（狗头图标+衬线名）→ 分组标签 → 导航（可滚）→ 底部用户区（头像/用户名/改密/退出/合规注脚）
- 当前页高亮：系统蓝 18% 底 + 左侧 3px 蓝色锚点线
- 桌面收起：顶栏 ☰ 切换 68px 图标栏（body.sb-collapsed，带 title 提示）
- 移动端 <1024px：侧边栏变抽屉（body.sb-open）+ 半透明遮罩，主区全宽；顶栏居中标题与红绿黄点隐藏
- 顶栏（Vibrancy Toolbar）：高 52px、#3a3a3c、左红黄绿 12px 圆点、标题衬线居中、右侧市场状态/日期/搜索/提醒铃
- 内容最大宽 1280px 居中

## 组件要点
- 按钮：系统蓝填充主按钮 6px 圆角 13px/500；次级按钮 #3a3a3c + 1px 白 10%；hover 仅亮度 +12%、active −8%；禁用白 12% 底 + 40% 文字
- 输入：白 6% 填充、1px 白 10%、focus 蓝边 + 3px rgba(10,132,255,.3) 光环
- 表格：行分隔 1px 白 8%，hover 白 4%，达标行红 14% 底
- ECharts 暗色：轴标签 rgba(255,255,255,.55)、网格 rgba(255,255,255,.06)、tooltip #3a3a3c 底；净值线系统蓝、回撤线系统橙、行业条涨红跌绿
