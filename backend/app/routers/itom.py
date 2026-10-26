"""Phase B — ITOM / ITAM: CMDB relationships & data quality, discovery import, event management, asset/licence/contract views, cost views."""
from collections import defaultdict, Counter
from datetime import timedelta, date
from statistics import mean
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Record, CIRelation, Event, CostRecord, now
from ..security import staff, current_user
from ..schemas import RecordCreate
from ..deps import scoped, next_number, get_or_404, out
from .. import hooks, audit, registry

router = APIRouter(prefix="/api", tags=["itom"])

# ---------------- CMDB ----------------
class RelIn(BaseModel):
    parent_id: int; child_id: int; rel_type: str = "depends_on"

def _cis(db, u):
    return db.scalars(scoped(select(Record), Record, u).where(Record.module == "ci")).all()

@router.post("/cmdb/relations", status_code=201)
def add_relation(body: RelIn, db: Session = Depends(get_db), u=Depends(staff)):
    p, c = get_or_404(db, Record, body.parent_id, u), get_or_404(db, Record, body.child_id, u)
    if p.module != "ci" or c.module != "ci" or p.id == c.id: raise HTTPException(400, "Relations link two different CIs")
    from .cmdbx import rel_types
    if body.rel_type not in {t["key"] for t in rel_types(db, u.tenant_id)}: raise HTTPException(400, f"Unknown relationship type “{body.rel_type}”")
    rel = CIRelation(tenant_id=u.tenant_id, parent_id=p.id, child_id=c.id, rel_type=body.rel_type); db.add(rel)
    audit.log(db, u.id, "relate", "ci", p.number, {"to": c.number, "type": body.rel_type}); db.commit()
    return {"id": rel.id}

@router.get("/cmdb/relations")
def relations(db: Session = Depends(get_db), u=Depends(staff)):
    return [{"id": r.id, "parent_id": r.parent_id, "child_id": r.child_id, "rel_type": r.rel_type} for r in db.scalars(scoped(select(CIRelation), CIRelation, u))]

def _graph(db, u):
    rels = db.scalars(scoped(select(CIRelation), CIRelation, u)).all()
    up, down = defaultdict(list), defaultdict(list)  # parent depends_on child => child is upstream of parent
    for r in rels: down[r.child_id].append(r.parent_id); up[r.parent_id].append(r.child_id)
    return up, down

def impacted(db, u, ci_id, depth=4):
    """CIs that depend (transitively) on ci_id — the blast radius."""
    _, down = _graph(db, u); seen, frontier = set(), [ci_id]
    for _ in range(depth):
        frontier = [x for f in frontier for x in down[f] if x not in seen]; seen.update(frontier)
    return seen

@router.get("/cmdb/ci/{cid}/graph")
def ci_graph(cid: int, db: Session = Depends(get_db), u=Depends(staff)):
    ci = get_or_404(db, Record, cid, u); up, down = _graph(db, u)
    ids = {cid} | set(up[cid]) | set(down[cid]) | impacted(db, u, cid)
    nodes = {r.id: r for r in db.scalars(select(Record).where(Record.id.in_(ids)))}
    rels = [r for r in db.scalars(scoped(select(CIRelation), CIRelation, u)) if r.parent_id in ids and r.child_id in ids]
    return {"ci": out(ci), "nodes": [{"id": n.id, "number": n.number, "title": n.title, "ci_class": n.data.get("ci_class"), "state": n.state, "dq_score": n.data.get("dq_score")} for n in nodes.values()],
            "edges": [{"source": r.parent_id, "target": r.child_id, "rel_type": r.rel_type} for r in rels],
            "depends_on": up[cid], "impacted": sorted(impacted(db, u, cid))}

