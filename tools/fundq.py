#!/usr/bin/env python3
"""fundq — 基金量化分析系统 Agent CLI

供 Muse / WorkBuddy 等外部 Agent 调用本系统的分析与数据。
单文件、零依赖(仅 Python 标准库)。输出统一为 JSON,便于 Agent 解析。

配置(环境变量):
  FUNDQ_URL      服务地址, 默认 http://192.168.99.4:18082
                 注意: 外网地址 https://fund.jjrex.duckdns.org:88 是给人用浏览器的,
                 外层还有飞牛 fnOS 的 Web 登录验证, API Key 穿不过去, Agent 勿用。
  FUNDQ_API_KEY  管理后台「Agent 接入」页生成的密钥(fqk_ 开头)
                 read  = 只读查询; write = 含写操作

用法:
  fundq.py me                          当前密钥信息
  fundq.py dashboard                   仪表盘汇总(跟踪数/达标/市场状态/行业TOP)
  fundq.py watch list                  销售跟踪列表
  fundq.py watch add 000001 --date 2026-11-02 --nav 0.9390 [--target 5] [--manager 张三] [--note 备注]   (write)
  fundq.py watch rm 3                                                                                (write)
  fundq.py watch refresh               刷新全部跟踪净值并触发达标判定                                    (write)
  fundq.py alerts [--limit 20]         达标提醒列表
  fundq.py alerts-contacted 5          标记提醒为已联系客户                                              (write)
  fundq.py pool list                   代销池列表
  fundq.py pool add 000001 161725 ...  向代销池添加代码                                                  (write)
  fundq.py pool import list.csv        从 csv/xlsx 导入代销池(提取 6 位代码)                              (write)
  fundq.py pool rm 7                   删除代销池一条                                                    (write)
  fundq.py screen run [--regime 防御]  发起一轮筛选(后台执行)                                            (write)
  fundq.py screen runs                 筛选轮次列表
  fundq.py screen results 3            某轮筛选结果(按综合分降序)
  fundq.py fund 000001                 基金详情: 最新净值/区间收益/夏普/卡玛/最大回撤/净值序列
  fundq.py industry                    申万一级行业涨幅(系统内缓存, 由周任务更新)
  fundq.py system status               系统任务日志与数据源说明
  fundq.py system run-job watch_update 手动触发任务: watch_update/market_regime/industry_sw              (write)

退出码: 0 成功; 2 参数/配置错误; 3 HTTP 错误(错误体打到 stderr)。
"""
import argparse, json, os, sys, urllib.request, urllib.error

BASE = os.getenv("FUNDQ_URL", "http://192.168.99.4:18082").rstrip("/")
KEY = os.getenv("FUNDQ_API_KEY", "")


