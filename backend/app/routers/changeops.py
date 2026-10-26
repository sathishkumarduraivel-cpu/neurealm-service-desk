"""Phase 5: change enablement (risk questionnaire, approval routes, CAB, calendar, freeze windows, pipeline, PIR),
problem management (RCA, trends) and the major incident console."""
from collections import Counter
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Record, Approval, Comment, now
from ..security import current_user, staff, admin_only
from ..deps import get_record, notify, link_for, out
from .. import audit, settings_store, bus, hooks

router = APIRouter(prefix="/api", tags=["change-ops"])

QUESTIONS = [
    {"key": "prod", "label": "Does it touch production?", "weight": 20},
    {"key": "users", "label": "Will users notice downtime?", "weight": 20},
    {"key": "untested", "label": "Has it NOT been tested in staging?", "weight": 20},
    {"key": "no_rollback", "label": "Is there NO tested rollback plan?", "weight": 20},
    {"key": "first_time", "label": "Is this the first time we've made this kind of change?", "weight": 10},
    {"key": "vendor", "label": "Does it depend on an outside vendor?", "weight": 10},
]
DEFAULT_ROUTES = {"standard": {"low": [], "moderate": [], "high": ["admin"]},
                  "normal": {"low": ["admin"], "moderate": ["group:CAB"], "high": ["group:CAB", "admin"]},
                  "emergency": {"low": ["admin"], "moderate": ["admin"], "high": ["admin"]}}

def questionnaire_score(ans: dict) -> int:
    return sum(q["weight"] for q in QUESTIONS if ans.get(q["key"]))

def _g(db, tid, key, default): v = settings_store.get(db, tid, key).get("v"); return default if v is None else v
def _p(db, tid, key, v): settings_store.put(db, tid, key, {"v": v})

def _dt(s):
    if not s: return None
    try: return datetime.fromisoformat(str(s).replace("Z", "")[:19])
    except ValueError: return None

def freeze_hit(db, tid, start, end=None):
    s, e = _dt(start), _dt(end) or (_dt(start) + timedelta(hours=1) if _dt(start) else None)
    if not s: return None
    for f in _g(db, tid, "change.freeze", []):
        fs, fe = _dt(f["start"]), _dt(f["end"])
        if fs and fe and s < fe and fs < e: return f
    return None

# ---------- hooks used by main.py ----------
def start_approvals(db, r):
    from .portal import _approver
    routes = _g(db, r.tenant_id, "change.routes", DEFAULT_ROUTES)
    ctype = r.data.get("change_type", "normal"); lvl = r.data.get("risk_level", "low")
    specs = (routes.get(ctype) or routes["normal"]).get(lvl, ["admin"]) or ["admin"]
    r.approvals.clear()
    for i, spec in enumerate(specs, 1):
        a = _approver(db, r.tenant_id, spec) or _approver(db, r.tenant_id, "admin")
        r.approvals.append(Approval(level=i, approver_id=a.id if a else None, comment=f"Route: {spec}"))

def guard(db, r, ns):
    """Called before a change moves state. Raises if the move breaks the rules."""
    if r.module != "change": return
    if ns == "implement":
        if r.approvals and not all(a.state == "approved" for a in r.approvals):
            raise HTTPException(400, "This change can't start until every approval is in.")
        if r.data.get("change_type") != "emergency":
            f = freeze_hit(db, r.tenant_id, now().isoformat(), (now() + timedelta(minutes=1)).isoformat())
            if f: raise HTTPException(400, f"We're in the change freeze “{f['name']}”. Only emergency changes can start now.")
    if ns == "closed" and not r.data.get("pir"):
        raise HTTPException(400, "Please add a post-implementation review before closing.")

def check_schedule(db, r):
    if r.module != "change" or r.data.get("change_type") == "emergency": return
    f = freeze_hit(db, r.tenant_id, r.data.get("planned_start"), r.data.get("planned_end"))
    if f: raise HTTPException(400, f"That time falls inside the change freeze “{f['name']}” ({f['start'][:10]} to {f['end'][:10]}). Please pick another slot.")