@router.get("/cmdb/quality")
def cmdb_quality(db: Session = Depends(get_db), u=Depends(staff)):
    cis = _cis(db, u)
    for c in cis: hooks.compute(c)
    db.commit()
    rel_ids = {x for r in db.scalars(scoped(select(CIRelation), CIRelation, u)) for x in (r.parent_id, r.child_id)}
    orphans = [c for c in cis if c.id not in rel_ids]
    scores = [c.data.get("dq_score", 0) for c in cis]
    return {"ci_count": len(cis), "avg_dq_score": round(mean(scores), 1) if scores else 0, "orphans": len(orphans),
            "undiscovered": sum(1 for c in cis if not c.data.get("last_discovered")),
            "by_class": dict(Counter(c.data.get("ci_class", "unknown") for c in cis)),
            "worst": [{"id": c.id, "number": c.number, "title": c.title, "dq_score": c.data.get("dq_score"), "missing": c.data.get("dq_missing")} for c in sorted(cis, key=lambda c: c.data.get("dq_score", 0))[:8]]}

class DiscoveryItem(BaseModel):
    name: str; ci_class: str = "server"; ip: str | None = None; os: str | None = None; serial: str | None = None
    environment: str | None = None; location: str | None = None; owner: str | None = None; criticality: str | None = None

class DiscoveryIn(BaseModel):
    source: str = "agentless-scan"; items: list[DiscoveryItem]; relations: list[dict] = []  # [{"parent": name, "child": name, "type": "runs_on"}]

@router.post("/cmdb/discovery")
def discovery(body: DiscoveryIn, db: Session = Depends(get_db), u=Depends(staff)):
    """Idempotent discovery import: reconciles on serial, then IP, then name. Never blanks existing values."""
    cis = _cis(db, u); created = updated = 0; by_name = {}
    for it in body.items:
        d = {k: v for k, v in it.model_dump().items() if v not in (None, "") and k != "name"}
        match = next((c for c in cis if (it.serial and c.data.get("serial") == it.serial) or (it.ip and c.data.get("ip") == it.ip) or c.title.lower() == it.name.lower()), None)
        if match:
            match.data = {**match.data, **d, "last_discovered": now().isoformat(), "discovery_source": body.source}; hooks.compute(match); updated += 1; ci = match
        else:
            ci = Record(tenant_id=u.tenant_id, module="ci", number=next_number(db, "ci"), title=it.name, state="operational", requester_id=u.id, impact=3, urgency=3,
                        priority="P4", category="cmdb", data={**d, "last_discovered": now().isoformat(), "discovery_source": body.source}, created_at=now(), ai_suggestion={})
            hooks.compute(ci); db.add(ci); db.flush(); cis.append(ci); created += 1
        by_name[it.name.lower()] = ci
    rels = 0
    existing = {(r.parent_id, r.child_id) for r in db.scalars(scoped(select(CIRelation), CIRelation, u))}
    for r in body.relations:
        p = by_name.get(str(r.get("parent", "")).lower()) or next((c for c in cis if c.title.lower() == str(r.get("parent", "")).lower()), None)
        c = by_name.get(str(r.get("child", "")).lower()) or next((c for c in cis if c.title.lower() == str(r.get("child", "")).lower()), None)
        if p and c and (p.id, c.id) not in existing:
            db.add(CIRelation(tenant_id=u.tenant_id, parent_id=p.id, child_id=c.id, rel_type=r.get("type", "depends_on"))); existing.add((p.id, c.id)); rels += 1
    audit.log(db, u.id, "discovery", "cmdb", body.source, {"created": created, "updated": updated, "relations": rels}); db.commit()
    return {"created": created, "updated": updated, "relations": rels}

# ---------------- Event management ----------------
SEV = {"info": 0, "warning": 1, "minor": 2, "major": 3, "critical": 4, "clear": -1}
WINDOW_MIN = 30

class EventIn(BaseModel):
    source: str = "prometheus"; node: str; metric: str; severity: str = "warning"; message: str = ""