def call(method, path, body=None, raw=None, ctype="application/json"):
    if not KEY:
        print("缺少 FUNDQ_API_KEY 环境变量(在管理后台「Agent 接入」页生成)", file=sys.stderr)
        sys.exit(2)
    data = raw
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("X-API-Key", KEY)
    if data is not None:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode(errors='ignore')[:400]}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"请求失败: {e}", file=sys.stderr)
        sys.exit(3)


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(prog="fundq", description="基金量化分析系统 Agent CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("me")
    sub.add_parser("dashboard")
    sub.add_parser("industry")

    w = sub.add_parser("watch"); ws = w.add_subparsers(dest="wcmd", required=True)
    ws.add_parser("list"); ws.add_parser("refresh")
    wa = ws.add_parser("add"); wa.add_argument("code")
    wa.add_argument("--date", required=True); wa.add_argument("--nav", required=True, type=float)
    wa.add_argument("--name", default=""); wa.add_argument("--target", type=float, default=5.0)
    wa.add_argument("--manager", default=""); wa.add_argument("--note", default="")
    wr = ws.add_parser("rm"); wr.add_argument("id", type=int)

    a = sub.add_parser("alerts"); a.add_argument("--limit", type=int, default=100)
    ac = sub.add_parser("alerts-contacted"); ac.add_argument("id", type=int)

    po = sub.add_parser("pool"); ps = po.add_subparsers(dest="pcmd", required=True)
    ps.add_parser("list")
    pa = ps.add_parser("add"); pa.add_argument("codes", nargs="+")
    pi = ps.add_parser("import"); pi.add_argument("file")
    pr = ps.add_parser("rm"); pr.add_argument("id", type=int)

    s = sub.add_parser("screen"); ss = s.add_subparsers(dest="scmd", required=True)
    sr = ss.add_parser("run"); sr.add_argument("--regime", default=None)
    ss.add_parser("runs")
    sres = ss.add_parser("results"); sres.add_argument("run_id", type=int)

    f = sub.add_parser("fund"); f.add_argument("code")

    sy = sub.add_parser("system"); sys_ = sy.add_subparsers(dest="ycmd", required=True)
    sys_.add_parser("status")
    sj = sys_.add_parser("run-job"); sj.add_argument("job", choices=["watch_update", "market_regime", "industry_sw"])

    args = p.parse_args()

    if args.cmd == "me":
        out(call("GET", "/api/me"))
    elif args.cmd == "dashboard":
        out(call("GET", "/api/dashboard"))
    elif args.cmd == "industry":
        out(call("GET", "/api/industry"))
    elif args.cmd == "watch":
        if args.wcmd == "list":
            out(call("GET", "/api/watch"))
        elif args.wcmd == "refresh":
            out(call("POST", "/api/watch/update"))
        elif args.wcmd == "add":
            out(call("POST", "/api/watch", {"fund_code": args.code, "fund_name": args.name,
                                            "sale_date": args.date, "sale_nav": args.nav,
                                            "target_pct": args.target, "manager": args.manager,
                                            "note": args.note}))
        elif args.wcmd == "rm":
            out(call("DELETE", f"/api/watch/{args.id}"))
    elif args.cmd == "alerts":
        rows = call("GET", "/api/alerts")
        out(rows[: args.limit])
    elif args.cmd == "alerts-contacted":
        out(call("POST", f"/api/alerts/{args.id}/contacted"))
    elif args.cmd == "pool":
        if args.pcmd == "list":
            out(call("GET", "/api/pool"))
        elif args.pcmd == "add":
            out(call("POST", "/api/pool/add", {"codes": args.codes}))
        elif args.pcmd == "import":
            import mimetypes, uuid
            fn = os.path.basename(args.file)
            boundary = "----fundq" + uuid.uuid4().hex
            payload = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fn}\"\r\n"
                       f"Content-Type: {mimetypes.guess_type(fn)[0] or 'application/octet-stream'}\r\n\r\n").encode() \
                      + open(args.file, "rb").read() + f"\r\n--{boundary}--\r\n".encode()
            out(call("POST", "/api/pool/import", raw=payload, ctype=f"multipart/form-data; boundary={boundary}"))
        elif args.pcmd == "rm":
            out(call("DELETE", f"/api/pool/{args.id}"))
    elif args.cmd == "screen":
        if args.scmd == "run":
            out(call("POST", "/api/screening/run", {"regime": args.regime}))
        elif args.scmd == "runs":
            out(call("GET", "/api/screening/runs"))
        elif args.scmd == "results":
            out(call("GET", f"/api/screening/runs/{args.run_id}/results"))
    elif args.cmd == "fund":
        d = call("GET", f"/api/funds/{args.code}")
        if isinstance(d, dict) and "series" in d:  # 序列太长时只留近 30 日, 全量走网页
            d["series_tail30"] = d.pop("series")[-30:]
        out(d)
    elif args.cmd == "system":
        if args.ycmd == "status":
            out(call("GET", "/api/system/status"))
        elif args.ycmd == "run-job":
            out(call("POST", "/api/system/run-job", {"job": args.job}))


if __name__ == "__main__":
    main()
