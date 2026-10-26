from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import SLAPolicy, Record, now

DEFAULTS = {"P1": (15, 240), "P2": (30, 480), "P3": (240, 1440), "P4": (480, 4320)}
from .registry import CLOSED

def apply_sla(db: Session, r: Record):
    pol = db.scalar(select(SLAPolicy).where(SLAPolicy.tenant_id == (r.tenant_id or 1), SLAPolicy.module == r.module, SLAPolicy.priority == r.priority, SLAPolicy.active == True))
    resp, res = (pol.response_minutes, pol.resolution_minutes) if pol else DEFAULTS.get(r.priority, (240, 1440))
    base = r.created_at or now()
    from .routers.serviceops import calendar, add_business_minutes
    cal = calendar(db, r.tenant_id or 1)
    if cal.get("enabled"):
        r.response_due_at = add_business_minutes(base, resp, cal); r.sla_due_at = add_business_minutes(base, res, cal)
    else:
        r.response_due_at = base + timedelta(minutes=resp)
        r.sla_due_at = base + timedelta(minutes=res)

def refresh_breaches(db: Session, tenant_id=None):
    t = now(); n = 0
    q = select(Record).where(Record.sla_due_at != None, Record.sla_breached == False)
    if tenant_id: q = q.where(Record.tenant_id == tenant_id)
    for r in db.scalars(q):
        end = r.resolved_at if r.state in CLOSED and r.resolved_at else (None if r.state in CLOSED else t)
        if end and end > r.sla_due_at:
            r.sla_breached = True; n += 1
    db.commit()
    return n

def sla_status(r: Record, warn_pct: int = 75):
    if r.sla_breached: return "breached"
    if not r.sla_due_at or r.state in CLOSED: return "met" if (r.state in CLOSED and r.sla_due_at) else "none"
    total = (r.sla_due_at - r.created_at).total_seconds() or 1
    left = (r.sla_due_at - now()).total_seconds()
    if left < 0: return "breached"
    return "at_risk" if left / total < (1 - warn_pct / 100) else "on_track"

BUMP = {"P4": "P3", "P3": "P2", "P2": "P1", "P1": "P1"}

def escalate(db: Session, tenant_id=None):
    """SLA Assist-style proactive SLA engine: warn at-risk, escalate breaches (notify + priority bump). Idempotent per level."""
    from .deps import notify, link_for
    from .models import User
    refresh_breaches(db, tenant_id)
    q = select(Record).where(Record.sla_due_at != None, Record.state.not_in(CLOSED))
    if tenant_id: q = q.where(Record.tenant_id == tenant_id)
    warned = escalated = 0
    for r in db.scalars(q):
        from .routers.serviceops import escalation
        esc = escalation(db, r.tenant_id); st = sla_status(r, esc.get("warn_pct", 75)); lvl = (r.data or {}).get("escalation_level", 0)
        if st == "at_risk" and lvl < 1:
            notify(db, r.tenant_id, f"SLA at risk: {r.number} {r.title}", "sla_warning", r.assignee_id, r.assignment_group_id, link_for(r))
            r.data = {**r.data, "escalation_level": 1}; warned += 1
            from . import bus; bus.emit(db, r, "sla_warning", None, {})
        elif st == "breached" and lvl < 2:
            for a in (db.scalars(select(User).where(User.tenant_id == r.tenant_id, User.role == "admin", User.active == True)) if esc.get("notify_admins", True) else []):
                notify(db, r.tenant_id, f"SLA BREACHED: {r.number} escalated", "escalation", a.id, None, link_for(r))
            notify(db, r.tenant_id, f"SLA breached: {r.number} {r.title}", "sla_breach", r.assignee_id, r.assignment_group_id, link_for(r))
            r.data = {**r.data, "escalation_level": 2, "escalated_from": r.priority}
            if esc.get("bump_priority", True) and r.module in ("incident", "case", "sec_incident"): r.priority = BUMP.get(r.priority, r.priority)
            escalated += 1
            from . import bus; bus.emit(db, r, "sla_breach", None, {})
    db.commit()
    return {"warned": warned, "escalated": escalated}