def ingest_event(db, u, e: EventIn):
    sev = e.severity.lower() if e.severity.lower() in SEV else "warning"
    key = f"{e.node.lower()}|{e.metric.lower()}"; t = now()
    ev = db.scalar(scoped(select(Event), Event, u).where(Event.correlation_key == key, Event.state == "open").order_by(Event.id.desc()))
    if sev == "clear":
        if ev: ev.state = "closed"; ev.last_seen = t
        return ev, "cleared"
    ci = db.scalar(scoped(select(Record), Record, u).where(Record.module == "ci", Record.title.ilike(e.node)))
    if ev and ev.last_seen >= t - timedelta(minutes=WINDOW_MIN):
        ev.count += 1; ev.last_seen = t; ev.message = e.message or ev.message
        if SEV[sev] > SEV[ev.severity]: ev.severity = sev
        action = "deduplicated"
    else:
        ev = Event(tenant_id=u.tenant_id, source=e.source, node=e.node, metric=e.metric, severity=sev, message=e.message, correlation_key=key, ci_id=ci.id if ci else None, first_seen=t, last_seen=t)
        db.add(ev); db.flush(); action = "new"
    if SEV[ev.severity] >= SEV["major"] and not ev.incident_id:
        # topology correlation: if an upstream CI (that this one depends on) already has an open event incident, attach to it
        parent_inc = None
        if ev.ci_id:
            up, _ = _graph(db, u)
            for up_id in up[ev.ci_id]:
                pe = db.scalar(scoped(select(Event), Event, u).where(Event.ci_id == up_id, Event.state == "open", Event.incident_id != None))
                if pe: parent_inc = pe.incident_id; break
            if not parent_inc:  # or same CI other metric
                pe = db.scalar(scoped(select(Event), Event, u).where(Event.ci_id == ev.ci_id, Event.state == "open", Event.incident_id != None, Event.id != ev.id))
                if pe: parent_inc = pe.incident_id
        if parent_inc:
            ev.incident_id = parent_inc; action = "correlated"
            inc = db.get(Record, parent_inc); inc.data = {**inc.data, "event_ids": inc.data.get("event_ids", []) + [ev.id]}
        else:
            from ..main import create_record_core
            imp = 1 if ev.severity == "critical" else 2
            inc = create_record_core(db, u, "incident", RecordCreate(title=f"[{ev.source}] {ev.node}: {ev.metric} {ev.severity}", description=ev.message or f"Auto-created from event {ev.correlation_key}",
                                     impact=imp, urgency=imp, data={"event_ids": [ev.id], "auto_created": True, "ci": ev.node}), emit=True)
            if ci: inc.linked = [ci]
            ev.incident_id = inc.id; action = "incident_created"
    return ev, action

@router.post("/events")
def post_events(body: EventIn | list[EventIn], db: Session = Depends(get_db), u=Depends(staff)):
    items = body if isinstance(body, list) else [body]; results = []
    for e in items:
        ev, action = ingest_event(db, u, e); db.flush()
        results.append({"event_id": ev.id if ev else None, "action": action, "incident_id": ev.incident_id if ev else None})
    db.commit()
    return results

@router.get("/events")
def list_events(state: str | None = None, db: Session = Depends(get_db), u=Depends(staff)):
    s = scoped(select(Event), Event, u)
    if state: s = s.where(Event.state == state)
    return [{"id": e.id, "source": e.source, "node": e.node, "metric": e.metric, "severity": e.severity, "message": e.message, "count": e.count, "state": e.state,
             "incident_id": e.incident_id, "ci_id": e.ci_id, "first_seen": e.first_seen, "last_seen": e.last_seen} for e in db.scalars(s.order_by(Event.last_seen.desc()).limit(200))]

@router.get("/events/stats")
def event_stats(db: Session = Depends(get_db), u=Depends(staff)):
    evs = db.scalars(scoped(select(Event), Event, u)).all()
    raw = sum(e.count for e in evs); alerts = len(evs); incs = len({e.incident_id for e in evs if e.incident_id})
    return {"raw_events": raw, "alerts": alerts, "incidents": incs, "open": sum(e.state == "open" for e in evs),
            "noise_reduction_pct": round(100 * (1 - incs / raw), 1) if raw else 0, "by_severity": dict(Counter(e.severity for e in evs)), "by_source": dict(Counter(e.source for e in evs))}

