"""Phase 6: CMDB classes/attributes, relationship types, identity rules, impact view, service map, health score,
CSV import wizard with dry run, licence compliance, contracts and purchase orders (no money anywhere)."""
import csv, io
from collections import Counter, defaultdict
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Record, CIRelation, Event, now
from ..security import staff, admin_only
from ..deps import scoped, next_number, get_or_404
from .. import hooks, audit, settings_store, registry
from .itom import impacted, _graph

router = APIRouter(prefix="/api", tags=["cmdb"])
OPEN = ("new", "in_progress", "on_hold", "assess", "authorize", "scheduled", "implement")

def DEFAULT_CLASSES():
    return [{"key": k, "label": k.replace("_", " ").title(), "attributes": [{"key": a, "label": a.replace("_", " ").title(), "required": True} for a in v]} for k, v in hooks.CI_REQUIRED.items()]
DEFAULT_RELS = [{"key": "depends_on", "label": "Depends on", "reverse": "Used by"}, {"key": "runs_on", "label": "Runs on", "reverse": "Runs"},
                {"key": "hosted_on", "label": "Hosted on", "reverse": "Hosts"}, {"key": "connects_to", "label": "Connects to", "reverse": "Connected from"},
                {"key": "backs_up", "label": "Backs up", "reverse": "Backed up by"}, {"key": "member_of", "label": "Member of", "reverse": "Has member"}]
DEFAULT_IDENTITY = [["serial"], ["ip", "ci_class"], ["name"]]

def _g(db, tid, k, d): v = settings_store.get(db, tid, k).get("v"); return d if v is None else v

def load_classes(db, tid):
    cl = _g(db, tid, "cmdb.classes", None)
    if cl:
        for c in cl: hooks.CI_REQUIRED[c["key"]] = [a["key"] for a in c["attributes"] if a.get("required")]
    return cl or DEFAULT_CLASSES()

def rel_types(db, tid): return _g(db, tid, "cmdb.rel_types", DEFAULT_RELS)

# ---------- config ----------
class Attr(BaseModel):
    key: str; label: str; required: bool = False; type: str = "text"
class CIClass(BaseModel):
    key: str; label: str; parent: str | None = None; attributes: list[Attr] = []
class RelType(BaseModel):
    key: str; label: str; reverse: str = ""

@router.get("/cmdb/config")
def config(u=Depends(staff), db: Session = Depends(get_db)):
    return {"classes": load_classes(db, u.tenant_id), "rel_types": rel_types(db, u.tenant_id), "identity": _g(db, u.tenant_id, "cmdb.identity", DEFAULT_IDENTITY)}

def _key_ok(k): return k and k.replace("_", "").isalnum() and k.lower() == k

@router.put("/cmdb/classes")
def put_classes(b: list[CIClass], u=Depends(admin_only), db: Session = Depends(get_db)):
    keys = [c.key for c in b]
    if len(set(keys)) != len(keys) or not all(_key_ok(k) for k in keys): raise HTTPException(400, "Class keys must be unique, lower-case letters, digits or _.")
    for c in b:
        if c.parent and c.parent not in keys: raise HTTPException(400, f"“{c.label}” has an unknown parent class.")
    v = [c.model_dump() for c in b]; settings_store.put(db, u.tenant_id, "cmdb.classes", {"v": v}); load_classes(db, u.tenant_id)
    audit.log(db, u.id, "update", "cmdb_classes", None); db.commit(); return v

@router.put("/cmdb/rel-types")
def put_rels(b: list[RelType], u=Depends(admin_only), db: Session = Depends(get_db)):
    if not all(_key_ok(r.key) for r in b) or len({r.key for r in b}) != len(b): raise HTTPException(400, "Relationship keys must be unique and lower-case.")
    v = [r.model_dump() for r in b]; settings_store.put(db, u.tenant_id, "cmdb.rel_types", {"v": v}); audit.log(db, u.id, "update", "cmdb_rel_types", None); db.commit(); return v

