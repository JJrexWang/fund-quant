# 基金量化分析系统 v1（财富中心）
B/S + Docker Compose 部署。服务: gateway(nginx, 18082) / api(FastAPI) / worker(定时任务) / db(PostgreSQL)。
- 定时: 工作日 17:40 市场状态判定 · 21:35 跟踪净值更新(触发5%达标提醒) · 周六 09:30 申万行业 · 周一 08:30 自动筛选
- 数据源(免费): AkShare 主源 + 东方财富直连(净值/指数) + BaoStock 预留校验; 原始口径见《数据来源说明-免费方案》
- 升级: 改代码后在飞牛 Compose 项目里重新构建 api/worker 即可; 数据在 ./data（SQLite 数据文件 fundquant.db）