# ---------- config ----------
class Freeze(BaseModel):
    name: str; start: str; end: str; reason: str = ""

@router.get("/change-ops/config")
def get_config(u=Depends(staff), db: Session = Depends(get_db)):
    return {"questions": QUESTIONS, "routes": _g(db, u.tenant_id, "change.routes", DEFAULT_ROUTES), "freeze": _g(db, u.tenant_id, "change.freeze", [])}

@router.put("/change-ops/routes")
def put_routes(b: dict, u=Depends(admin_only), db: Session = Depends(get_db)):
    for t, lv in b.items():
        if t not in DEFAULT_ROUTES or not isinstance(lv, dict): raise HTTPException(400, f"Unknown change type {t}")
        for k, specs in lv.items():
            if k not in ("low", "moderate", "high"): raise HTTPException(400, f"Unknown risk level {k}")
            for s in specs:
                if not (s == "admin" or str(s).startswith(("group:", "user:"))): raise HTTPException(400, f"Unknown approver “{s}”")
    _p(db, u.tenant_id, "change.routes", b); audit.log(db, u.id, "update", "change_routes", None); db.commit(); return b

@router.put("/change-ops/freeze")
def put_freeze(b: list[Freeze], u=Depends(admin_only), db: Session = Depends(get_db)):
    for f in b:
        if not _dt(f.start) or not _dt(f.end) or _dt(f.end) <= _dt(f.start): raise HTTPException(400, f"“{f.name}” needs an end after its start.")
    v = [f.model_dump() for f in b]; _p(db, u.tenant_id, "change.freeze", v); audit.log(db, u.id, "update", "change_freeze", None); db.commit(); return v

# ---------- risk ----------
@router.post("/changes/{rid}/risk")
def assess_risk(rid: int, b: dict, u=Depends(staff), db: Session = Depends(get_db)):
    r = get_record(db, "change", rid, u)
    ans = {q["key"]: bool(b.get(q["key"])) for q in QUESTIONS}
    r.data = {**r.data, "risk_answers": ans}; r.data.update(hooks.HOOKS["change"](r))
    audit.log(db, u.id, "risk", "change", r.number, {"score": r.data["risk_score"]}); db.commit()
    return {"risk_score": r.data["risk_score"], "risk_level": r.data["risk_level"]}

# ---------- calendar + pipeline ----------
def _ch(db, u): return db.scalars(select(Record).where(Record.tenant_id == u.tenant_id, Record.module == "change").order_by(Record.id)).all()
def _brief(r): return {"id": r.id, "number": r.number, "title": r.title, "state": r.state, "type": r.data.get("change_type"), "risk": r.data.get("risk_level"),
                       "start": r.data.get("planned_start"), "end": r.data.get("planned_end"), "ci": r.data.get("ci")}

@router.get("/change-ops/calendar")
def calendar(u=Depends(staff), db: Session = Depends(get_db)):
    rows = [_brief(r) for r in _ch(db, u) if r.data.get("planned_start")]
    clashes = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if a["ci"] and a["ci"] == b["ci"] and _dt(a["start"]) and _dt(b["start"]) and abs((_dt(a["start"]) - _dt(b["start"])).total_seconds()) < 4 * 3600:
                clashes.append([a["number"], b["number"]])
    return {"changes": rows, "freeze": _g(db, u.tenant_id, "change.freeze", []), "clashes": clashes}

PIPE = ["new", "assess", "authorize", "scheduled", "implement", "review", "closed"]
@router.get("/change-ops/pipeline")
def pipeline(u=Depends(staff), db: Session = Depends(get_db)):
    cols = {s: [] for s in PIPE}
    for r in _ch(db, u):
        if r.state in cols: cols[r.state].append(_brief(r))
    return [{"state": s, "items": cols[s]} for s in PIPE]

# ---------- CAB ----------
class Meeting(BaseModel):
    title: str; date: str; change_ids: list[int] = []; minutes: str = ""; decisions: dict = {}

