import json, math, traceback
from datetime import datetime, date, timedelta
import sources
from db import SessionLocal
from models import WatchRecord, Alert, NavHistory, JobLog, KV, AgencyPool, ScreeningRun, ScreeningResult

ALGO_VERSION = "screen-v1.1 / nav-v1.0"
WEIGHTS = {
    "进攻": dict(persist=.25, risk_adj=.20, dd=.15, momentum=.30, long=.10),
    "均衡": dict(persist=.30, risk_adj=.25, dd=.20, momentum=.15, long=.10),
    "防御": dict(persist=.30, risk_adj=.30, dd=.30, momentum=.05, long=.05),
}

def _log_start(db, job):
    jl = JobLog(job=job, status="running")
    db.add(jl); db.commit(); db.refresh(jl)
    return jl

def _log_done(db, jl, status, detail):
    jl.finished_at = datetime.now(); jl.status = status; jl.detail = detail[:1900]
    db.commit()

def set_kv(db, key, obj):
    row = db.get(KV, key)
    if row:
        row.value = json.dumps(obj, ensure_ascii=False); row.updated_at = datetime.now()
    else:
        db.add(KV(key=key, value=json.dumps(obj, ensure_ascii=False)))
    db.commit()

def get_kv(db, key, default=None):
    row = db.get(KV, key)
    if not row:
        return default
    try:
        return json.loads(row.value)
    except Exception:
        return default

# ---------------- 需求一: 跟踪净值更新 ----------------
def update_watchlist():
    db = SessionLocal()
    jl = _log_start(db, "watch_update")
    ok, fail, hits = 0, [], 0
    try:
        records = db.query(WatchRecord).all()
        for rec in records:
            try:
                ds, nav, cum, dpct = sources.em_latest_nav(rec.fund_code)
                ldate = datetime.strptime(ds, "%Y-%m-%d").date()
                # 双源校验: AkShare 历史接口最新值 (允许慢一天, 仅当日期相同才比)
                warn = ""
                try:
                    hist = sources.ak_fund_history(rec.fund_code)
                    if hist and str(hist[-1][0])[:10] == ds and abs(hist[-1][1] - nav) / nav > 0.0005:
                        warn = f"双源不一致 akshare={hist[-1][1]}"
                except Exception:
                    pass
                rec.latest_date, rec.latest_nav, rec.latest_cum_nav, rec.daily_pct = ldate, nav, cum, dpct
                rec.ret_pct = (nav - rec.sale_nav) / rec.sale_nav * 100
                rec.status = "hit" if rec.ret_pct >= rec.target_pct else ("warn_down" if rec.ret_pct <= -5 else "tracking")
                if not rec.fund_name:
                    try: rec.fund_name = sources.em_fund_name(rec.fund_code)
                    except Exception: pass
                # 落历史
                exist = db.query(NavHistory).filter_by(fund_code=rec.fund_code, date=ldate).first()
                if not exist:
                    db.add(NavHistory(fund_code=rec.fund_code, date=ldate, unit_nav=nav, cum_nav=cum, daily_pct=dpct))
                if rec.status == "hit":
                    already = db.query(Alert).filter_by(watch_id=rec.id, triggered_date=ldate).first()
                    if not already:
                        db.add(Alert(watch_id=rec.id, fund_code=rec.fund_code, fund_name=rec.fund_name,
                                     triggered_date=ldate, ret_pct=rec.ret_pct, nav=nav))
                        hits += 1
                ok += 1
                sources.sleep_jitter(0.3, 0.8)
            except Exception as e:
                fail.append(f"{rec.fund_code}:{str(e)[:80]}")
            db.commit()
        _log_done(db, jl, "done" if not fail else "partial", f"成功{ok} 失败{len(fail)} 新达标{hits} {'; '.join(fail)[:400]}")
        return {"ok": ok, "fail": fail, "new_alerts": hits}
    except Exception:
        _log_done(db, jl, "failed", traceback.format_exc()[-1500:])
        raise
    finally:
        db.close()

