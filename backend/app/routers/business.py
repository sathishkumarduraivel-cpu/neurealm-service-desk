"""Phase C — CSM (entitlements, account 360, customer portal), HRSD lifecycle workflows, Workplace, Field Service dispatch."""
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Record, User, Group, now
from ..security import staff, current_user
from ..schemas import RecordCreate
from ..deps import scoped, get_or_404, out, notify, link_for
from .. import bus, audit, registry, sla

router = APIRouter(prefix="/api", tags=["business"])

def _by_number(db, tenant_id, module, number):
    return db.scalar(select(Record).where(Record.tenant_id == tenant_id, Record.module == module, Record.number == number)) if number else None

# ---------------- CSM ----------------
TIER_PRIORITY = {"24x7": "P2", "business_hours": "P3", "best_effort": "P4"}

@bus.subscribe
def case_entitlement(db, r, event, actor, changes):
    """On case creation: verify entitlement for the account, apply entitled SLA tier."""
    if r.module != "case" or event != "created": return
    acc = r.data.get("account")
    ent = db.scalar(select(Record).where(Record.tenant_id == r.tenant_id, Record.module == "entitlement", Record.state == "active").where(Record.data["account"].as_string() == acc)) if acc else None
    if ent:
        tier = ent.data.get("sla_tier", "best_effort"); r.data = {**r.data, "entitled": True, "entitlement": ent.number, "sla_tier": tier}
        if tier == "24x7" and r.priority in ("P3", "P4"): r.priority = "P2"
        sla.apply_sla(db, r)
    else:
        r.data = {**r.data, "entitled": False}
    g = db.scalar(select(Group).where(Group.tenant_id == r.tenant_id, Group.name == "Customer Support"))
    if g and not r.assignment_group_id: r.assignment_group_id = g.id

@router.get("/csm/accounts/{aid}/overview")
def account_overview(aid: int, db: Session = Depends(get_db), u=Depends(staff)):
    a = get_or_404(db, Record, aid, u)
    if a.module != "account": raise HTTPException(404)
    rel = lambda m: [r for r in db.scalars(scoped(select(Record), Record, u).where(Record.module == m)) if r.data.get("account") == a.number]
    cases = rel("case"); open_cases = [c for c in cases if c.state not in registry.CLOSED]
    breached = sum(c.sla_breached for c in cases)
    health = max(0, 100 - 10 * len(open_cases) - 15 * breached)
    return {"account": out(a), "contacts": [out(c) for c in rel("contact")], "cases": [out(c) for c in cases], "entitlements": [out(e) for e in rel("entitlement")],
            "health_score": health, "open_cases": len(open_cases)}

# ---------------- HRSD lifecycle ----------------
TEMPLATES = {
    "onboarding": [("Create AD / M365 account", "Service Desk"), ("Provision laptop", "Desktop Support"), ("Grant VPN & app access", "Network Ops"),
                   ("Allocate desk & ID badge", "Facilities"), ("Collect documents & sign policies", "HR Services"), ("Schedule induction", "HR Services")],
    "offboarding": [("Disable accounts & revoke access", "Service Desk"), ("Recover laptop & peripherals", "Desktop Support"), ("Revoke VPN", "Network Ops"),
                    ("Collect ID badge", "Facilities"), ("Final settlement & exit interview", "HR Services")],
}

class LifecycleIn(BaseModel):
    type: str; employee: str; date: str = ""; manager: str = ""; employee_email: str = ""

@router.post("/hr/lifecycle", status_code=201)
def lifecycle(body: LifecycleIn, db: Session = Depends(get_db), u=Depends(staff)):
    if body.type not in TEMPLATES: raise HTTPException(400, "type must be onboarding or offboarding")
    from ..main import create_record_core
    case = create_record_core(db, u, "hr_case", RecordCreate(title=f"{body.type.title()}: {body.employee}", description=f"{body.type.title()} for {body.employee} on {body.date or 'TBD'}",
                              data={"hr_category": body.type, "employee": body.employee, "lifecycle": body.type, "date": body.date, "manager": body.manager, "employee_email": body.employee_email.strip().lower()}))
    case.state = "in_progress"
    groups = {g.name: g.id for g in db.scalars(scoped(select(Group), Group, u))}
    for title, grp in TEMPLATES[body.type]:
        t = create_record_core(db, u, "task", RecordCreate(title=f"{title} — {body.employee}", assignment_group_id=groups.get(grp), data={"parent_number": case.number}), emit=False)
        t.parent_id = case.id
    db.commit(); db.refresh(case)
    return {"case": out(case), "tasks": len(TEMPLATES[body.type])}

@bus.subscribe
def close_parent_when_tasks_done(db, r, event, actor, changes):
    if r.module != "task" or event != "updated" or "state" not in changes or not r.parent_id: return
    db.flush()
    sibs = db.scalars(select(Record).where(Record.parent_id == r.parent_id)).all()
    if all(s.state in ("done", "cancelled") for s in sibs):
        p = db.get(Record, r.parent_id)
        if p.state not in registry.CLOSED:
            p.state = "resolved"; p.resolved_at = now()
            from .platform import offboard_deactivate
            offboard_deactivate(db, p, "updated", actor, {"state"})
            notify(db, p.tenant_id, f"{p.number} completed — all {len(sibs)} tasks done", "info", p.requester_id, None, link_for(p))