@router.get("/change-ops/cab")
def cab_list(u=Depends(staff), db: Session = Depends(get_db)):
    ms = _g(db, u.tenant_id, "cab.meetings", [])
    agenda = [_brief(r) for r in _ch(db, u) if r.state == "authorize"]
    return {"meetings": sorted(ms, key=lambda m: m["date"], reverse=True), "suggested_agenda": agenda}

@router.post("/change-ops/cab", status_code=201)
def cab_save(b: Meeting, mid: int | None = None, u=Depends(staff), db: Session = Depends(get_db)):
    if not b.title.strip() or not _dt(b.date): raise HTTPException(400, "A meeting needs a title and a date.")
    ms = _g(db, u.tenant_id, "cab.meetings", [])
    if mid:
        m = next((m for m in ms if m["id"] == mid), None)
        if not m: raise HTTPException(404, "Not found")
        m.update(b.model_dump())
    else:
        m = {"id": max([x["id"] for x in ms] or [0]) + 1, **b.model_dump()}; ms.append(m)
    _p(db, u.tenant_id, "cab.meetings", ms); audit.log(db, u.id, "cab", "cab_meeting", m["id"]); db.commit(); return m

# ---------- PIR ----------
class PIR(BaseModel):
    successful: bool; notes: str = ""; lessons: str = ""; caused_incident: bool = False

@router.post("/changes/{rid}/pir")
def pir(rid: int, b: PIR, u=Depends(staff), db: Session = Depends(get_db)):
    r = get_record(db, "change", rid, u)
    if r.state not in ("review", "implement", "closed"): raise HTTPException(400, "Reviews happen after the change is implemented.")
    r.data = {**r.data, "pir": {**b.model_dump(), "by": u.full_name, "at": now().isoformat()}}
    audit.log(db, u.id, "pir", "change", r.number, {"successful": b.successful}); db.commit(); return out(r)

@router.get("/change-ops/stats")
def change_stats(u=Depends(staff), db: Session = Depends(get_db)):
    rs = _ch(db, u); pirs = [r.data["pir"] for r in rs if r.data.get("pir")]
    return {"total": len(rs), "by_type": dict(Counter(r.data.get("change_type", "normal") for r in rs)), "by_risk": dict(Counter(r.data.get("risk_level", "low") for r in rs)),
            "success_rate": round(100 * sum(p["successful"] for p in pirs) / len(pirs)) if pirs else None, "reviews": len(pirs)}

# ---------- problem ----------
class RCA(BaseModel):
    method: str = "5whys"; whys: list[str] = []; fishbone: dict[str, list[str]] = {}; root_cause: str = ""

@router.put("/problems/{rid}/rca")
def save_rca(rid: int, b: RCA, u=Depends(staff), db: Session = Depends(get_db)):
    r = get_record(db, "problem", rid, u)
    if b.method not in ("5whys", "fishbone"): raise HTTPException(400, "Method must be 5 whys or fishbone.")
    r.data = {**r.data, "rca": b.model_dump(), **({"root_cause": b.root_cause} if b.root_cause else {})}
    audit.log(db, u.id, "rca", "problem", r.number); db.commit(); return out(r)

@router.get("/problems/trends")
def trends(days: int = 30, u=Depends(staff), db: Session = Depends(get_db)):
    since = now() - timedelta(days=days)
    inc = db.scalars(select(Record).where(Record.tenant_id == u.tenant_id, Record.module == "incident")).all()
    recent = [r for r in inc if r.created_at and r.created_at.replace(tzinfo=None) >= since.replace(tzinfo=None)]
    linked = {i.id for p in db.scalars(select(Record).where(Record.tenant_id == u.tenant_id, Record.module == "problem")) for i in p.linked}
    by_cat = Counter(r.category for r in recent)
    words = Counter(w for r in recent for w in {w.strip(".,:()").lower() for w in r.title.split()} if len(w) > 4)
    clusters = []
    for cat, n in by_cat.most_common():
        if n < 3: continue
        ids = [r.id for r in recent if r.category == cat and r.id not in linked]
        if len(ids) >= 3: clusters.append({"category": cat, "count": n, "unlinked_ids": ids[:20], "suggestion": f"{len(ids)} {cat} incidents aren't linked to a problem yet. Worth a look?"})
    return {"days": days, "by_category": dict(by_cat.most_common(10)), "top_words": words.most_common(10), "clusters": clusters}

