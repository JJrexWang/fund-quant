---
name: fund-quant-cli
description: "接入银行财富中心「基金量化分析系统」: 销售跟踪与收益、达标提醒、代销池与筛选结果、基金详情指标、申万行业与市场状态。拿到本文件与一把 API Key 即可自助接入, 无需其他资料。当用户要查基金跟踪/收益达标/代销筛选/某只基金的夏普回撤/行业走势时使用。"
---

# 基金量化分析系统 · Agent 自助接入

本系统是银行财富中心的内部研究与销售辅助工具（不承诺收益，结论仅供内部参考）。
你（Agent）通过 API Key 调用它的分析与数据。**接入只需三步，不需要向任何人要更多文档。**

## 地址与双层验证（先看这里）

系统有两个地址，验证层数不同，别用错：

- **局域网地址 `http://192.168.99.4:18082`（Agent 调用用这个）**：只有系统自身的验证，
  带上 API Key 即可直达 API，无其他门槛。
- **外网地址 `https://fund.jjrex.duckdns.org:88`（人用浏览器访问）**：**双层验证**——
  外层是飞牛 fnOS 的 Web 登录验证（门户账号会话），先过这一层才摸到系统；
  内层是系统自己的登录验证（网页账号密码 / API Key）。
  未持有 fnOS 登录会话时，外层会直接拦下请求（返回登录页或 403），**API Key 单独穿不过外层**。
  所以 Agent 不要拿外网地址调 API；在同一局域网/VPN 内时一律用局域网地址。

## 第一步：拿到 API Key

向用户索取一把本系统的 API Key（`fqk_` 开头）。用户在系统管理后台「Agent 接入」页生成（左侧导航 →「Agent 接入」→ 新建密钥）。
密钥分两档：`read` 只读、`write` 含写操作。按任务需要向用户要对应档位；
不要猜密钥、不要把密钥明文写进文件或在回复里回显（引用时只写前 12 位前缀）。

## 第二步：选一种调用方式

### 方式 A：fundq CLI（推荐，单文件零依赖）

```bash
curl -fsSL https://raw.githubusercontent.com/JJrexWang/fund-quant/main/tools/fundq.py -o fundq.py
export FUNDQ_URL=http://192.168.99.4:18082
export FUNDQ_API_KEY=fqk_...        # 第一步拿到的密钥
python3 fundq.py me                 # 自检: 应返回 role=agent 与 scopes
```

（若你所在环境已装有本 skill 且 `scripts/fundq.py` 就在 skill 目录内，直接用那份，不必下载。）

### 方式 B：直接调 HTTP API（无法下载文件时用）

所有接口带请求头 `X-API-Key: <redacted>` Bearer fqk_...`），返回 JSON：

```bash
curl -s http://192.168.99.4:18082/api/me -H "X-API-Key: <key>"
curl -s http://192.168.99.4:18082/api/watch -H "X-API-Key: <key>"
curl -s -X POST http://192.168.99.4:18082/api/watch/update -H "X-API-Key: <key>"   # write 档
```

端点全集（GET 除注明外）：
`/api/me` `/api/dashboard` `/api/watch`（POST 新增 / PUT /api/watch/{id} / DELETE /api/watch/{id} / POST /api/watch/update 刷新净值）
`/api/alerts`（POST /api/alerts/{id}/contacted 标记已联系）
`/api/pool`（POST /api/pool/add {codes:[...]} / POST /api/pool/import 上传 csv|xlsx / DELETE /api/pool/{id}）
`/api/screening/run`（POST）`/api/screening/runs` `/api/screening/runs/{id}/results`
`/api/funds/{6位代码}` `/api/industry` `/api/system/status`（POST /api/system/run-job {job}）
写操作需 write 档；发布名单、账号与密钥的创建/吊销仅限网页 admin，你调不通是正常的，不要反复重试。

## 第三步：自检

`fundq.py me`（或 GET /api/me）返回 `role: "agent"` 与你的 scopes 即接入成功。
401 = 密钥无效/已吊销，找用户重建；403 = 档位不够（如 read 钥做写操作），找用户换 write 钥。

## 命令速查（方式 A）

只读：`dashboard` 汇总 · `watch list` 销售跟踪（收益率/状态 tracking/hit/warn_down）·
`alerts [--limit N]` 达标提醒 · `pool list` 代销池 ·
`screen runs` / `screen results <id>` 筛选（综合分=业绩持续性30%+风险调整25%+回撤控制20%+动量15%+长期10%，随市场状态调权；risk_tag「谨慎推荐」=回撤超门槛）·
`fund <代码>` 基金详情（最新净值/区间收益/夏普/卡玛/最大回撤）· `industry` 申万行业 · `system status`

写（write 档）：`watch add <代码> --date YYYY-MM-DD --nav <销售日净值> [--target 5] [--manager 名] [--note 备注]` ·
`watch rm <id>` · `watch refresh` · `alerts-contacted <id>` ·
`pool add <代码...>` · `pool import <csv|xlsx>` · `pool rm <id>` ·
`screen run [--regime 进攻|均衡|防御]`（后台执行，用 screen runs 轮询）·
`system run-job watch_update|market_regime|industry_sw`

## 数据口径

- 输出统一 JSON；CLI 的 HTTP 错误打到 stderr、退出码 3，参数/配置错误退出码 2。
- 收益率、夏普等以系统返回为准，不要自行重算或外推；引用时注明截至日期（latest_date / 行业 updated）。
- 数据源为免费公开数据（AkShare/东方财富），无 SLA：返回为空或过旧时如实说明，不要用其他来源冒充系统数据。
