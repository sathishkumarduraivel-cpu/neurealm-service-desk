"""Phase 4: catalog builder (conditional forms, stages, fulfilment tasks, entitlements), on-behalf ordering,
approval delegation, KB versions/feedback/insights, CSAT + reopen."""
from collections import Counter
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from ..db import get_db
from ..models import CatalogItem, Record, Approval, User, Group, KBArticle, now
from ..security import current_user, staff, admin_only
from ..deps import get_record, notify, link_for, next_number
from .. import audit, sla, settings_store, registry, bus

router = APIRouter(prefix="/api", tags=["portal"])
FTYPES = ["text", "textarea", "number", "date", "choice", "checkbox", "user"]

# ---------- catalog builder ----------
class CField(BaseModel):
    key: str; label: str; type: str = "text"; options: list[str] = []; required: bool = False; help: str = ""; visible_if: dict | None = None
class ItemIn(BaseModel):
    name: str; category: str = "General"; description: str = ""; icon: str = "📦"; requires_approval: bool = True; fulfillment_group: str | None = None
    form_fields: list[CField] = []; approval_stages: list[dict] = []; fulfilment_tasks: list[str] = []; entitled: list[str] = []; active: bool = True

def item_out(i, db=None):
    g = db.get(Group, i.fulfillment_group_id) if db and i.fulfillment_group_id else None
    return {"id": i.id, "name": i.name, "category": i.category, "description": i.description, "icon": i.icon, "requires_approval": i.requires_approval, "active": i.active,
            "form_fields": i.form_fields or [], "approval_stages": i.approval_stages or [], "fulfilment_tasks": i.fulfilment_tasks or [], "entitled": i.entitled or [], "fulfillment_group": g.name if g else None}

def _apply(db, i, b, tid):
    if not b.name.strip(): raise HTTPException(400, "Please give the item a name.")
    keys = set()
    for f in b.form_fields:
        if f.type not in FTYPES: raise HTTPException(400, f"Unknown field type: {f.type}")
        if f.type == "choice" and not f.options: raise HTTPException(400, f"“{f.label}” needs options.")
        if f.key in keys: raise HTTPException(400, f"Duplicate field key: {f.key}")
        keys.add(f.key)
    for st in b.approval_stages:
        a = str(st.get("approver", "admin"))
        if not (a == "admin" or a.startswith("group:") or a.startswith("user:")): raise HTTPException(400, "Approver must be admin, group:<name> or user:<id>.")
    g = db.scalar(select(Group).where(Group.tenant_id == tid, Group.name == b.fulfillment_group)) if b.fulfillment_group else None
    if b.fulfillment_group and not g: raise HTTPException(400, "Unknown fulfilment group.")
    for k in ("name", "category", "description", "icon", "requires_approval", "fulfilment_tasks", "entitled", "active", "approval_stages"): setattr(i, k, getattr(b, k))
    i.form_fields = [f.model_dump() for f in b.form_fields]; i.fulfillment_group_id = g.id if g else None
    if i.requires_approval and not i.approval_stages: i.approval_stages = [{"name": "Approval", "approver": "admin"}]

@router.get("/catalog-admin/items")
def admin_items(u=Depends(admin_only), db: Session = Depends(get_db)):
    return [item_out(i, db) for i in db.scalars(select(CatalogItem).where(CatalogItem.tenant_id == u.tenant_id).order_by(CatalogItem.category, CatalogItem.name))]

@router.post("/catalog-admin/items", status_code=201)
def create_item(b: ItemIn, u=Depends(admin_only), db: Session = Depends(get_db)):
    i = CatalogItem(tenant_id=u.tenant_id); _apply(db, i, b, u.tenant_id); db.add(i); db.flush(); audit.log(db, u.id, "create", "catalog_item", i.id); db.commit(); return item_out(i, db)

@router.put("/catalog-admin/items/{iid}")
def update_item(iid: int, b: ItemIn, u=Depends(admin_only), db: Session = Depends(get_db)):
    i = db.get(CatalogItem, iid)
    if not i or i.tenant_id != u.tenant_id: raise HTTPException(404, "Not found")
    _apply(db, i, b, u.tenant_id); audit.log(db, u.id, "update", "catalog_item", i.id); db.commit(); return item_out(i, db)

def entitled(db, i, u):
    if not i.entitled or u.role in ("admin", "agent"): return True
    return u.role in i.entitled or any(e == f"group:{db.get(Group, u.group_id).name}" for e in i.entitled if u.group_id)

