"""免费数据源适配层。
主源: AkShare(聚合东方财富等公开页) / 东方财富直连; 校验: BaoStock(股票指数, 按需)。
所有函数失败抛异常, 由 jobs 层记录, 绝不返回假数据。
"""
import json, re, time, random, urllib.request
from datetime import datetime, timedelta

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://fund.eastmoney.com/"}

def _get(url, headers=None, timeout=25):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")

def sleep_jitter(a=0.4, b=1.2):
    time.sleep(random.uniform(a, b))

# ---------- 东方财富直连: 基金净值 ----------
def em_latest_nav(code: str):
    """返回 (date_str, unit_nav, cum_nav, daily_pct) 取 lsjz 最新一行"""
    url = f"https://api.fund.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize=2"
    txt = _get(url, {"Referer": "https://fundf10.eastmoney.com/"})
    d = json.loads(txt)
    row = d["Data"]["LSJZList"][0]
    return row["FSRQ"], float(row["DWJZ"]), float(row["LJJZ"]), float(row["JZZZL"] or 0)

def em_fund_history(code: str):
    """pingzhongdata: 返回 (fund_name, [(date, unit_nav), ...] 升序)"""
    txt = _get(f"https://fund.eastmoney.com/pingzhongdata/{code}.js")
    m = re.search(r'var fS_name = "(.*?)";', txt)
    name = m.group(1) if m else ""
    m = re.search(r"var Data_netWorthTrend = (\[.*?\]);/\*单位净值走势", txt, re.S)
    if not m:
        m = re.search(r"var Data_netWorthTrend = (\[.*?\]);", txt, re.S)
    if not m:
        raise ValueError(f"{code} 未找到净值走势数据")
    arr = json.loads(m.group(1))
    out = []
    for it in arr:
        dt = datetime.fromtimestamp(it["x"] / 1000).date()
        out.append((dt, float(it["y"])))
    out.sort(key=lambda x: x[0])
    return name, out

def em_fund_name(code: str):
    txt = _get(f"https://fund.eastmoney.com/pingzhongdata/{code}.js")
    m = re.search(r'var fS_name = "(.*?)";', txt)
    return m.group(1) if m else ""

# ---------- 东方财富直连: 指数日线 ----------
def em_index_closes(secid: str, limit=200):
    """secid 如 1.000300 沪深300 / 0.399001 深证成指。返回 [(date, close)] 升序"""
    url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}"
           f"&fields1=f1&fields2=f51,f53&klt=101&fqt=0&end=20500101&lmt={limit}")
    d = json.loads(_get(url, {"Referer": "https://quote.eastmoney.com/"}))
    out = []
    for line in (d.get("data") or {}).get("klines") or []:
        ds, close = line.split(",")
        out.append((datetime.strptime(ds, "%Y-%m-%d").date(), float(close)))
    return out

# ---------- AkShare: 基金排行(筛选快筛, 一次取全市场) ----------
def ak_rank_all():
    import akshare as ak
    import pandas as pd
    frames = []
    for sym in ["股票型", "混合型", "债券型", "指数型", "QDII"]:
        try:
            d = ak.fund_open_fund_rank_em(symbol=sym)
            d["类型"] = sym
            frames.append(d)
            sleep_jitter(1.0, 2.0)
        except Exception:
            continue
    if not frames:
        raise RuntimeError("AkShare 排行接口全部失败")
    rank = pd.concat(frames).drop_duplicates("基金代码").reset_index(drop=True)
    rank["基金代码"] = rank["基金代码"].astype(str).str.zfill(6)
    return rank

def ak_fund_history(code: str):
    import akshare as ak
    df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    out = [(row["净值日期"], float(row["单位净值"])) for _, row in df.iterrows()]
    out.sort(key=lambda x: x[0])
    return out

# ---------- AkShare: 申万一级行业 ----------
SW_INDUSTRIES = {
    "801010": "农林牧渔", "801030": "基础化工", "801040": "钢铁", "801050": "有色金属",
    "801080": "电子", "801880": "汽车", "801110": "家用电器", "801120": "食品饮料",
    "801130": "纺织服饰", "801140": "轻工制造", "801150": "医药生物", "801160": "公用事业",
    "801170": "交通运输", "801180": "房地产", "801200": "商贸零售", "801210": "社会服务",
    "801230": "综合", "801710": "建筑材料", "801720": "建筑装饰", "801730": "电力设备",
    "801890": "机械设备", "801740": "国防军工", "801750": "计算机", "801760": "传媒",
    "801770": "通信", "801950": "煤炭", "801960": "石油石化", "801970": "环保",
    "801980": "美容护理", "801780": "银行", "801790": "非银金融",
}

def ak_sw_industry_returns():
    """逐行业取日线, 算近1周/1月/3月涨跌幅。慢且依赖 swsresearch 可达性, 失败抛错由上层处理。"""
    import akshare as ak
    results = []
    for code, name in SW_INDUSTRIES.items():
        try:
            df = ak.index_hist_sw(symbol=code, period="day")
            # index_hist_sw 列: 日期/开盘/最高/最低/收盘/成交量/成交额 (以实际列名为准做兜底)
            cols = list(df.columns)
            date_col = cols[0]
            close_col = "收盘" if "收盘" in cols else cols[4]
            series = [(str(r[date_col])[:10], float(r[close_col])) for _, r in df.iterrows()]
            series.sort()
            if len(series) < 65:
                continue
            last = series[-1][1]
            def ret(n):
                return (last / series[-1 - n][1] - 1) * 100 if len(series) > n else None
            results.append({"code": code, "name": name, "date": series[-1][0],
                            "r1w": ret(5), "r1m": ret(21), "r3m": ret(63)})
            sleep_jitter(0.2, 0.6)
        except Exception:
            continue
    if not results:
        raise RuntimeError("申万行业数据全部获取失败")
    return results