@router.put("/cmdb/identity")
def put_identity(b: list[list[str]], u=Depends(admin_only), db: Session = Depends(get_db)):
    if not b or any(not r for r in b): raise HTTPException(400, "Each identity rule needs at least one attribute.")
    settings_store.put(db, u.tenant_id, "cmdb.identity", {"v": b}); audit.log(db, u.id, "update", "cmdb_identity", None); db.commit(); return b

# ---------- import wizard ----------
class ImportIn(BaseModel):
    csv: str = ""; rows: list[dict] = []; mapping: dict[str, str] = {}; default_class: str = "server"; dry_run: bool = True

def _val(c, attr): return c.title if attr == "name" else c.data.get(attr)

@router.post("/cmdb/import")
def cmdb_import(b: ImportIn, u=Depends(staff), db: Session = Depends(get_db)):
    rows = b.rows or list(csv.DictReader(io.StringIO(b.csv.strip()))) if (b.rows or b.csv.strip()) else []
    if not rows: raise HTTPException(400, "No rows found. Paste a CSV with a header row.")
    if len(rows) > 500: raise HTTPException(400, "Please import 500 rows or fewer at a time.")
    classes = {c["key"] for c in load_classes(db, u.tenant_id)}; ident = _g(db, u.tenant_id, "cmdb.identity", DEFAULT_IDENTITY)
    cis = db.scalars(scoped(select(Record), Record, u).where(Record.module == "ci")).all()
    res, cnt = [], Counter()
    for n, raw in enumerate(rows, 1):
        m = {(b.mapping.get(k) or k).strip().lower(): (str(v).strip() if v is not None else "") for k, v in raw.items() if k and (b.mapping.get(k) or k) != "_skip"}
        m = {k: v for k, v in m.items() if v}
        m.setdefault("ci_class", b.default_class)
        if not m.get("name"): res.append({"row": n, "action": "error", "message": "Missing name"}); cnt["error"] += 1; continue
        if m["ci_class"] not in classes: res.append({"row": n, "action": "error", "message": f"Unknown class “{m['ci_class']}”"}); cnt["error"] += 1; continue
        match, rule = None, None
        for r in ident:
            if all(m.get(a) for a in r):
                match = next((c for c in cis if all(str(_val(c, a) or "").lower() == m[a].lower() for a in r)), None)
                if match: rule = "+".join(r); break
        data = {k: v for k, v in m.items() if k != "name"}
        if match:
            diff = {k: v for k, v in data.items() if str(match.data.get(k) or "") != v}
            if not diff: res.append({"row": n, "action": "unchanged", "name": m["name"], "match": match.number, "rule": rule}); cnt["unchanged"] += 1; continue
            res.append({"row": n, "action": "update", "name": m["name"], "match": match.number, "rule": rule, "changes": diff}); cnt["update"] += 1
            if not b.dry_run: match.data = {**match.data, **diff, "last_discovered": now().isoformat(), "discovery_source": "csv-import"}; hooks.compute(match)
        else:
            res.append({"row": n, "action": "create", "name": m["name"]}); cnt["create"] += 1
            if not b.dry_run:
                ci = Record(tenant_id=u.tenant_id, module="ci", number=next_number(db, "ci"), title=m["name"][:250], state="operational", requester_id=u.id, impact=3, urgency=3, priority="P4",
                            category="cmdb", data={**data, "last_discovered": now().isoformat(), "discovery_source": "csv-import"}, created_at=now(), ai_suggestion={})
                hooks.compute(ci); db.add(ci); db.flush(); cis.append(ci)
    if not b.dry_run: audit.log(db, u.id, "import", "ci", None, dict(cnt)); db.commit()
    return {"dry_run": b.dry_run, "summary": {k: cnt.get(k, 0) for k in ("create", "update", "unchanged", "error")}, "rows": res}