# ---------------- 市场状态 ----------------
def update_market_regime():
    db = SessionLocal()
    jl = _log_start(db, "market_regime")
    try:
        closes = sources.em_index_closes("1.000300", 200)
        if len(closes) < 65:
            raise RuntimeError("沪深300数据不足")
        vals = [c for _, c in closes]
        last = vals[-1]
        ret20 = (last / vals[-21] - 1) * 100
        ret60 = (last / vals[-61] - 1) * 100
        ma60 = sum(vals[-60:]) / 60
        if ret20 > 3 and last > ma60 and ret60 > 0:
            regime = "进攻"
        elif ret20 < -3 and last < ma60:
            regime = "防御"
        else:
            regime = "均衡"
        obj = {"regime": regime, "date": str(closes[-1][0]), "csi300": last,
               "ret20": round(ret20, 2), "ret60": round(ret60, 2),
               "ma60": round(ma60, 2), "above_ma60": last > ma60,
               "basis": f"沪深300 近20日 {ret20:+.2f}%、近60日 {ret60:+.2f}%、收盘 {'高于' if last > ma60 else '低于'} 60日均线"}
        set_kv(db, "market_regime", obj)
        _log_done(db, jl, "done", json.dumps(obj, ensure_ascii=False))
        return obj
    except Exception:
        _log_done(db, jl, "failed", traceback.format_exc()[-1500:])
        raise
    finally:
        db.close()

# ---------------- 行业 ----------------
def update_industry():
    db = SessionLocal()
    jl = _log_start(db, "industry_sw")
    try:
        rows = sources.ak_sw_industry_returns()
        rows_sorted = sorted(rows, key=lambda x: (x["r1m"] if x["r1m"] is not None else -999), reverse=True)
        for i, r in enumerate(rows_sorted):
            r["rank"] = i + 1
            r["stance"] = "超配" if i < 5 else ("低配" if i >= len(rows_sorted) - 5 else "标配")
        obj = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "AkShare/申万宏源研究", "rows": rows_sorted}
        set_kv(db, "industry_sw", obj)
        _log_done(db, jl, "done", f"{len(rows)} 个行业")
        return obj
    except Exception:
        _log_done(db, jl, "failed", traceback.format_exc()[-1200:])
        raise
    finally:
        db.close()

# ---------------- 需求二: 筛选 ----------------
def _fund_metrics(code):
    """用东财历史净值算近3年指标; 数据不足返回 None"""
    import numpy as np
    name, hist = sources.em_fund_history(code)
    if len(hist) < 250:
        return None
    hist = hist[-750:]
    navs = [n for _, n in hist]
    rets = [(navs[i] / navs[i - 1] - 1) for i in range(1, len(navs))]
    peak, maxdd = navs[0], 0.0
    for n in navs:
        peak = max(peak, n); maxdd = min(maxdd, n / peak - 1)
    years = len(rets) / 252
    ann = (navs[-1] / navs[0]) ** (1 / years) - 1 if years > 0 else 0
    vol = (sum((r - sum(rets) / len(rets)) ** 2 for r in rets) / len(rets)) ** 0.5 * math.sqrt(252)
    sharpe = (ann - 0.015) / vol if vol > 0 else 0
    calmar = (ann * 100) / abs(maxdd * 100) if maxdd < 0 else 0
    return {"name": name, "max_dd": round(maxdd * 100, 2), "sharpe": round(sharpe, 3), "calmar": round(calmar, 3), "ann": round(ann * 100, 2)}

def _pct_rank(series):
    return series.rank(pct=True) * 100