@router.get("/portal/catalog")
def portal_catalog(u=Depends(current_user), db: Session = Depends(get_db)):
    return [item_out(i, db) for i in db.scalars(select(CatalogItem).where(CatalogItem.tenant_id == u.tenant_id, CatalogItem.active == True).order_by(CatalogItem.category, CatalogItem.name)) if entitled(db, i, u)]

def _visible(f, vals):
    c = f.get("visible_if") or {}
    if not c.get("field"): return True
    v = str(vals.get(c["field"], "")).lower(); x = str(c.get("value", "")).lower()
    return v != x if c.get("op") == "neq" else v == x

def _approver(db, tid, spec):
    spec = str(spec or "admin")
    if spec.startswith("user:"):
        u = db.get(User, int(spec[5:])); return u if u and u.tenant_id == tid else None
    if spec.startswith("group:"):
        g = db.scalar(select(Group).where(Group.tenant_id == tid, Group.name == spec[6:]))
        return db.scalar(select(User).where(User.group_id == g.id, User.active == True, User.role != "end_user").order_by(User.id)) if g else None
    return db.scalar(select(User).where(User.tenant_id == tid, User.role == "admin", User.active == True).order_by(User.id))

class OrderIn(BaseModel):
    values: dict = {}; justification: str = ""; on_behalf_of: int | None = None

@router.post("/portal/order/{iid}", status_code=201)
def order(iid: int, b: OrderIn, u=Depends(current_user), db: Session = Depends(get_db)):
    i = db.get(CatalogItem, iid)
    if not i or i.tenant_id != u.tenant_id or not i.active: raise HTTPException(404, "Not found")
    if not entitled(db, i, u): raise HTTPException(403, "This item isn't available to you. Please ask the service desk.")
    who = u
    if b.on_behalf_of and b.on_behalf_of != u.id:
        who = db.get(User, b.on_behalf_of)
        if not who or who.tenant_id != u.tenant_id: raise HTTPException(400, "Unknown person.")
    vals = {}
    for f in i.form_fields or []:
        if not _visible(f, b.values): continue
        k = f.get("key") or f.get("name"); v = b.values.get(k)
        if f.get("required") and v in (None, "", False): raise HTTPException(400, f"Please fill in “{f['label']}”.")
        if v not in (None, "") and f.get("type") in ("choice", "select") and v not in f.get("options", []): raise HTTPException(400, f"“{f['label']}” has an unknown option.")
        if v not in (None, ""): vals[k] = v
    r = Record(tenant_id=u.tenant_id, module="request", number=next_number(db, "request"), title=f"{i.name} for {who.full_name}", description=b.justification,
               requester_id=who.id, category=i.category, assignment_group_id=i.fulfillment_group_id, priority="P4", impact=3, urgency=3, created_at=now(),
               data={"catalog_item_id": i.id, "item": i.name, "values": vals, **({"ordered_by": u.id, "ordered_by_name": u.full_name} if who.id != u.id else {})})
    if i.requires_approval:
        r.state = "pending_approval"
        for lvl, st in enumerate(i.approval_stages or [{"approver": "admin"}], 1):
            ap = _approver(db, u.tenant_id, st.get("approver"))
            r.approvals.append(Approval(level=lvl, approver_id=ap.id if ap else None, comment=st.get("name", "")[:500]))
    else:
        r.state = "approved"
    sla.apply_sla(db, r); db.add(r); db.flush()
    if not i.requires_approval: start_fulfilment(db, r)
    else:
        first = next((a for a in r.approvals if a.level == 1), None)
        if first and first.approver_id: notify(db, u.tenant_id, f"Approval needed: {r.number} {r.title}", "approval", first.approver_id, None, link_for(r))
    audit.log(db, u.id, "order", "request", r.number, {"item": i.name, "for": who.id}); bus.emit(db, r, "created", u); db.commit()
    return {"id": r.id, "number": r.number, "state": r.state}

def start_fulfilment(db, r):
    i = db.get(CatalogItem, (r.data or {}).get("catalog_item_id") or 0)
    tasks = [{"id": n + 1, "title": t, "done": False} for n, t in enumerate((i.fulfilment_tasks if i else []) or [])]
    r.data = {**(r.data or {}), "tasks": tasks}; r.state = "in_progress" if tasks else "approved"; flag_modified(r, "data")
    if r.assignment_group_id: notify(db, r.tenant_id, f"Ready to fulfil: {r.number} {r.title}", "info", None, r.assignment_group_id, link_for(r))