# ---------------- ITAM ----------------
@router.get("/itam/summary")
def itam_summary(db: Session = Depends(get_db), u=Depends(staff)):
    recs = db.scalars(scoped(select(Record), Record, u).where(Record.module.in_(["asset", "license", "contract"]))).all()
    for r in recs: hooks.compute(r)
    today = now().date().isoformat(); soon = (now().date() + timedelta(days=60)).isoformat()
    assets = [r for r in recs if r.module == "asset"]; lic = [r for r in recs if r.module == "license"]; ctr = [r for r in recs if r.module == "contract"]
    return {
        "assets": {"total": len(assets), "by_state": dict(Counter(a.state for a in assets)), 
                   "warranty_expiring": [{"id": a.id, "number": a.number, "title": a.title, "warranty_end": a.data.get("warranty_end")} for a in assets if today <= (a.data.get("warranty_end") or "") <= soon]},
        "licenses": [{"id": l.id, "number": l.number, "title": l.title, **{k: l.data.get(k) for k in ("product", "seats_owned", "seats_used", "compliance", "utilization_pct")}} for l in lic],
        "contracts_expiring": [{"id": c.id, "number": c.number, "title": c.title, "vendor": c.data.get("vendor"), "end_date": c.data.get("end_date")}
                               for c in ctr if c.state == "active" and (c.data.get("end_date") or "9") <= soon],
    }

# ---------------- Cost views ----------------
class CostIn(BaseModel):
    provider: str; service: str; kind: str = "cloud"; month: str; amount: float; utilization: float = 1.0

def anomalies(rows, threshold=1.3, min_share=0.01):
    """Flags services whose latest month jumped vs. their trailing baseline. Only percentages leave this function (no money)."""
    series = defaultdict(list)
    for r in sorted(rows, key=lambda r: r.month): series[(r.provider, r.service)].append(r)
    months = sorted({r.month for r in rows}); last_total = sum(r.amount for r in rows if months and r.month == months[-1]) or 1
    flags = []
    for (p, s), rs in series.items():
        if len(rs) < 3: continue
        last, base = rs[-1], mean(x.amount for x in rs[:-1])
        if base and last.amount > base * threshold and (last.amount - base) / last_total >= min_share:
            flags.append({"provider": p, "service": s, "month": last.month, "increase_pct": round(100 * (last.amount / base - 1), 1), "_delta": last.amount - base})
    return sorted(flags, key=lambda f: -f["increase_pct"])

def _public(f): return {k: v for k, v in f.items() if not k.startswith("_")}

@router.post("/costs", status_code=201)
def add_costs(body: list[CostIn], db: Session = Depends(get_db), u=Depends(staff)):
    for c in body: db.add(CostRecord(tenant_id=u.tenant_id, **c.model_dump()))
    db.commit(); return {"ingested": len(body)}

def cost_rows(db, u): return db.scalars(scoped(select(CostRecord), CostRecord, u)).all()

@router.get("/costs")
def costs(db: Session = Depends(get_db), u=Depends(staff)):
    """Usage view without monetary values: a usage index (first month = 100) and shares in percent."""
    rows = cost_rows(db, u)
    months = sorted({r.month for r in rows}); provs = sorted({r.provider for r in rows})
    base = sum(r.amount for r in rows if months and r.month == months[0]) or 1
    idx = lambda v: round(100 * v / base, 1)
    trend = [{"month": m, **{p: idx(sum(r.amount for r in rows if r.month == m and r.provider == p)) for p in provs}} for m in months]
    last = months[-1] if months else None; cur = [r for r in rows if r.month == last]; tot = sum(r.amount for r in cur) or 1
    return {"months": months, "providers": provs, "trend": trend, "unit": "usage index (first month = 100)",
            "by_kind": [{"name": k, "share_pct": round(100 * sum(r.amount for r in cur if r.kind == k) / tot, 1)} for k in sorted({r.kind for r in rows})],
            "current_month": last, "current_index": idx(sum(r.amount for r in cur)),
            "services": [{"provider": r.provider, "service": r.service, "kind": r.kind, "share_pct": round(100 * r.amount / tot, 1), "utilization": r.utilization} for r in cur],
            "anomalies": [_public(f) for f in anomalies(rows)]}
