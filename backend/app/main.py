import io, json, os, threading
from datetime import datetime, date
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import jwt as jwtlib

from db import Base, engine, SessionLocal, get_db
from models import User, WatchRecord, Alert, AgencyPool, ScreeningRun, ScreeningResult, JobLog, NavHistory
from security import hash_password, verify_password, make_token, parse_token
import jobs as jobmod
import sources

Base.metadata.create_all(bind=engine)
app = FastAPI(title="基金量化分析系统", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------- 初始化: 管理员 + 示例数据 ----------
DEFAULT_PASSWORD = "admin"

def seed():
    db = SessionLocal()
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pw = os.getenv("ADMIN_PASSWORD", DEFAULT_PASSWORD)
    u = db.query(User).filter_by(username=admin_user).first()
    if not u:
        db.add(User(username=admin_user, password_hash=hash_password(admin_pw), role="admin"))
        db.commit()
    elif not verify_password(admin_pw, u.password_hash):
        # 管理员密码以部署环境为准: 改 .env 后重启即生效
        u.password_hash = hash_password(admin_pw)
        db.commit()
    if os.getenv("SEED_DEMO", "true").lower() == "true" and db.query(WatchRecord).count() == 0:
        demo = [
            ("000001", "华夏成长混合", date(2026, 11, 2), 0.9390, "示例-可删"),
            ("161725", "招商中证白酒指数(LOF)A", date(2026, 11, 2), 0.5877, "示例-可删"),
            ("110011", "易方达优质精选混合(QDII)", date(2026, 11, 2), 4.0490, "示例-可删"),
        ]
        for code, name, sd, nav, note in demo:
            db.add(WatchRecord(owner=admin_user, fund_code=code, fund_name=name, sale_date=sd, sale_nav=nav, note=note))
        for code, name in [("000001", "华夏成长混合"), ("161725", "招商中证白酒指数(LOF)A"), ("110011", "易方达优质精选混合(QDII)"),
                           ("005825", "申万菱信智能驱动股票A"), ("002289", "华商改革创新股票A")]:
            db.add(AgencyPool(batch="default", fund_code=code, fund_name=name))
        db.commit()
    db.close()

seed()

# ---------- 鉴权 ----------
def current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    try:
        p = parse_token(authorization[7:])
        return {"username": p["sub"], "role": p.get("role", "manager")}
    except jwtlib.PyJWTError:
        raise HTTPException(401, "登录已过期")

class LoginIn(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login")
def login(body: LoginIn, db=Depends(get_db)):
    u = db.query(User).filter_by(username=body.username).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return {"token": make_token(u.username, u.role), "username": u.username, "role": u.role}

@app.get("/api/me")
def me(user=Depends(current_user), db=Depends(get_db)):
    u = db.query(User).filter_by(username=user["username"]).first()
    using_default = bool(u and verify_password(DEFAULT_PASSWORD, u.password_hash))
    return {**user, "using_default_password": using_default}

@app.get("/api/health")
def health():
    return {"ok": True, "time": datetime.now().isoformat()}

# ---------- 账号管理(仅 admin) ----------
def require_admin(user):
    if user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可管理账号")

class UserIn(BaseModel):
    username: str
    password: str
    role: Optional[str] = "manager"

class PwIn(BaseModel):
    password: str

class MyPwIn(BaseModel):
    old_password: str
    new_password: str

@app.get("/api/users")
def list_users(user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    return [{"id": u.id, "username": u.username, "role": u.role, "created_at": str(u.created_at)}
            for u in db.query(User).order_by(User.id).all()]

@app.post("/api/users")
def create_user(body: UserIn, user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    if body.role not in ("admin", "manager", "viewer"):
        raise HTTPException(400, "角色只能是 admin/manager/viewer")
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(400, "用户名已存在")
    u = User(username=body.username.strip(), password_hash=hash_password(body.password), role=body.role)
    db.add(u); db.commit(); db.refresh(u)
    return {"id": u.id, "username": u.username, "role": u.role}

@app.post("/api/users/{uid}/password")
def reset_user_password(uid: int, body: PwIn, user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    u = db.get(User, uid)
    if not u: raise HTTPException(404, "用户不存在")
    u.password_hash = hash_password(body.password); db.commit()
    return {"ok": True}

@app.delete("/api/users/{uid}")
def delete_user(uid: int, user=Depends(current_user), db=Depends(get_db)):
    require_admin(user)
    u = db.get(User, uid)
    if not u: raise HTTPException(404, "用户不存在")
    if u.username == user["username"]:
        raise HTTPException(400, "不能删除自己")
    db.delete(u); db.commit()
    return {"ok": True}

@app.post("/api/me/password")
def change_my_password(body: MyPwIn, user=Depends(current_user), db=Depends(get_db)):
    u = db.query(User).filter_by(username=user["username"]).first()
    if not u or not verify_password(body.old_password, u.password_hash):
        raise HTTPException(400, "原密码不正确")
    if len(body.new_password) < 6:
        raise HTTPException(400, "新密码至少 6 位")
    u.password_hash = hash_password(body.new_password); db.commit()
    return {"ok": True}

# ---------- 仪表盘 ----------
@app.get("/api/dashboard")
def dashboard(user=Depends(current_user), db=Depends(get_db)):
    watches = db.query(WatchRecord).all()
    alerts = db.query(Alert).order_by(Alert.id.desc()).limit(10).all()
    regime = jobmod.get_kv(db, "market_regime", {})
    industry = jobmod.get_kv(db, "industry_sw", {})
    last_jobs = {}
    for job in ["watch_update", "market_regime", "industry_sw", "screening"]:
        jl = db.query(JobLog).filter_by(job=job).order_by(JobLog.id.desc()).first()
        if jl:
            last_jobs[job] = {"status": jl.status, "at": str(jl.finished_at or jl.started_at), "detail": jl.detail}
    return {
        "watch_count": len(watches),
        "hit_count": sum(1 for w in watches if w.status == "hit"),
        "warn_down_count": sum(1 for w in watches if w.status == "warn_down"),
        "pool_count": db.query(AgencyPool).count(),
        "alerts": [{"id": a.id, "fund_code": a.fund_code, "fund_name": a.fund_name, "date": str(a.triggered_date),
                    "ret_pct": a.ret_pct, "contacted": a.contacted} for a in alerts],
        "regime": regime,
        "industry_top": (industry.get("rows") or [])[:5],
        "industry_bottom": (industry.get("rows") or [])[-5:],
        "industry_updated": industry.get("updated"),
        "last_jobs": last_jobs,
        "algo_version": jobmod.ALGO_VERSION,
    }

# ---------- 需求一: 跟踪 ----------
class WatchIn(BaseModel):
    fund_code: str
    fund_name: Optional[str] = ""
    sale_date: str
    sale_nav: float
    target_pct: Optional[float] = 5.0
    manager: Optional[str] = ""
    note: Optional[str] = ""

def watch_out(w: WatchRecord):
    return {"id": w.id, "fund_code": w.fund_code, "fund_name": w.fund_name, "sale_date": str(w.sale_date),
            "sale_nav": w.sale_nav, "target_pct": w.target_pct, "manager": w.manager, "note": w.note,
            "latest_date": str(w.latest_date) if w.latest_date else None, "latest_nav": w.latest_nav,
            "latest_cum_nav": w.latest_cum_nav, "daily_pct": w.daily_pct, "ret_pct": w.ret_pct, "status": w.status}

@app.get("/api/watch")
def list_watch(user=Depends(current_user), db=Depends(get_db)):
    return [watch_out(w) for w in db.query(WatchRecord).order_by(WatchRecord.id).all()]

@app.post("/api/watch")
def add_watch(body: WatchIn, user=Depends(current_user), db=Depends(get_db)):
    code = body.fund_code.strip().zfill(6)
    name = body.fund_name or ""
    if not name:
        try: name = sources.em_fund_name(code)
        except Exception: name = ""
    w = WatchRecord(owner=user["username"], fund_code=code, fund_name=name,
                    sale_date=datetime.strptime(body.sale_date, "%Y-%m-%d").date(),
                    sale_nav=body.sale_nav, target_pct=body.target_pct or 5.0,
                    manager=body.manager or "", note=body.note or "")
    db.add(w); db.commit(); db.refresh(w)
    return watch_out(w)

@app.put("/api/watch/{wid}")
def edit_watch(wid: int, body: WatchIn, user=Depends(current_user), db=Depends(get_db)):
    w = db.get(WatchRecord, wid)
    if not w: raise HTTPException(404, "记录不存在")
    w.sale_date = datetime.strptime(body.sale_date, "%Y-%m-%d").date()
    w.sale_nav = body.sale_nav; w.target_pct = body.target_pct or 5.0
    w.manager = body.manager or ""; w.note = body.note or ""
    if w.latest_nav:
        w.ret_pct = (w.latest_nav - w.sale_nav) / w.sale_nav * 100
        w.status = "hit" if w.ret_pct >= w.target_pct else ("warn_down" if w.ret_pct <= -5 else "tracking")
    db.commit()
    return watch_out(w)

@app.delete("/api/watch/{wid}")
def del_watch(wid: int, user=Depends(current_user), db=Depends(get_db)):
    w = db.get(WatchRecord, wid)
    if w: db.delete(w); db.commit()
    return {"ok": True}

@app.post("/api/watch/update")
def update_watch(user=Depends(current_user)):
    return jobmod.update_watchlist()

@app.get("/api/alerts")
def list_alerts(user=Depends(current_user), db=Depends(get_db)):
    return [{"id": a.id, "fund_code": a.fund_code, "fund_name": a.fund_name, "date": str(a.triggered_date),
             "ret_pct": a.ret_pct, "nav": a.nav, "contacted": a.contacted}
            for a in db.query(Alert).order_by(Alert.id.desc()).limit(100).all()]

@app.post("/api/alerts/{aid}/contacted")
def mark_contacted(aid: int, user=Depends(current_user), db=Depends(get_db)):
    a = db.get(Alert, aid)
    if a: a.contacted = True; db.commit()
    return {"ok": True}

# ---------- 代销池 ----------
@app.get("/api/pool")
def list_pool(user=Depends(current_user), db=Depends(get_db)):
    return [{"id": p.id, "fund_code": p.fund_code, "fund_name": p.fund_name, "fund_type": p.fund_type, "risk_level": p.risk_level}
            for p in db.query(AgencyPool).filter_by(batch="default").order_by(AgencyPool.id).all()]

class PoolIn(BaseModel):
    codes: list[str]

@app.post("/api/pool/add")
def pool_add(body: PoolIn, user=Depends(current_user), db=Depends(get_db)):
    added = 0
    for raw in body.codes:
        code = str(raw).strip().zfill(6)
        if not code.isdigit(): continue
        if db.query(AgencyPool).filter_by(batch="default", fund_code=code).first(): continue
        name = ""
        try: name = sources.em_fund_name(code)
        except Exception: pass
        db.add(AgencyPool(batch="default", fund_code=code, fund_name=name)); added += 1
    db.commit()
    return {"added": added, "total": db.query(AgencyPool).filter_by(batch="default").count()}

@app.delete("/api/pool/{pid}")
def pool_del(pid: int, user=Depends(current_user), db=Depends(get_db)):
    p = db.get(AgencyPool, pid)
    if p: db.delete(p); db.commit()
    return {"ok": True}

@app.post("/api/pool/import")
async def pool_import(file: UploadFile = File(...), user=Depends(current_user), db=Depends(get_db)):
    content = await file.read()
    codes = []
    fname = (file.filename or "").lower()
    if fname.endswith(".csv"):
        import csv
        rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig", "ignore"))))
        for r in rows:
            for cell in r:
                c = str(cell).strip()
                if c.isdigit() and len(c) == 6: codes.append(c)
    elif fname.endswith((".xlsx", ".xls")):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            for cell in row or []:
                c = str(cell).strip() if cell is not None else ""
                if c.isdigit() and len(c) == 6: codes.append(c)
    else:
        raise HTTPException(400, "只支持 csv / xlsx")
    added = 0
    for code in dict.fromkeys(codes):
        if db.query(AgencyPool).filter_by(batch="default", fund_code=code).first(): continue
        db.add(AgencyPool(batch="default", fund_code=code)); added += 1
    db.commit()
    return {"found_codes": len(set(codes)), "added": added, "total": db.query(AgencyPool).filter_by(batch="default").count()}

# ---------- 需求二: 筛选 ----------
class ScreenIn(BaseModel):
    regime: Optional[str] = None
    weights: Optional[dict] = None

@app.post("/api/screening/run")
def screening_run(body: ScreenIn, user=Depends(current_user)):
    # 同步执行可能数分钟: 放后台线程, 前端轮询 runs 状态
    def _run():
        try: jobmod.run_screening(regime=body.regime, weights=body.weights)
        except Exception: pass
    t = threading.Thread(target=_run, daemon=True); t.start()
    return {"started": True}

@app.get("/api/screening/runs")
def screening_runs(user=Depends(current_user), db=Depends(get_db)):
    return [{"id": r.id, "created_at": str(r.created_at), "regime": r.regime, "status": r.status,
             "universe": r.universe_count, "pool": r.pool_count, "note": r.note}
            for r in db.query(ScreeningRun).order_by(ScreeningRun.id.desc()).limit(20).all()]

@app.get("/api/screening/runs/{rid}/results")
def screening_results(rid: int, user=Depends(current_user), db=Depends(get_db)):
    return [{"fund_code": r.fund_code, "fund_name": r.fund_name, "fund_type": r.fund_type, "score": r.score,
             "persist": r.persist, "risk_adj": r.risk_adj, "dd_score": r.dd_score, "momentum": r.momentum,
             "long_score": r.long_score, "max_dd": r.max_dd, "sharpe": r.sharpe, "calmar": r.calmar,
             "r1m": r.r1m, "r3m": r.r3m, "r1y": r.r1y, "r3y": r.r3y, "risk_tag": r.risk_tag, "reason": r.reason}
            for r in db.query(ScreeningResult).filter_by(run_id=rid).order_by(ScreeningResult.score.desc()).all()]

@app.post("/api/screening/publish/{rid}")
def screening_publish(rid: int, user=Depends(current_user), db=Depends(get_db)):
    if user["role"] != "admin": raise HTTPException(403, "仅主管(admin)可发布")
    for r in db.query(ScreeningResult).filter_by(run_id=rid).all(): r.published = True
    db.commit()
    return {"ok": True}

# ---------- 基金详情 ----------
@app.get("/api/funds/{code}")
def fund_detail(code: str, user=Depends(current_user), db=Depends(get_db)):
    code = code.strip().zfill(6)
    name, hist = sources.em_fund_history(code)
    for d, nav in hist:
        if not db.query(NavHistory).filter_by(fund_code=code, date=d).first():
            db.add(NavHistory(fund_code=code, date=d, unit_nav=nav))
    db.commit()
    series = [{"date": str(d), "nav": n} for d, n in hist]
    met = {}
    try:
        m = jobmod._fund_metrics(code)
        if m: met = m
    except Exception: pass
    def period(days):
        if len(hist) > days: return round((hist[-1][1] / hist[-1 - days][1] - 1) * 100, 2)
        return None
    return {"code": code, "name": name, "latest_date": str(hist[-1][0]) if hist else None,
            "latest_nav": hist[-1][1] if hist else None,
            "returns": {"r1m": period(21), "r3m": period(63), "r6m": period(126), "r1y": period(252), "r3y": period(756)},
            "metrics": met, "series": series[-756:]}

# ---------- 行业与系统 ----------
@app.get("/api/industry")
def industry(user=Depends(current_user), db=Depends(get_db)):
    return jobmod.get_kv(db, "industry_sw", {"rows": [], "updated": None})

@app.post("/api/system/run-job")
def run_job(body: dict, user=Depends(current_user)):
    job = body.get("job")
    def _run():
        try:
            if job == "watch_update": jobmod.update_watchlist()
            elif job == "market_regime": jobmod.update_market_regime()
            elif job == "industry_sw": jobmod.update_industry()
        except Exception: pass
    threading.Thread(target=_run, daemon=True).start()
    return {"started": True, "job": job}

@app.get("/api/system/status")
def system_status(user=Depends(current_user), db=Depends(get_db)):
    logs = db.query(JobLog).order_by(JobLog.id.desc()).limit(30).all()
    return {"jobs": [{"id": l.id, "job": l.job, "status": l.status, "started": str(l.started_at),
                      "finished": str(l.finished_at) if l.finished_at else None, "detail": l.detail} for l in logs],
            "sources": [
                {"name": "AkShare(主源)", "role": "基金排行/历史净值校验/申万行业", "note": "免费, 无SLA"},
                {"name": "东方财富直连", "role": "最新净值/历史净值/指数日线", "note": "免费, 无SLA"},
                {"name": "BaoStock", "role": "股票/指数校验(预留)", "note": "免费免注册"},
                {"name": "官方源", "role": "指数成分/行业分类季度校准(人工)", "note": "中证/申万/巨潮"},
            ], "algo_version": jobmod.ALGO_VERSION}

# ---------- 静态前端(镜像内文件, 避免宿主机文件权限问题) ----------
from fastapi.staticfiles import StaticFiles
_FRONTEND_DIR = os.getenv("FRONTEND_DIR", "/app/frontend")
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="static")