# ---------- health, impact, service map ----------
def _open_by_ci(db, u):
    m = defaultdict(list)
    for r in db.scalars(scoped(select(Record), Record, u).where(Record.module.in_(["incident", "change", "problem"]), Record.state.in_(OPEN + ("assessment", "root_cause_analysis", "known_error", "fix_in_progress")))):
        k = str(r.data.get("ci") or "").lower()
        if k: m[k].append(r)
    return m

def health(c, opens, evs):
    rs = opens.get(c.title.lower(), []) + opens.get(c.number.lower(), [])
    inc = [r for r in rs if r.module == "incident"]
    s = 100 - 25 * sum(r.priority in ("P1", "P2") for r in inc) - 8 * sum(r.priority not in ("P1", "P2") for r in inc) - 10 * evs.get(c.id, 0)
    s -= max(0, (80 - (c.data.get("dq_score") or 80)) // 4)
    if c.state == "maintenance": s -= 10
    s = max(0, min(100, s))
    return {"score": s, "status": "healthy" if s >= 80 else "degraded" if s >= 50 else "critical", "open_incidents": len(inc), "open_changes": sum(r.module == "change" for r in rs)}

def _ctx(db, u):
    load_classes(db, u.tenant_id)
    cis = db.scalars(scoped(select(Record), Record, u).where(Record.module == "ci")).all()
    since = now() - timedelta(days=1)
    evs = Counter(e.ci_id for e in db.scalars(scoped(select(Event), Event, u)) if e.ci_id and e.state != "closed" and e.severity in ("critical", "major") and (e.last_seen or now()).replace(tzinfo=None) >= since.replace(tzinfo=None))
    return cis, _open_by_ci(db, u), evs

@router.get("/cmdb/health")
def cmdb_health(u=Depends(staff), db: Session = Depends(get_db)):
    cis, opens, evs = _ctx(db, u)
    rows = sorted(({"id": c.id, "number": c.number, "title": c.title, "ci_class": c.data.get("ci_class"), **health(c, opens, evs)} for c in cis), key=lambda x: x["score"])
    return {"average": round(sum(r["score"] for r in rows) / len(rows)) if rows else None, "by_status": dict(Counter(r["status"] for r in rows)), "rows": rows}

@router.get("/cmdb/service-map")
def service_map(u=Depends(staff), db: Session = Depends(get_db)):
    cis, opens, evs = _ctx(db, u)
    rels = db.scalars(scoped(select(CIRelation), CIRelation, u)).all(); labels = {r["key"]: r["label"] for r in rel_types(db, u.tenant_id)}
    return {"nodes": [{"id": c.id, "number": c.number, "title": c.title, "ci_class": c.data.get("ci_class"), "environment": c.data.get("environment"), **health(c, opens, evs)} for c in cis],
            "edges": [{"source": r.parent_id, "target": r.child_id, "rel_type": r.rel_type, "label": labels.get(r.rel_type, r.rel_type)} for r in rels]}

@router.get("/cmdb/ci/{cid}/impact")
def impact(cid: int, u=Depends(staff), db: Session = Depends(get_db)):
    ci = get_or_404(db, Record, cid, u)
    if ci.module != "ci": raise HTTPException(404, "Not found")
    cis, opens, evs = _ctx(db, u); by = {c.id: c for c in cis}
    up, _ = _graph(db, u); hit = [by[i] for i in impacted(db, u, cid) if i in by]
    affected_services = [c for c in hit if c.data.get("ci_class") in ("application", "cloud_service")]
    tickets = [r for c in [ci, *hit] for r in opens.get(c.title.lower(), []) + opens.get(c.number.lower(), [])]
    b = lambda c: {"id": c.id, "number": c.number, "title": c.title, "ci_class": c.data.get("ci_class"), "criticality": c.data.get("criticality"), **health(c, opens, evs)}
    return {"ci": b(ci), "depends_on": [b(by[i]) for i in up[cid] if i in by], "impacted": [b(c) for c in hit], "services": [b(c) for c in affected_services],
            "open_tickets": [{"id": r.id, "module": r.module, "number": r.number, "title": r.title, "priority": r.priority, "state": r.state} for r in {r.id: r for r in tickets}.values()],
            "summary": f"If {ci.title} goes down, {len(hit)} other item(s) could be affected, including {len(affected_services)} service(s)."}

# ---------- licences, contracts, purchase orders ----------
@router.get("/itam/licence-compliance")
def licence_compliance(u=Depends(staff), db: Session = Depends(get_db)):
    rows = []
    for l in db.scalars(scoped(select(Record), Record, u).where(Record.module == "license")):
        hooks.compute(l); o, us = int(l.data.get("seats_owned") or 0), int(l.data.get("seats_used") or 0)
        rows.append({"id": l.id, "number": l.number, "title": l.title, "vendor": l.data.get("vendor"), "seats_owned": o, "seats_used": us, "gap": us - o,
                     "status": l.data.get("compliance"), "utilization_pct": l.data.get("utilization_pct"), "renewal_date": l.data.get("renewal_date")})
    return {"by_status": dict(Counter(r["status"] for r in rows)), "over_deployed_seats": sum(max(0, r["gap"]) for r in rows), "unused_seats": sum(max(0, -r["gap"]) for r in rows),
            "rows": sorted(rows, key=lambda r: -r["gap"])}

@router.get("/itam/contracts")
def contracts(days: int = 90, u=Depends(staff), db: Session = Depends(get_db)):
    today = now().date(); out = []
    for c in db.scalars(scoped(select(Record), Record, u).where(Record.module == "contract")):
        e = c.data.get("end_date"); left = None
        try: left = (__import__("datetime").date.fromisoformat(e) - today).days if e else None
        except ValueError: pass
        out.append({"id": c.id, "number": c.number, "title": c.title, "vendor": c.data.get("vendor"), "type": c.data.get("contract_type"), "state": c.state, "end_date": e, "days_left": left,
                    "renewal": "overdue" if left is not None and left < 0 and c.state == "active" else "soon" if left is not None and 0 <= left <= days else "ok"})
    return sorted(out, key=lambda x: (x["days_left"] is None, x["days_left"] or 0))

@router.post("/itam/po/{pid}/receive")
def receive_po(pid: int, b: dict, u=Depends(staff), db: Session = Depends(get_db)):
    po = get_or_404(db, Record, pid, u)
    if po.module != "purchase_order": raise HTTPException(404, "Not found")
    if po.state != "ordered": raise HTTPException(400, "Only ordered POs can be received.")
    qty = int(po.data.get("quantity") or 1); left = qty - int(po.data.get("received") or 0); got = int(b.get("quantity") or left)
    if got < 1 or got > left: raise HTTPException(400, "That's more than is still outstanding.")
    made = []
    for i in range(got):
        a = Record(tenant_id=u.tenant_id, module="asset", number=next_number(db, "asset"), title=f"{po.data.get('item') or po.title}"[:250], state="in_stock", requester_id=u.id, impact=3, urgency=3,
                   priority="P4", category="hardware", data={"asset_type": "hardware", "model": po.data.get("item"), "po": po.number, "contract": po.data.get("contract"), "purchase_date": now().date().isoformat()}, created_at=now(), ai_suggestion={})
        db.add(a); db.flush(); made.append(a.number)
    po.data = {**po.data, "received": int(po.data.get("received") or 0) + got, "assets": list(po.data.get("assets", [])) + made}
    if po.data["received"] >= qty: po.state = "received"
    audit.log(db, u.id, "receive", "purchase_order", po.number, {"assets": len(made)}); db.commit()
    return {"state": po.state, "received": po.data["received"], "assets": made}