def run_screening(regime=None, weights=None, batch="default", top_n=20, max_candidates=60):
    db = SessionLocal()
    if not regime:
        mr = get_kv(db, "market_regime", {})
        regime = mr.get("regime", "均衡")
    w = weights or WEIGHTS.get(regime, WEIGHTS["均衡"])
    run = ScreeningRun(regime=regime, weights=json.dumps(w), status="running")
    db.add(run); db.commit(); db.refresh(run)
    jl = _log_start(db, "screening")
    try:
        import pandas as pd
        pool = db.query(AgencyPool).filter_by(batch=batch).all()
        pool_codes = [p.fund_code for p in pool]
        if not pool_codes:
            raise RuntimeError("代销池为空, 请先导入代销名单")
        rank = sources.ak_rank_all()
        # 分位在全市场同类型全集内计算
        rank["persist"] = pd.concat([_pct_rank(g["近1年"]) * .4 + _pct_rank(g["近2年"]) * .3 + _pct_rank(g["近3年"]) * .3 for _, g in rank.groupby("类型")])
        rank["momentum_s"] = pd.concat([_pct_rank(g["近1月"]) * .4 + _pct_rank(g["近3月"]) * .6 for _, g in rank.groupby("类型")])
        rank["long_s"] = pd.concat([_pct_rank(g["成立来"]) for _, g in rank.groupby("类型")])
        run.universe_count = len(rank); run.pool_count = len(pool_codes)
        m = rank[rank["基金代码"].isin(pool_codes)].copy()
        if m.empty:
            raise RuntimeError("代销池代码与排行数据无匹配")
        # 入围: 持续性>=60 或 前40%, 上限 max_candidates 只 (按持续性排序)
        thr = m["persist"].quantile(0.6)
        cand = m[(m["persist"] >= 60) | (m["persist"] >= thr)].sort_values("persist", ascending=False).head(max_candidates)
        rows = []
        for _, r in cand.iterrows():
            code = str(r["基金代码"]).zfill(6)
            try:
                met = _fund_metrics(code)
            except Exception:
                met = None
            if met is None:
                continue
            rows.append({"code": code, "name": str(r.get("基金简称") or met["name"]), "type": str(r.get("类型") or ""),
                         "persist": float(r["persist"]), "momentum": float(r["momentum_s"]), "long": float(r["long_s"]),
                         "r1m": float(r.get("近1月") or 0), "r3m": float(r.get("近3月") or 0),
                         "r1y": float(r.get("近1年") or 0), "r3y": float(r.get("近3年") or 0), **met})
            sources.sleep_jitter(0.2, 0.5)
        if not rows:
            raise RuntimeError("入围基金指标计算全部失败")
        import pandas as pd
        df = pd.DataFrame(rows)
        df["risk_adj"] = _pct_rank(df["sharpe"]) * .5 + _pct_rank(df["calmar"]) * .5
        df["dd_score"] = _pct_rank(-df["max_dd"].abs())
        df["score"] = (df["persist"] * w["persist"] + df["risk_adj"] * w["risk_adj"] + df["dd_score"] * w["dd"]
                       + df["momentum"] * w["momentum"] + df["long"] * w["long"]).round(1)
        df = df.sort_values("score", ascending=False).head(top_n)
        for _, r in df.iterrows():
            dd = abs(r["max_dd"])
            if r["type"] == "债券型" and dd > 8:
                tag = "⚠️ 债型回撤超8%门槛,谨慎推荐"
            elif r["type"] in ("股票型", "混合型", "指数型", "QDII") and dd > 35:
                tag = "⚠️ 回撤超35%门槛,谨慎推荐"
            else:
                tag = "正常"
            reason = (f"持续性分 {r['persist']:.0f}(全市场同类分位), 近3年 {r['r3y']:+.1f}%, 夏普 {r['sharpe']:.2f}, "
                      f"卡玛 {r['calmar']:.2f}, 近3年最大回撤 {r['max_dd']:.1f}%")
            db.add(ScreeningResult(run_id=run.id, fund_code=r["code"], fund_name=r["name"], fund_type=r["type"],
                                   score=float(r["score"]), persist=float(r["persist"]), risk_adj=float(r["risk_adj"]),
                                   dd_score=float(r["dd_score"]), momentum=float(r["momentum"]), long_score=float(r["long"]),
                                   max_dd=float(r["max_dd"]), sharpe=float(r["sharpe"]), calmar=float(r["calmar"]),
                                   r1m=float(r["r1m"]), r3m=float(r["r3m"]), r1y=float(r["r1y"]), r3y=float(r["r3y"]),
                                   risk_tag=tag, reason=reason))
        run.status = "done"; run.finished_at = datetime.now(); run.note = f"算法 {ALGO_VERSION}; 入围精算 {len(df)} 只"
        db.commit()
        _log_done(db, jl, "done", f"run#{run.id} 结果{len(df)}只 市场状态{regime}")
        return {"run_id": run.id, "count": len(df)}
    except Exception as e:
        run.status = "failed"; run.note = str(e)[:500]; db.commit()
        _log_done(db, jl, "failed", traceback.format_exc()[-1500:])
        raise
    finally:
        db.close()
