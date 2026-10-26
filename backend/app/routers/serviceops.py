"""Phase 3: SLA business calendar & holidays, escalation rules, assignment policies (round robin / least loaded / on-call), on-call rota."""
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Record, Group, User, now
from ..security import staff, admin_only, current_user
from .. import settings_store, audit, bus, registry

router = APIRouter(prefix="/api/service-ops", tags=["service-ops"])
CAL_DEFAULT = {"enabled": False, "tz_offset_min": 330, "days": [0, 1, 2, 3, 4], "start": "09:00", "end": "18:00", "holidays": []}
ESC_DEFAULT = {"warn_pct": 75, "bump_priority": True, "notify_admins": True}
POLICIES = ["manual", "round_robin", "least_loaded", "on_call"]

def _get(db, tid, key, default):
    v = settings_store.get(db, tid, key).get("v"); return {**default, **(v or {})} if isinstance(default, dict) else (v if v is not None else default)
def _put(db, tid, key, v): settings_store.put(db, tid, key, {"v": v})
def calendar(db, tid): return _get(db, tid, "sla.calendar", CAL_DEFAULT)
def escalation(db, tid): return _get(db, tid, "sla.escalation", ESC_DEFAULT)

def _hm(s): h, m = s.split(":"); return int(h) * 60 + int(m)

def add_business_minutes(start: datetime, minutes: float, cal: dict) -> datetime:
    """start is naive UTC. Walk through working windows in the calendar's local time."""
    off = timedelta(minutes=cal.get("tz_offset_min", 330)); cur = start + off; left = float(minutes)
    s_min, e_min = _hm(cal.get("start", "09:00")), _hm(cal.get("end", "18:00")); hol = set(cal.get("holidays") or []); days = set(cal.get("days") or [0, 1, 2, 3, 4])
    if e_min <= s_min or not days: return start + timedelta(minutes=minutes)
    for _ in range(800):
        day0 = datetime(cur.year, cur.month, cur.day); ws, we = day0 + timedelta(minutes=s_min), day0 + timedelta(minutes=e_min)
        if cur.weekday() in days and cur.date().isoformat() not in hol and cur < we:
            if cur < ws: cur = ws
            avail = (we - cur).total_seconds() / 60
            if left <= avail: return cur + timedelta(minutes=left) - off
            left -= avail
        cur = day0 + timedelta(days=1, minutes=s_min)
    return cur - off

class CalIn(BaseModel):
    enabled: bool = False; tz_offset_min: int = 330; days: list[int] = [0, 1, 2, 3, 4]; start: str = "09:00"; end: str = "18:00"; holidays: list[str] = []
class EscIn(BaseModel):
    warn_pct: int = 75; bump_priority: bool = True; notify_admins: bool = True
class PolIn(BaseModel):
    policies: dict[str, str]
class OnCallIn(BaseModel):
    group: str; user_id: int; start: str; end: str; note: str = ""

@router.get("/config")
def get_config(u=Depends(staff), db: Session = Depends(get_db)):
    return {"calendar": calendar(db, u.tenant_id), "escalation": escalation(db, u.tenant_id), "policies": _get(db, u.tenant_id, "assign.policies", {}),
            "policy_types": POLICIES, "oncall": _get(db, u.tenant_id, "oncall", []), "rr": _get(db, u.tenant_id, "assign.rr", {})}

@router.put("/calendar")
def put_calendar(b: CalIn, u=Depends(admin_only), db: Session = Depends(get_db)):
    try:
        if _hm(b.end) <= _hm(b.start): raise ValueError
        [date.fromisoformat(h) for h in b.holidays]
    except (ValueError, IndexError): raise HTTPException(400, "Please check the working hours and holiday dates (YYYY-MM-DD).")
    if any(d < 0 or d > 6 for d in b.days): raise HTTPException(400, "Days are 0 (Mon) to 6 (Sun).")
    _put(db, u.tenant_id, "sla.calendar", {**b.model_dump(), "holidays": sorted(set(b.holidays))}); audit.log(db, u.id, "update", "sla.calendar", 0); db.commit(); return calendar(db, u.tenant_id)

@router.put("/escalation")
def put_escalation(b: EscIn, u=Depends(admin_only), db: Session = Depends(get_db)):
    if not 1 <= b.warn_pct <= 99: raise HTTPException(400, "Warn at between 1% and 99% of the SLA.")
    _put(db, u.tenant_id, "sla.escalation", b.model_dump()); audit.log(db, u.id, "update", "sla.escalation", 0); db.commit(); return escalation(db, u.tenant_id)