# ---------------- Workplace ----------------
SPACES = registry.MODULES["reservation"]["fields"][0]["options"]

@router.get("/workplace/availability")
def availability(day: str, db: Session = Depends(get_db), u=Depends(current_user)):
    rs = db.scalars(scoped(select(Record), Record, u).where(Record.module == "reservation", Record.state.in_(["confirmed", "checked_in"]))).all()
    out_ = []
    for sp in SPACES:
        bookings = sorted([{"number": r.number, "title": r.title, "start": r.data.get("start"), "end": r.data.get("end")} for r in rs if r.data.get("space") == sp and str(r.data.get("start", "")).startswith(day)], key=lambda b: b["start"])
        out_.append({"space": sp, "bookings": bookings, "free": not bookings})
    return out_

@router.get("/workplace/visitors/today")
def visitors_today(db: Session = Depends(get_db), u=Depends(staff)):
    d = now().date().isoformat()
    return [out(r) for r in db.scalars(scoped(select(Record), Record, u).where(Record.module == "visitor")) if r.data.get("visit_date") == d]

# ---------------- Field Service ----------------
def _techs(db, u):
    g = db.scalar(select(Group).where(Group.tenant_id == u.tenant_id, Group.name == "Field Services"))
    return db.scalars(select(User).where(User.tenant_id == u.tenant_id, User.group_id == (g.id if g else -1), User.active == True)).all()

def _slot(load_by_tech, tech_id, base: datetime, dur):
    """Next free slot for a technician, 09:00–18:00 working day, starting from base."""
    t = max(base, base.replace(hour=9, minute=0, second=0, microsecond=0))
    for (s, e) in sorted(load_by_tech[tech_id]):
        if t + timedelta(hours=dur) <= s: break
        t = max(t, e)
    if (t + timedelta(hours=dur)).hour > 18 or t.hour >= 18: t = (t + timedelta(days=1)).replace(hour=9, minute=0)
    return t

def dispatch_one(db, u, wo, techs, load):
    skill = wo.data.get("skill"); dur = float(wo.data.get("duration_h") or 2)
    cands = [t for t in techs if not skill or skill in (t.skills or [])] or techs
    if not cands: raise HTTPException(400, "No technicians available")
    base = now().replace(second=0, microsecond=0) + timedelta(hours=1)
    best = min(cands, key=lambda t: (_slot(load, t.id, base, dur), sum((e - s).total_seconds() for s, e in load[t.id])))
    start = _slot(load, best.id, base, dur); load[best.id].append((start, start + timedelta(hours=dur)))
    wo.assignee_id = best.id; wo.state = "scheduled"
    wo.data = {**wo.data, "technician": best.full_name, "scheduled_start": start.isoformat(timespec="minutes"), "skill_match": skill in (best.skills or []) if skill else True}
    notify(db, u.tenant_id, f"Work order {wo.number} scheduled {start:%d %b %H:%M}", "info", best.id, None, link_for(wo))
    return wo

def _load(db, u, techs):
    load = defaultdict(list)
    for w in db.scalars(scoped(select(Record), Record, u).where(Record.module == "work_order", Record.state.in_(["scheduled", "dispatched", "on_site"]))):
        if w.assignee_id and w.data.get("scheduled_start"):
            s = datetime.fromisoformat(w.data["scheduled_start"]); load[w.assignee_id].append((s, s + timedelta(hours=float(w.data.get("duration_h") or 2))))
    return load

@router.post("/fsm/dispatch/{wid}")
def dispatch(wid: int, db: Session = Depends(get_db), u=Depends(staff)):
    wo = get_or_404(db, Record, wid, u)
    if wo.module != "work_order": raise HTTPException(404)
    techs = _techs(db, u); dispatch_one(db, u, wo, techs, _load(db, u, techs))
    audit.log(db, u.id, "dispatch", "work_order", wo.number, {"tech": wo.data["technician"]}); db.commit()
    return out(wo)

@router.post("/fsm/optimize")
def optimize(db: Session = Depends(get_db), u=Depends(staff)):
    """Greedy optimiser: highest priority first, skill match, earliest feasible slot, balanced load."""
    techs = _techs(db, u); load = _load(db, u, techs)
    pending = sorted(db.scalars(scoped(select(Record), Record, u).where(Record.module == "work_order", Record.state == "new")).all(), key=lambda w: (w.priority, w.created_at))
    done = [dispatch_one(db, u, w, techs, load).number for w in pending]
    audit.log(db, u.id, "fsm_optimize", "work_order", "batch", {"count": len(done)}); db.commit()
    return {"scheduled": done}

@router.get("/fsm/board")
def board(db: Session = Depends(get_db), u=Depends(staff)):
    techs = _techs(db, u)
    wos = db.scalars(scoped(select(Record), Record, u).where(Record.module == "work_order")).all()
    return {"technicians": [{"id": t.id, "name": t.full_name, "skills": t.skills, "jobs": [out(w) for w in sorted(wos, key=lambda w: w.data.get("scheduled_start") or "") if w.assignee_id == t.id and w.state not in registry.CLOSED]} for t in techs],
            "unassigned": [out(w) for w in wos if w.state == "new"]}