@bus.subscribe
def _on_update(db, r, event, actor, changes=None):
    """Requests: auto-complete when every fulfilment task is done."""
    if r.module == "request" and r.state == "in_progress" and "data.tasks" in (changes or {}):
        t = (r.data or {}).get("tasks") or []
        if t and all(x.get("done") for x in t) and (r.data or {}).get("catalog_item_id"):
            r.state = "fulfilled"; r.resolved_at = r.resolved_at or now()
            notify(db, r.tenant_id, f"{r.number} is done. How did we do?", "info", r.requester_id, None, link_for(r))

# ---------- delegation ----------
class DelegateIn(BaseModel):
    to_user_id: int | None = None; until: str | None = None

def delegators_for(db, u):
    """IDs of users who have delegated their approvals to u (still in date)."""
    from ..models import Setting
    out = []
    for s in db.scalars(select(Setting).where(Setting.tenant_id == u.tenant_id, Setting.key.like("delegate.%"))):
        v = (s.value or {}).get("v") or {}
        if v.get("to") == u.id and (not v.get("until") or v["until"] >= date.today().isoformat()): out.append(int(s.key.split(".")[1]))
    return out

@router.get("/me/delegate")
def get_delegate(u=Depends(staff), db: Session = Depends(get_db)):
    return {**(settings_store.get(db, u.tenant_id, f"delegate.{u.id}").get("v") or {}), "covering_for": delegators_for(db, u)}

@router.put("/me/delegate")
def put_delegate(b: DelegateIn, u=Depends(staff), db: Session = Depends(get_db)):
    if b.to_user_id:
        t = db.get(User, b.to_user_id)
        if not t or t.tenant_id != u.tenant_id or t.id == u.id or t.role == "end_user": raise HTTPException(400, "Please pick a colleague who can approve.")
        try: b.until and date.fromisoformat(b.until)
        except ValueError: raise HTTPException(400, "Please use a date like 2026-11-01.")
        notify(db, u.tenant_id, f"{u.full_name} asked you to cover their approvals", "approval", t.id, None, "/approvals")
    settings_store.put(db, u.tenant_id, f"delegate.{u.id}", {"v": {"to": b.to_user_id, "until": b.until} if b.to_user_id else None})
    audit.log(db, u.id, "delegate", "user", u.id, {"to": b.to_user_id, "until": b.until}); db.commit(); return get_delegate(u, db)

# ---------- KB versions / feedback / insights ----------
class KBIn(BaseModel):
    title: str; body: str; category: str = "general"; tags: str = ""; published: bool = True

@router.put("/kb/{aid}")
def kb_update(aid: int, b: KBIn, u=Depends(staff), db: Session = Depends(get_db)):
    a = db.get(KBArticle, aid)
    if not a or a.tenant_id != u.tenant_id: raise HTTPException(404, "Not found")
    a.versions = [*(a.versions or []), {"version": a.version or 1, "title": a.title, "body": a.body, "saved_at": now().isoformat(), "by": u.full_name}]
    for k, v in b.model_dump().items(): setattr(a, k, v)
    a.version = (a.version or 1) + 1; audit.log(db, u.id, "update", "kb", a.number, {"version": a.version}); db.commit()
    return {"id": a.id, "version": a.version}

@router.get("/kb/{aid}/versions")
def kb_versions(aid: int, u=Depends(staff), db: Session = Depends(get_db)):
    a = db.get(KBArticle, aid)
    if not a or a.tenant_id != u.tenant_id: raise HTTPException(404, "Not found")
    return {"current": a.version or 1, "versions": list(reversed(a.versions or []))}

class FeedbackIn(BaseModel):
    helpful: bool; comment: str = ""

