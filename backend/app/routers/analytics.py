"""Phase 8: analytics. Explore (filter + group), pivot (two dimensions), report templates, a saved
report library, boards (dashboards made of saved reports) and CSV export. Counts and durations only, never money."""
import csv, io, uuid
from collections import Counter, defaultdict
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Record, now
from ..security import staff
from .. import audit, registry, settings_store

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
DIMS = ["priority", "state", "category", "assignment_group", "assignee", "requester", "month", "week", "day", "sla_breached"]
METRICS = ["count", "avg_age_hours", "breached_pct", "open"]

class Spec(BaseModel):
    module: str = "incident"; days: int = Field(30, ge=1, le=730)
    rows: str = "priority"; cols: str | None = None; metric: str = "count"
    filter: dict = {}; chart: str = "bar"

def _key(r, g):
    if g == "assignment_group": return r.assignment_group.name if r.assignment_group else "Unassigned"
    if g == "assignee": return r.assignee.full_name if r.assignee else "Unassigned"
    if g == "requester": return r.requester.full_name if getattr(r, "requester", None) else "Unknown"
    if g == "month": return r.created_at.strftime("%Y-%m")
    if g == "week": return r.created_at.strftime("%G-W%V")
    if g == "day": return r.created_at.strftime("%Y-%m-%d")
    if g == "sla_breached": return "Breached" if r.sla_breached else "Within SLA"
    return str(getattr(r, g, None) or "none")

def _metric(rs, m):
    if m == "count": return len(rs)
    if m == "open": return sum(1 for r in rs if r.state not in registry.CLOSED)
    if m == "breached_pct": return round(100 * sum(1 for r in rs if r.sla_breached) / len(rs), 1) if rs else 0
    t = now().replace(tzinfo=None); ages = [((r.resolved_at or t).replace(tzinfo=None) - r.created_at.replace(tzinfo=None)).total_seconds() / 3600 for r in rs if r.created_at] if rs else []
    return round(sum(ages) / len(ages), 1) if ages else 0

def run(db, u, s: Spec):
    if s.module not in registry.MODULES: raise HTTPException(400, "Unknown module")
    if s.rows not in DIMS or (s.cols and s.cols not in DIMS): raise HTTPException(400, "Unknown dimension")
    if s.metric not in METRICS: raise HTTPException(400, "Unknown measure")
    since = (now() - timedelta(days=s.days)).replace(tzinfo=None)
    rs = [r for r in db.scalars(select(Record).where(Record.tenant_id == u.tenant_id, Record.module == s.module)) if r.created_at and r.created_at.replace(tzinfo=None) >= since]
    f = s.filter or {}
    for k in ("priority", "state", "category"):
        if f.get(k): rs = [r for r in rs if str(getattr(r, k)) == str(f[k])]
    if f.get("open"): rs = [r for r in rs if r.state not in registry.CLOSED]
    if f.get("breached"): rs = [r for r in rs if r.sla_breached]
    if f.get("text"): rs = [r for r in rs if f["text"].lower() in (r.title or "").lower()]
    time = s.rows in ("month", "week", "day")
    by = defaultdict(list)
    for r in rs: by[_key(r, s.rows)].append(r)
    order = sorted(by) if time else sorted(by, key=lambda k: -len(by[k]))
    out = {"spec": s.model_dump(), "total": len(rs), "rows": [{"label": k, "value": _metric(by[k], s.metric)} for k in order]}
    if s.cols:
        colk = Counter(_key(r, s.cols) for r in rs); cols = sorted(colk) if s.cols in ("month", "week", "day") else [c for c, _ in colk.most_common()]
        cell = defaultdict(list)
        for r in rs: cell[(_key(r, s.rows), _key(r, s.cols))].append(r)
        out["columns"] = cols
        out["matrix"] = [{"label": k, **{c: _metric(cell[(k, c)], s.metric) for c in cols}, "_total": _metric(by[k], s.metric)} for k in order]
    out["records"] = [{"id": r.id, "number": r.number, "title": r.title, "state": r.state, "priority": r.priority} for r in rs[:200]]
    return out

@router.get("/meta")
def meta(u=Depends(staff)):
    return {"modules": [{"key": k, "label": m["label"]} for k, m in registry.MODULES.items()], "dimensions": DIMS, "metrics": METRICS}

@router.post("/explore")
def explore(s: Spec, db: Session = Depends(get_db), u=Depends(staff)): return run(db, u, s)

def _csv(res):
    buf = io.StringIO(); w = csv.writer(buf)
    if "matrix" in res:
        w.writerow([res["spec"]["rows"], *res["columns"], "Total"])
        for m in res["matrix"]: w.writerow([m["label"], *[m[c] for c in res["columns"]], m["_total"]])
    else:
        w.writerow([res["spec"]["rows"], res["spec"]["metric"]])
        for r in res["rows"]: w.writerow([r["label"], r["value"]])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="servicedesk-report.csv"'})

@router.post("/explore.csv")
def explore_csv(s: Spec, db: Session = Depends(get_db), u=Depends(staff)): return _csv(run(db, u, s))