# ---------- major incident ----------
@router.post("/incidents/{rid}/major")
def declare_major(rid: int, b: dict, u=Depends(staff), db: Session = Depends(get_db)):
    r = get_record(db, "incident", rid, u); on = bool(b.get("declare", True))
    r.data = {**r.data, "major": on, "major_at": now().isoformat() if on else r.data.get("major_at"), "bridge": b.get("bridge", r.data.get("bridge", ""))}
    if on:
        r.priority = "P1"
        notify(db, r.tenant_id, f"Major incident declared: {r.number} {r.title}", "warning", None, None, link_for(r))
        db.add(Comment(record_id=r.id, author_id=u.id, body="Major incident declared. The bridge is open.", internal=True))
    audit.log(db, u.id, "major" if on else "major.off", "incident", r.number)
    bus.emit(db, r, "updated", u, {"data.major": [not on, on]}); db.commit(); return out(r)

class Comms(BaseModel):
    audience: str = "everyone"; message: str

@router.post("/incidents/{rid}/comms")
def post_comms(rid: int, b: Comms, u=Depends(staff), db: Session = Depends(get_db)):
    r = get_record(db, "incident", rid, u)
    if not r.data.get("major"): raise HTTPException(400, "Declare a major incident first.")
    if not b.message.strip(): raise HTTPException(400, "Please write an update.")
    c = list(r.data.get("comms", [])) + [{"at": now().isoformat(), "by": u.full_name, "audience": b.audience, "message": b.message[:2000]}]
    r.data = {**r.data, "comms": c}
    notify(db, r.tenant_id, f"Update on {r.number}: {b.message[:80]}", "info", r.requester_id, None, link_for(r))
    db.add(Comment(record_id=r.id, author_id=u.id, body=f"[Update to {b.audience}] {b.message}", internal=False))
    audit.log(db, u.id, "comms", "incident", r.number); db.commit(); return c

class Review(BaseModel):
    summary: str; root_cause: str = ""; actions: list[str] = []; problem: bool = False

@router.post("/incidents/{rid}/major-review")
def major_review(rid: int, b: Review, u=Depends(staff), db: Session = Depends(get_db)):
    r = get_record(db, "incident", rid, u)
    if not r.data.get("major"): raise HTTPException(400, "Only major incidents get a review.")
    r.data = {**r.data, "review": {**b.model_dump(), "by": u.full_name, "at": now().isoformat()}}
    pid = None
    if b.problem:
        from ..deps import next_number
        p = Record(tenant_id=r.tenant_id, module="problem", number=next_number(db, "problem"), title=f"Root cause of {r.number}: {r.title}"[:250], description=b.summary,
                   state="new", requester_id=u.id, data={"root_cause": b.root_cause}, priority=r.priority, impact=r.impact, urgency=r.urgency, category=r.category, ai_suggestion={}, created_at=now())
        db.add(p); db.flush(); p.linked = [r]; pid = p.id
    audit.log(db, u.id, "major.review", "incident", r.number); db.commit(); return {"ok": True, "problem_id": pid}

@router.get("/major-incidents")
def majors(u=Depends(staff), db: Session = Depends(get_db)):
    rs = [r for r in db.scalars(select(Record).where(Record.tenant_id == u.tenant_id, Record.module == "incident").order_by(Record.id.desc())) if r.data.get("major")]
    return [{"id": r.id, "number": r.number, "title": r.title, "state": r.state, "priority": r.priority, "since": r.data.get("major_at"), "bridge": r.data.get("bridge"),
             "updates": len(r.data.get("comms", [])), "reviewed": bool(r.data.get("review"))} for r in rs]
