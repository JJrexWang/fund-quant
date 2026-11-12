"""定时任务进程: 与 api 共用同一套代码与数据库。"""
import time, threading
from apscheduler.schedulers.blocking import BlockingScheduler
import jobs as jobmod

sched = BlockingScheduler(timezone="Asia/Shanghai")

@sched.scheduled_job("cron", day_of_week="mon-fri", hour=17, minute=40, id="market")
def market():
    try: jobmod.update_market_regime()
    except Exception: pass

@sched.scheduled_job("cron", day_of_week="mon-fri", hour=21, minute=35, id="watch")
def watch():
    try: jobmod.update_watchlist()
    except Exception: pass

@sched.scheduled_job("cron", day_of_week="sat", hour=9, minute=30, id="industry")
def industry():
    try: jobmod.update_industry()
    except Exception: pass

@sched.scheduled_job("cron", day_of_week="mon", hour=8, minute=30, id="screening")
def screening():
    try: jobmod.run_screening()
    except Exception: pass

def _startup():
    time.sleep(20)
    for fn in (jobmod.update_market_regime, jobmod.update_watchlist, jobmod.update_industry):
        try: fn()
        except Exception: pass

if __name__ == "__main__":
    threading.Thread(target=_startup, daemon=True).start()
    sched.start()