@router.put("/policies")
def put_policies(b: PolIn, u=Depends(admin_only), db: Session = Depends(get_db)):
    names = {g.name for g in db.scalars(select(Group).where(Group.tenant_id == u.tenant_id))}
    for g, p in b.policies.items():
        if g not in names: raise HTTPException(400, f"Unknown group: {g}")
        if p not in POLICIES: raise HTTPException(400, f"Unknown policy: {p}")
    _put(db, u.tenant_id, "assign.policies", b.policies); audit.log(db, u.id, "update", "assign.policies", 0, b.policies); db.commit(); return b.policies

@router.post("/oncall", status_code=201)
def add_oncall(b: OnCallIn, u=Depends(admin_only), db: Session = Depends(get_db)):
    try: s, e = datetime.fromisoformat(b.start), datetime.fromisoformat(b.end)
    except ValueError: raise HTTPException(400, "Please use dates like 2026-10-26T09:00.")
    if e <= s: raise HTTPException(400, "The shift must end after it starts.")
    usr = db.get(User, b.user_id)
    if not usr or usr.tenant_id != u.tenant_id: raise HTTPException(400, "Unknown person.")
    rota = _get(db, u.tenant_id, "oncall", []); nid = max([x["id"] for x in rota] or [0]) + 1
    rota = [*rota, {"id": nid, **b.model_dump(), "name": usr.full_name}]; _put(db, u.tenant_id, "oncall", rota); audit.log(db, u.id, "create", "oncall", nid); db.commit(); return rota

@router.delete("/oncall/{sid}")
def del_oncall(sid: int, u=Depends(admin_only), db: Session = Depends(get_db)):
    rota = [x for x in _get(db, u.tenant_id, "oncall", []) if x["id"] != sid]; _put(db, u.tenant_id, "oncall", rota); db.commit(); return rota

def on_call_now(db, tid, group, at=None):
    """`at` and shift times are local (calendar tz)."""
    at = at or (now() + timedelta(minutes=calendar(db, tid).get("tz_offset_min", 330)))
    for x in _get(db, tid, "oncall", []):
        if x["group"] == group and datetime.fromisoformat(x["start"]) <= at < datetime.fromisoformat(x["end"]): return x
    return None

@router.get("/oncall/now")
def oncall_now(group: str | None = None, u=Depends(current_user), db: Session = Depends(get_db)):
    groups = [group] if group else [g.name for g in db.scalars(select(Group).where(Group.tenant_id == u.tenant_id))]
    return {g: on_call_now(db, u.tenant_id, g) for g in groups}

def pick_assignee(db, r):
    if not r.assignment_group_id or r.assignee_id: return None
    g = db.get(Group, r.assignment_group_id); pol = _get(db, r.tenant_id, "assign.policies", {}).get(g.name if g else "", "manual")
    if pol == "manual": return None
    members = db.scalars(select(User).where(User.tenant_id == r.tenant_id, User.group_id == g.id, User.active == True, User.role != "end_user").order_by(User.id)).all()
    if pol == "on_call":
        x = on_call_now(db, r.tenant_id, g.name); return db.get(User, x["user_id"]) if x else None
    if not members: return None
    if pol == "round_robin":
        rr = _get(db, r.tenant_id, "assign.rr", {}); last = rr.get(g.name)
        ids = [m.id for m in members]; nxt = ids[(ids.index(last) + 1) % len(ids)] if last in ids else ids[0]
        _put(db, r.tenant_id, "assign.rr", {**rr, g.name: nxt}); return db.get(User, nxt)
    if pol == "least_loaded":
        load = dict(db.execute(select(Record.assignee_id, func.count()).where(Record.tenant_id == r.tenant_id, Record.assignee_id.in_([m.id for m in members]),
                    Record.state.not_in(list(registry.CLOSED))).group_by(Record.assignee_id)).all())
        return min(members, key=lambda m: (load.get(m.id, 0), m.id))
    return None

@bus.subscribe
def auto_assign(db, r, event, actor, changes=None):
    if event not in ("created", "updated") or r.assignee_id: return
    if event == "updated" and "assignment_group_id" not in (changes or {}): return
    try:
        u = pick_assignee(db, r)
        if u:
            r.assignee_id = u.id; db.flush(); audit.log(db, None, "auto_assign", r.module, r.number, {"to": u.full_name})
    except Exception:
        import logging; logging.exception("auto-assign failed")

@router.post("/preview-due")
def preview_due(minutes: int = 240, u=Depends(staff), db: Session = Depends(get_db)):
    cal = calendar(db, u.tenant_id); t = now()
    return {"from": t, "wall_clock": t + timedelta(minutes=minutes), "business": add_business_minutes(t, minutes, cal) if cal["enabled"] else t + timedelta(minutes=minutes)}
