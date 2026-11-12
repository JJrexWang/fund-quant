from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, Text, UniqueConstraint
from sqlalchemy.sql import func
from db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="manager")  # admin / manager / viewer
    created_at = Column(DateTime, server_default=func.now())

class WatchRecord(Base):
    __tablename__ = "watch_records"
    id = Column(Integer, primary_key=True)
    owner = Column(String(64), default="admin")
    fund_code = Column(String(6), nullable=False, index=True)
    fund_name = Column(String(128), default="")
    sale_date = Column(Date, nullable=False)
    sale_nav = Column(Float, nullable=False)
    target_pct = Column(Float, default=5.0)
    manager = Column(String(64), default="")
    note = Column(String(256), default="")
    latest_date = Column(Date)
    latest_nav = Column(Float)
    latest_cum_nav = Column(Float)
    daily_pct = Column(Float)
    ret_pct = Column(Float)
    status = Column(String(32), default="tracking")  # tracking / hit / warn_down
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    watch_id = Column(Integer, index=True)
    fund_code = Column(String(6))
    fund_name = Column(String(128), default="")
    triggered_date = Column(Date)
    ret_pct = Column(Float)
    nav = Column(Float)
    contacted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

class NavHistory(Base):
    __tablename__ = "nav_history"
    id = Column(Integer, primary_key=True)
    fund_code = Column(String(6), index=True)
    date = Column(Date, index=True)
    unit_nav = Column(Float)
    cum_nav = Column(Float)
    daily_pct = Column(Float)
    source = Column(String(32), default="eastmoney")
    __table_args__ = (UniqueConstraint("fund_code", "date", name="uq_nav_code_date"),)

class AgencyPool(Base):
    __tablename__ = "agency_pool"
    id = Column(Integer, primary_key=True)
    batch = Column(String(64), default="default")
    fund_code = Column(String(6), index=True)
    fund_name = Column(String(128), default="")
    fund_type = Column(String(32), default="")
    risk_level = Column(String(8), default="")
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("batch", "fund_code", name="uq_pool_batch_code"),)

class ScreeningRun(Base):
    __tablename__ = "screening_runs"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime)
    regime = Column(String(16), default="均衡")
    weights = Column(Text, default="{}")
    universe_count = Column(Integer, default=0)
    pool_count = Column(Integer, default=0)
    status = Column(String(16), default="running")  # running/done/failed
    note = Column(Text, default="")

class ScreeningResult(Base):
    __tablename__ = "screening_results"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, index=True)
    fund_code = Column(String(6))
    fund_name = Column(String(128), default="")
    fund_type = Column(String(32), default="")
    score = Column(Float)
    persist = Column(Float)
    risk_adj = Column(Float)
    dd_score = Column(Float)
    momentum = Column(Float)
    long_score = Column(Float)
    max_dd = Column(Float)
    sharpe = Column(Float)
    calmar = Column(Float)
    r1m = Column(Float); r3m = Column(Float); r1y = Column(Float); r3y = Column(Float)
    risk_tag = Column(String(128), default="正常")
    reason = Column(Text, default="")
    published = Column(Boolean, default=False)

class JobLog(Base):
    __tablename__ = "job_logs"
    id = Column(Integer, primary_key=True)
    job = Column(String(48), index=True)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime)
    status = Column(String(16), default="running")
    detail = Column(Text, default="")

class KV(Base):
    __tablename__ = "kv_cache"
    key = Column(String(64), primary_key=True)
    value = Column(Text, default="{}")
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())