@router.post("/kb/{aid}/feedback")
def kb_feedback(aid: int, b: FeedbackIn, u=Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(KBArticle, aid)
    if not a or a.tenant_id != u.tenant_id: raise HTTPException(404, "Not found")
    key = f"kbfb.{a.id}"; seen = settings_store.get(db, u.tenant_id, key).get("v") or []
    if u.id in seen: raise HTTPException(409, "Thanks, we already have your feedback on this one.")
    if b.helpful: a.helpful = (a.helpful or 0) + 1
    else: a.not_helpful = (a.not_helpful or 0) + 1
    settings_store.put(db, u.tenant_id, key, {"v": [*seen, u.id]}); db.commit()
    return {"helpful": a.helpful, "not_helpful": a.not_helpful}

@router.get("/kb-insights")
def kb_insights(u=Depends(staff), db: Session = Depends(get_db)):
    arts = db.scalars(select(KBArticle).where(KBArticle.tenant_id == u.tenant_id)).all()
    rate = lambda a: (a.helpful or 0) / max(1, (a.helpful or 0) + (a.not_helpful or 0))
    cats = Counter(r.category for r in db.scalars(select(Record).where(Record.tenant_id == u.tenant_id, Record.module == "incident", Record.created_at >= now() - timedelta(days=90))))
    covered = {a.category for a in arts if a.published}
    return {"total": len(arts), "published": sum(a.published for a in arts),
            "top_viewed": [{"id": a.id, "title": a.title, "views": a.views} for a in sorted(arts, key=lambda a: -(a.views or 0))[:5]],
            "needs_work": [{"id": a.id, "title": a.title, "helpful": a.helpful, "not_helpful": a.not_helpful} for a in sorted([a for a in arts if (a.not_helpful or 0) > 0], key=rate)[:5]],
            "gaps": [{"category": c, "incidents": n} for c, n in cats.most_common() if c not in covered][:5]}

# ---------- CSAT + reopen ----------
DONE = ("resolved", "closed", "fulfilled")
class RateIn(BaseModel):
    score: int; comment: str = ""

@router.post("/records/{module}/{rid}/rate")
def rate(module: str, rid: int, b: RateIn, u=Depends(current_user), db: Session = Depends(get_db)):
    r = get_record(db, module, rid, u)
    if r.requester_id != u.id: raise HTTPException(403, "Only the person who raised it can rate it.")
    if r.state not in DONE: raise HTTPException(400, "You can rate this once it's resolved.")
    if not 1 <= b.score <= 5: raise HTTPException(400, "Please pick 1 to 5 stars.")
    r.data = {**(r.data or {}), "csat": {"score": b.score, "comment": b.comment[:1000], "at": now().isoformat()}}
    if b.score <= 2 and r.assignment_group_id: notify(db, r.tenant_id, f"Low rating on {r.number} ({b.score}/5)", "info", None, r.assignment_group_id, link_for(r))
    audit.log(db, u.id, "csat", module, r.number, {"score": b.score}); db.commit(); return {"ok": True, "csat": r.data["csat"]}

class ReopenIn(BaseModel):
    reason: str

@router.post("/records/{module}/{rid}/reopen")
def reopen(module: str, rid: int, b: ReopenIn, u=Depends(current_user), db: Session = Depends(get_db)):
    r = get_record(db, module, rid, u)
    if u.role == "end_user" and r.requester_id != u.id: raise HTTPException(403)
    if r.state not in DONE: raise HTTPException(400, "It's still open.")
    if r.resolved_at and r.resolved_at < now() - timedelta(days=14) and u.role == "end_user": raise HTTPException(400, "This was closed over 14 days ago. Please raise a new ticket.")
    if not b.reason.strip(): raise HTTPException(400, "Please tell us what's still wrong.")
    flow = registry.MODULES[module].get("flow", {})
    r.state = "in_progress" if "in_progress" in flow else registry.initial(module); r.resolved_at = None
    r.data = {**(r.data or {}), "reopened": (r.data or {}).get("reopened", 0) + 1}
    from ..models import Comment
    db.add(Comment(record_id=r.id, author_id=u.id, body=f"Reopened: {b.reason.strip()}", internal=False))
    if r.assignee_id or r.assignment_group_id: notify(db, r.tenant_id, f"{r.number} was reopened", "info", r.assignee_id, r.assignment_group_id, link_for(r))
    audit.log(db, u.id, "reopen", module, r.number, {"reason": b.reason[:200]}); bus.emit(db, r, "updated", u, {"state": ["resolved", r.state]}); db.commit()
    return {"ok": True, "state": r.state}

@router.get("/csat/summary")
def csat_summary(u=Depends(staff), db: Session = Depends(get_db)):
    rows = [r for r in db.scalars(select(Record).where(Record.tenant_id == u.tenant_id)) if (r.data or {}).get("csat")]
    sc = [r.data["csat"]["score"] for r in rows]; by = Counter(sc)
    return {"responses": len(sc), "average": round(sum(sc) / len(sc), 2) if sc else None, "satisfied_pct": round(100 * sum(1 for s in sc if s >= 4) / len(sc)) if sc else None,
            "distribution": {str(k): by.get(k, 0) for k in range(1, 6)}, "recent": [{"number": r.number, "score": r.data["csat"]["score"], "comment": r.data["csat"]["comment"]} for r in rows[-5:]]}
