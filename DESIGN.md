# 设计语言：Apple 风格（HIG 取向）
未找到现成的 Apple 设计 skill，按 Apple Human Interface Guidelines 原则落地以下令牌（tokens），改版只改 style.css 不动结构与配色语义：

- 字体：-apple-system / SF Pro / PingFang SC 栈；大标题 26-32px、字距 -0.02~-0.03em；数字 tabular-nums
- 色板：底 #f5f5f7，卡片 #ffffff，文字 #1d1d1f，次级 #86868b，强调蓝 #0071e3
- 金融语义色（中国市场惯例优先于 Apple 美股惯例）：涨/达标 #e3002b，跌 #00913a
- 形状：卡片圆角 18px、弹窗 22px、按钮胶囊 980px、输入框 10px；阴影 0 4px 24px rgba(0,0,0,.06)
- 材质：侧栏与顶栏毛玻璃（backdrop-filter blur 20-24px + 半透明白）
- 表格：只留横向发丝线、无竖线、行悬停浅灰；标签一律胶囊形