TEMPLATES = [
    {"id": "t-inc-priority", "name": "Open incidents by priority", "spec": {"module": "incident", "rows": "priority", "filter": {"open": True}, "days": 90}},
    {"id": "t-inc-trend", "name": "Incident volume by week", "spec": {"module": "incident", "rows": "week", "days": 90, "chart": "line"}},
    {"id": "t-team-sla", "name": "SLA breaches by team", "spec": {"module": "incident", "rows": "assignment_group", "metric": "breached_pct", "days": 90}},
    {"id": "t-age", "name": "Average age by priority (hours)", "spec": {"module": "incident", "rows": "priority", "metric": "avg_age_hours", "days": 90}},
    {"id": "t-req-state", "name": "Requests by state", "spec": {"module": "request", "rows": "state", "days": 90, "chart": "pie"}},
    {"id": "t-pivot", "name": "Incidents: team × priority", "spec": {"module": "incident", "rows": "assignment_group", "cols": "priority", "days": 90, "chart": "table"}},
    {"id": "t-chg", "name": "Changes by month", "spec": {"module": "change", "rows": "month", "days": 365, "chart": "line"}},
]

@router.get("/templates")
def templates(u=Depends(staff)): return TEMPLATES

class Saved(BaseModel):
    name: str = Field(min_length=1, max_length=120); spec: Spec; shared: bool = True

def _lib(db, u): return settings_store.get(db, u.tenant_id, "analytics.reports").get("v") or []

@router.get("/reports")
def reports(db: Session = Depends(get_db), u=Depends(staff)): return [r for r in _lib(db, u) if r["shared"] or r["owner"] == u.id]

@router.post("/reports", status_code=201)
def save_report(b: Saved, db: Session = Depends(get_db), u=Depends(staff)):
    run(db, u, b.spec)  # validate
    r = {"id": uuid.uuid4().hex[:10], "name": b.name, "spec": b.spec.model_dump(), "shared": b.shared, "owner": u.id, "owner_name": u.full_name, "created": now().isoformat()[:16]}
    settings_store.put(db, u.tenant_id, "analytics.reports", {"v": _lib(db, u) + [r]}); audit.log(db, u.id, "report_save", "report", r["id"], {"name": b.name}); db.commit(); return r

def _own(db, u, lib, rid):
    r = next((x for x in lib if x["id"] == rid), None)
    if not r: raise HTTPException(404, "Report not found")
    if r["owner"] != u.id and u.role != "admin": raise HTTPException(403, "Only the owner or an admin can change this")
    return r

@router.delete("/reports/{rid}")
def delete_report(rid: str, db: Session = Depends(get_db), u=Depends(staff)):
    lib = _lib(db, u); _own(db, u, lib, rid)
    settings_store.put(db, u.tenant_id, "analytics.reports", {"v": [x for x in lib if x["id"] != rid]})
    bs = _boards(db, u)
    for b in bs: b["widgets"] = [w for w in b["widgets"] if w["report"] != rid]
    settings_store.put(db, u.tenant_id, "analytics.boards", {"v": bs}); db.commit(); return {"ok": True}

@router.get("/reports/{rid}/run")
def run_report(rid: str, db: Session = Depends(get_db), u=Depends(staff)):
    r = next((x for x in reports(db, u) if x["id"] == rid), None)
    if not r: raise HTTPException(404, "Report not found")
    return {"report": r, **run(db, u, Spec(**r["spec"]))}

@router.get("/reports/{rid}/csv")
def report_csv(rid: str, db: Session = Depends(get_db), u=Depends(staff)):
    r = next((x for x in reports(db, u) if x["id"] == rid), None)
    if not r: raise HTTPException(404, "Report not found")
    return _csv(run(db, u, Spec(**r["spec"])))

class Board(BaseModel):
    name: str = Field(min_length=1, max_length=120); widgets: list[dict] = []; shared: bool = True

def _boards(db, u): return settings_store.get(db, u.tenant_id, "analytics.boards").get("v") or []

@router.get("/boards")
def boards(db: Session = Depends(get_db), u=Depends(staff)): return [b for b in _boards(db, u) if b["shared"] or b["owner"] == u.id]

def _clean(db, u, ws):
    ids = {r["id"] for r in reports(db, u)}
    return [{"report": w["report"], "size": w.get("size", "half") if w.get("size") in ("half", "full") else "half"} for w in ws if w.get("report") in ids][:12]

@router.post("/boards", status_code=201)
def create_board(b: Board, db: Session = Depends(get_db), u=Depends(staff)):
    x = {"id": uuid.uuid4().hex[:10], "name": b.name, "widgets": _clean(db, u, b.widgets), "shared": b.shared, "owner": u.id, "owner_name": u.full_name}
    settings_store.put(db, u.tenant_id, "analytics.boards", {"v": _boards(db, u) + [x]}); db.commit(); return x

@router.put("/boards/{bid}")
def update_board(bid: str, b: Board, db: Session = Depends(get_db), u=Depends(staff)):
    bs = _boards(db, u); x = _own(db, u, bs, bid)
    x.update(name=b.name, widgets=_clean(db, u, b.widgets), shared=b.shared)
    settings_store.put(db, u.tenant_id, "analytics.boards", {"v": bs}); db.commit(); return x

@router.delete("/boards/{bid}")
def delete_board(bid: str, db: Session = Depends(get_db), u=Depends(staff)):
    bs = _boards(db, u); _own(db, u, bs, bid)
    settings_store.put(db, u.tenant_id, "analytics.boards", {"v": [x for x in bs if x["id"] != bid]}); db.commit(); return {"ok": True}

@router.get("/boards/{bid}")
def board(bid: str, db: Session = Depends(get_db), u=Depends(staff)):
    b = next((x for x in boards(db, u) if x["id"] == bid), None)
    if not b: raise HTTPException(404, "Board not found")
    lib = {r["id"]: r for r in reports(db, u)}
    return {**b, "widgets": [{**w, "report": lib[w["report"]], "data": run(db, u, Spec(**lib[w["report"]]["spec"]))} for w in b["widgets"] if w["report"] in lib]}
