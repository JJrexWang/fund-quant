---
name: fund-quant-cli
description: "通过 fundq CLI 调用银行财富中心「基金量化分析系统」的数据与分析: 销售跟踪与收益、达标提醒、代销池与筛选结果、基金详情指标、申万行业与市场状态。当用户提到查基金跟踪/收益达标/代销筛选/某只基金的夏普回撤/行业走势, 且环境里配置了 FUNDQ_API_KEY 时使用。"
---

# 基金量化系统 Agent 接入（fundq CLI）

本系统是银行财富中心的内部研究与销售辅助工具（不承诺收益，结论供内部参考）。
外部 Agent 通过单文件 CLI `fundq.py`（Python 标准库、零依赖）以 API Key 调用。

## 准备

1. CLI 位置：本 skill 目录 `scripts/fundq.py`（仓库内为 `tools/fundq.py`）。
2. 环境变量：
   - `FUNDQ_URL`：服务地址，默认 `http://192.168.99.4:18082`（局域网）。
   - `FUNDQ_API_KEY`：密钥在系统管理后台「Agent 接入」页由 admin 生成（`fqk_` 开头）。没有就向用户索取，不要猜、不要把密钥写进任何文件或回复里明文回显（只可引用前 12 位前缀辨认）。
3. 先跑 `python3 fundq.py me` 确认密钥有效与权限档位（scopes: read / write）。

## 命令速查

只读（read 档即可）：
- `fundq.py dashboard` — 汇总：跟踪数、达标数、市场状态、行业 TOP/BOTTOM、最近任务
- `fundq.py watch list` — 销售跟踪：代码/名称/销售日净值/最新净值/收益率/状态(tracking/hit/warn_down)
- `fundq.py alerts [--limit N]` — 达标提醒（收益率≥目标触发），含 contacted 是否已联系
- `fundq.py pool list` — 代销池
- `fundq.py screen runs` / `fundq.py screen results <run_id>` — 筛选轮次与结果（综合分=业绩持续性30%+风险调整25%+回撤控制20%+动量15%+长期10%，随市场状态调权；risk_tag 带「谨慎推荐」即回撤超门槛）
- `fundq.py fund <6位代码>` — 基金详情：最新净值、区间收益、夏普/卡玛/最大回撤、近30日净值序列
- `fundq.py industry` — 申万一级行业涨幅（系统缓存，周更）
- `fundq.py system status` — 任务日志与数据源说明

写操作（需 write 档）：
- `fundq.py watch add <代码> --date YYYY-MM-DD --nav <销售日净值> [--target 5] [--manager 名] [--note 备注]`
- `fundq.py watch rm <id>` / `fundq.py watch refresh`（刷新全部净值并触发达标判定）
- `fundq.py alerts-contacted <id>` — 标记已联系客户
- `fundq.py pool add <代码...>` / `fundq.py pool import <csv|xlsx>` / `fundq.py pool rm <id>`
- `fundq.py screen run [--regime 进攻|均衡|防御]` — 后台执行，用 `screen runs` 轮询状态
- `fundq.py system run-job watch_update|market_regime|industry_sw`

不可用（仅网页 admin）：发布建议名单、账号管理、密钥管理。遇到 403 先看是不是档位不够，不要反复重试。

## 输出与口径

- 输出统一 JSON；HTTP 错误打到 stderr 且退出码 3，参数/配置错误退出码 2。
- 收益率、夏普等指标以系统返回为准，不要自行重算或外推；引用数据时注明「截至」日期（字段 latest_date / 行业 updated）。
- 数据源为免费公开数据（AkShare/东方财富），无 SLA：返回为空或时间过旧时如实说明，不要用别的数据冒充系统数据。
