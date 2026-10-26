"""Background jobs. APScheduler in-process by default; Celery worker optional (see celery_app.py).
Disable with APP_SCHEDULER=0 (tests do this)."""
import os, logging
from .db import SessionLocal
from . import sla

_sched = None

def sla_job():
    db = SessionLocal()
    try:
        res = sla.escalate(db)
        if res["warned"] or res["escalated"]: logging.info("SLA job: %s", res)
    finally:
        db.close()

def wf_job():
    db = SessionLocal()
    try:
        from . import flowengine
        flowengine.tick(db)
    except Exception: logging.exception("workflow tick failed")
    finally:
        db.close()

def start():
    global _sched
    if os.getenv("APP_SCHEDULER", "1") == "0" or _sched: return
    from apscheduler.schedulers.background import BackgroundScheduler
    _sched = BackgroundScheduler(daemon=True)
    _sched.add_job(sla_job, "interval", seconds=int(os.getenv("SLA_JOB_SECONDS", "60")), id="sla", max_instances=1, coalesce=True)
    _sched.add_job(wf_job, "interval", seconds=60, id="wf", max_instances=1, coalesce=True)
    _sched.start()

def stop():
    global _sched
    if _sched: _sched.shutdown(wait=False); _sched = None
