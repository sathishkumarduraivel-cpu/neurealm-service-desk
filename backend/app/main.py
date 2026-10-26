from collections import Counter
from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from . import config, ai, audit, sla, registry, hooks, bus, scheduler, sso
from .deps import scoped, next_number as _next_number, out as _out, get_record as _get, check_module as _check_module, notify, link_for, get_or_404
from .db import get_db, Base, engine
from .models import *
from .schemas import *
from .security import current_user, staff, admin_only, make_token, verify_pw, hash_pw

app = FastAPI(title=config.BRAND_NAME + " API", version="0.1.0",
              description="Neurealm Service Desk by Neurealm — AI-Native Service Management. Zero Friction. Full Autonomy.")
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
MODULES = set(registry.MODULES)
app.include_router(sso.router)
from .routers import identity as _identity
app.include_router(_identity.router)
from .routers import ticketing as _ticketing
app.include_router(_ticketing.router)
from . import forms as _forms
from .routers import serviceops as _serviceops
from .routers import portal as _portal
app.include_router(_portal.router)
app.include_router(_serviceops.router)
app.include_router(_forms.export_router)
app.include_router(_forms.router)
from .routers import itom as _itom
app.include_router(_itom.router)
from .routers import business as _business
app.include_router(_business.router)
from .routers import governance as _gov
app.include_router(_gov.router)
from .routers import changeops as _chops
app.include_router(_chops.router)
from .routers import cmdbx as _cmdbx
app.include_router(_cmdbx.router)
from .routers import aiops as _aiops
app.include_router(_aiops.router)
from .routers import analytics as _analytics
app.include_router(_analytics.router)
from .routers import platform as _platform
_platform.install(app)
from .routers import autonomy as _auto
from . import autoresolve as _ar, flowengine as _fe, integrations as _int
for _r in (_auto.router, _ar.router, _fe.router, _int.router): app.include_router(_r)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)  # Alembic is the source of truth for prod; this keeps dev/SQLite zero-config
    scheduler.start()
    try:
        from .db import SessionLocal
        _db = SessionLocal(); _ticketing.load_matrix(_db); _db.close()
    except Exception: pass

@app.on_event("shutdown")
def shutdown():
    scheduler.stop()

@app.get("/api/meta/modules")
def modules_meta(_=Depends(current_user)):
    return registry.meta()

@app.get("/api/health")
def health():
    return {"status": "ok", "db": engine.url.get_backend_name(), "llm_enabled": bool(config.LLM_API_KEY)}

# ---------- auth ----------
class LoginIn(BaseModel):
    email: str; password: str

def _login(db, email, pw):
    u = db.scalar(select(User).where(User.email == email.lower()))
    if not u or not verify_pw(pw, u.password_hash) or not u.active:
        raise HTTPException(401, "Invalid credentials")
    return _identity.begin_login(db, u)

@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    return _login(db, body.email, body.password)

@app.post("/api/auth/token")
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password)

@app.get("/api/auth/me", response_model=UserOut)
def me(u: User = Depends(current_user)):
    return u


FEATURE_KEYS = ["events", "fsm", "dex", "patch", "costs", "finops", "csm", "workplace", "spm", "secops", "grc", "autonomy", "quality"]
@app.get("/api/features")
def get_features(u: User = Depends(current_user), db: Session = Depends(get_db)):
    from . import settings_store
    v = settings_store.get(db, u.tenant_id, "features")
    return {k: bool(v.get(k, False)) for k in FEATURE_KEYS}

@app.put("/api/features")
def put_features(body: dict, u: User = Depends(admin_only), db: Session = Depends(get_db)):
    from . import settings_store
    clean = {k: bool(body[k]) for k in FEATURE_KEYS if k in body}
    settings_store.put(db, u.tenant_id, "features", clean)
    audit.log(db, u.id, "features.update", "settings", 0, clean)
    db.commit(); return get_features(u, db)

@app.get("/api/ai/status")
def ai_status(_=Depends(current_user), db: Session = Depends(get_db)):
    return _aiops.status(db, _.tenant_id)

@app.get("/api/tenant")
def my_tenant(u: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Tenant, u.tenant_id)
    return {"id": u.tenant_id, "name": t.name if t else "", "domain": t.domain if t else ""}

@app.get("/api/search")
def global_search(q: str = Query(..., min_length=2), u: User = Depends(current_user), db: Session = Depends(get_db)):
    like = f"%{q}%"
    st = select(Record).where(Record.tenant_id == u.tenant_id, or_(Record.number.ilike(like), Record.title.ilike(like)))
    if u.role == "end_user": st = st.where(Record.requester_id == u.id)
    rows = db.scalars(st.order_by(Record.created_at.desc()).limit(12)).all()
    return [{"id": r.id, "number": r.number, "title": r.title, "module": r.module, "state": r.state, "priority": r.priority} for r in rows]

# ---------- users & groups ----------
@app.get("/api/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(staff)):
    return db.scalars(scoped(select(User), User, _).order_by(User.id)).all()

@app.post("/api/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), me=Depends(admin_only)):
    if body.role not in ("admin", "agent", "end_user"): raise HTTPException(400, "bad role")
    if db.scalar(select(User).where(User.email == body.email.lower())): raise HTTPException(409, "email exists")
    u = User(tenant_id=me.tenant_id, email=body.email.lower(), full_name=body.full_name, password_hash=hash_pw(body.password), role=body.role, group_id=body.group_id)
    db.add(u); db.flush(); audit.log(db, me.id, "create", "user", u.id, {"role": u.role}); db.commit()
    return u

@app.patch("/api/users/{uid}", response_model=UserOut)
def update_user(uid: int, body: UserUpdate, db: Session = Depends(get_db), me=Depends(admin_only)):
    u = get_or_404(db, User, uid, me)
    d = body.model_dump(exclude_unset=True)
    if "password" in d: u.password_hash = hash_pw(d.pop("password"))
    for k, v in d.items(): setattr(u, k, v)
    audit.log(db, me.id, "update", "user", uid, d); db.commit()
    return u

@app.get("/api/groups", response_model=list[GroupOut])
def groups(db: Session = Depends(get_db), _=Depends(current_user)):
    return db.scalars(scoped(select(Group), Group, _).order_by(Group.name)).all()

# ---------- records ----------
@app.get("/api/records/{module}", response_model=list[RecordOut])
def list_records(request: Request, module: str, q: str | None = None, state: str | None = None, priority: str | None = None,
                 mine: bool = False, limit: int = Query(200, le=1000), db: Session = Depends(get_db), u=Depends(current_user)):
    _check_module(module)
    s = scoped(select(Record), Record, u).where(Record.module == module)
    if u.role == "end_user" and module not in ("request",) and "end_user" not in registry.MODULES[module]["create"]: raise HTTPException(403)
    if u.role == "end_user" or mine:
        s = s.where(Record.requester_id == u.id) if u.role == "end_user" else s.where(Record.assignee_id == u.id)
    if state: s = s.where(Record.state == state)
    if priority: s = s.where(Record.priority == priority)
    if q: s = s.where(or_(Record.title.ilike(f"%{q}%"), Record.number.ilike(f"%{q}%"), Record.description.ilike(f"%{q}%")))
    rows = list(db.scalars(s.order_by(Record.created_at.desc()).limit(limit)))
    if any(k.startswith("cf_") for k in request.query_params): rows = _forms.filter_rows(db, u.tenant_id, module, rows, dict(request.query_params))
    return [_out(r) for r in rows]

@app.post("/api/records/{module}", response_model=RecordDetail, status_code=201)
def create_record(module: str, body: RecordCreate, db: Session = Depends(get_db), u=Depends(current_user)):
    _check_module(module); m = registry.MODULES[module]
    if u.role not in m["create"]:
        raise HTTPException(400 if module == "request" else 403, "Use /api/catalog/{id}/order to raise requests" if module == "request" else "Not allowed")
    return _out(create_record_core(db, u, module, body), RecordDetail)

def create_record_core(db, u, module, body: RecordCreate, emit=True):
    m = registry.MODULES[module]
    r = Record(tenant_id=u.tenant_id, module=module, number=_next_number(db, module), title=body.title, description=body.description,
               state=registry.initial(module), requester_id=u.id, data=dict(body.data), created_at=now(), priority="P3" if m.get("ai") else "P4", impact=3, urgency=3, category="general", ai_suggestion={})
    if body.use_ai and m.get("ai"):
        t = ai.triage(db, body.title, body.description, u.tenant_id); r.ai_suggestion = t
        r.category = t["category"]; r.impact = t["impact"]; r.urgency = t["urgency"]; r.priority = t["priority"]
        if t["auto_apply"]: r.assignment_group_id = t["assignment_group_id"]
    for f in ("impact", "urgency", "category", "assignment_group_id", "assignee_id"):
        v = getattr(body, f)
        if v is not None and (u.role != "end_user" or f in ("impact", "urgency")): setattr(r, f, v)
    if body.priority and u.role != "end_user": r.priority = body.priority
    elif body.impact is not None or body.urgency is not None or (m.get("ai") and not body.use_ai): r.priority = ai.priority_from(r.impact, r.urgency)
    r.data = _forms.apply(db, u.tenant_id, module, r.data, create=True)
    if module == "change":
        r.data.setdefault("change_type", "normal")
    hooks.compute(r)
    if module == "change": _chops.check_schedule(db, r)
    if module == "change" and r.data["change_type"] == "standard": r.state = "scheduled"  # pre-approved
    if module == "reservation" and _reservation_conflict(db, r): r.state = "conflict"
    if m.get("sla"): sla.apply_sla(db, r)
    db.add(r); db.flush()
    if module == "problem" and body.data.get("incident_ids"):
        r.linked = [i for i in db.scalars(select(Record).where(Record.id.in_(body.data["incident_ids"]), Record.module == "incident", Record.tenant_id == u.tenant_id))]
    if r.assignment_group_id: notify(db, u.tenant_id, f"New {module.replace('_', ' ')} {r.number}: {r.title}", "info", None, r.assignment_group_id, link_for(r))
    audit.log(db, u.id, "create", module, r.number, {"priority": r.priority, "ai": r.ai_suggestion.get("engine")})
    if emit: bus.emit(db, r, "created", u)
    db.commit(); db.refresh(r)
    return r

def _reservation_conflict(db, r):
    sp, st, en = r.data.get("space"), r.data.get("start"), r.data.get("end")
    if not (sp and st and en): return False
    for o in db.scalars(select(Record).where(Record.module == "reservation", Record.tenant_id == r.tenant_id, Record.state.in_(["confirmed", "checked_in"]))):
        if o.data.get("space") == sp and o.data.get("start", "") < en and st < o.data.get("end", ""): return True
    return False

@app.get("/api/records/{module}/{rid}", response_model=RecordDetail)
def get_record(module: str, rid: int, db: Session = Depends(get_db), u=Depends(current_user)):
    _check_module(module); return _out(_get(db, module, rid, u), RecordDetail)

@app.patch("/api/records/{module}/{rid}", response_model=RecordDetail)
def update_record(module: str, rid: int, body: RecordUpdate, db: Session = Depends(get_db), u=Depends(staff)):
    _check_module(module); r = _get(db, module, rid, u)
    d = body.model_dump(exclude_unset=True); changes = {}
    exp = d.pop("expected_updated_at", None)
    if exp and r.updated_at and exp[:19] != r.updated_at.isoformat()[:19]:
        raise HTTPException(409, "Someone else updated this ticket while you were editing. Please review their changes.")
    if "state" in d and d["state"] != r.state:
        ns = d.pop("state")
        if ns not in registry.allowed(module, r.state): raise HTTPException(400, f"Transition {r.state} -> {ns} not allowed")
        _chops.guard(db, r, ns)
        if module == "change" and ns == "authorize": _start_change_approvals(db, r)
        changes["state"] = [r.state, ns]; r.state = ns
        if ns in registry.CLOSED and not r.resolved_at: r.resolved_at = now()
        if ns == "in_progress": r.resolved_at = None
    else: d.pop("state", None)
    if "data" in d:
        nd = _forms.apply(db, u.tenant_id, module, {**r.data, **d.pop("data")})
        for k in set(nd) | set(r.data or {}):
            if (r.data or {}).get(k) != nd.get(k) and k not in ("tasks", "watchers"): changes[f"data.{k}"] = [(r.data or {}).get(k), nd.get(k)]
        r.data = nd
    for k, v in d.items():
        if getattr(r, k) != v: changes[k] = [getattr(r, k), v]; setattr(r, k, v)
    if ("impact" in changes or "urgency" in changes) and "priority" not in changes:
        r.priority = ai.priority_from(r.impact, r.urgency)
    if "priority" in changes or "impact" in changes or "urgency" in changes:
        if registry.MODULES[module].get("sla"): sla.apply_sla(db, r)
    hooks.compute(r)
    if module == "change" and ({"data.planned_start", "data.planned_end", "data.change_type"} & set(changes)): _chops.check_schedule(db, r)
    if "assignee_id" in changes and r.assignee_id: notify(db, u.tenant_id, f"{r.number} assigned to you", "info", r.assignee_id, None, link_for(r))
    audit.log(db, u.id, "update", module, r.number, {k: [str(a), str(b)] for k, (a, b) in changes.items()})
    bus.emit(db, r, "updated", u, changes)
    db.commit(); db.refresh(r)
    return _out(r, RecordDetail)

@app.get("/api/records/{module}/{rid}/children", response_model=list[RecordOut])
def children(module: str, rid: int, db: Session = Depends(get_db), u=Depends(current_user)):
    r = _get(db, module, rid, u)
    return [_out(c) for c in db.scalars(select(Record).where(Record.parent_id == r.id).order_by(Record.id))]

@app.post("/api/records/{module}/{rid}/comments", response_model=CommentOut, status_code=201)
def add_comment(module: str, rid: int, body: CommentIn, db: Session = Depends(get_db), u=Depends(current_user)):
    r = _get(db, module, rid, u)
    c = Comment(record_id=r.id, author_id=u.id, body=body.body, internal=body.internal and u.role != "end_user")
    db.add(c); audit.log(db, u.id, "comment", module, r.number); db.commit(); db.refresh(c)
    return c

@app.post("/api/records/{module}/{rid}/link/{other}", response_model=RecordDetail)
def link(module: str, rid: int, other: int, db: Session = Depends(get_db), u=Depends(staff)):
    r = _get(db, module, rid, u); o = get_or_404(db, Record, other, u)
    if o not in r.linked: r.linked.append(o)
    audit.log(db, u.id, "link", module, r.number, {"to": o.number}); db.commit()
    return _out(r, RecordDetail)

@app.post("/api/records/problem/{rid}/known-error", response_model=RecordDetail)
def mark_known_error(rid: int, body: dict, db: Session = Depends(get_db), u=Depends(staff)):
    r = _get(db, "problem", rid, u)
    r.data = {**r.data, "known_error": True, "workaround": body.get("workaround", ""), "root_cause": body.get("root_cause", r.data.get("root_cause", ""))}
    if "known_error" in registry.allowed("problem", r.state): r.state = "known_error"
    audit.log(db, u.id, "known_error", "problem", r.number); db.commit()
    return _out(r, RecordDetail)

@app.get("/api/known-errors", response_model=list[RecordOut])
def known_errors(db: Session = Depends(get_db), _=Depends(current_user)):
    rows = db.scalars(scoped(select(Record), Record, _).where(Record.module == "problem")).all()
    return [_out(r) for r in rows if r.data.get("known_error")]

# ---------- approvals ----------
def _approvers(db, n, tenant_id=1):
    return db.scalars(select(User).where(User.role == "admin", User.active == True, User.tenant_id == tenant_id).order_by(User.id).limit(n)).all()

def _start_change_approvals(db, r):
    _chops.start_approvals(db, r)

@app.get("/api/approvals/pending")
def pending_approvals(db: Session = Depends(get_db), u=Depends(staff)):
    rows = db.scalars(select(Approval).join(Record, Record.id == Approval.record_id).where(Approval.state == "requested", Record.tenant_id == u.tenant_id)).all()
    out = []
    for a in rows:
        r = db.get(Record, a.record_id)
        lower_open = any(x.level < a.level and x.state != "approved" for x in r.approvals)
        if not lower_open and (u.role == "admin" or a.approver_id == u.id or a.approver_id in _portal.delegators_for(db, u)):
            out.append({"approval_id": a.id, "level": a.level, "record": RecordBrief.model_validate(r).model_dump(), "data": r.data})
    return out

@app.post("/api/approvals/{aid}/decide", response_model=RecordDetail)
def decide(aid: int, body: Decision, db: Session = Depends(get_db), u=Depends(staff)):
    a = get_or_404(db, Approval, aid)
    if db.get(Record, a.record_id).tenant_id != u.tenant_id: raise HTTPException(404)
    if a.state != "requested": raise HTTPException(400, "Already decided")
    delegated_from = a.approver_id if a.approver_id != u.id and a.approver_id in _portal.delegators_for(db, u) else None
    if u.role != "admin" and a.approver_id != u.id and not delegated_from: raise HTTPException(403, "Not your approval")
    r = db.get(Record, a.record_id)
    if any(x.level < a.level and x.state != "approved" for x in r.approvals): raise HTTPException(400, "Earlier level pending")
    a.state = "approved" if body.approve else "rejected"; a.comment = (body.comment + (f" (on behalf of user {delegated_from})" if delegated_from else "")).strip(); a.decided_at = now(); a.approver_id = u.id
    if not body.approve:
        r.state = "rejected"
    elif all(x.state == "approved" for x in r.approvals):  # final stage approved
        r.state = {"change": "scheduled", "patch_job": "approved"}.get(r.module, "approved")
        if r.module == "request" and r.data.get("catalog_item_id"): _portal.start_fulfilment(db, r)
        if r.module == "incident" and r.data.get("pending_playbook"):
            from .autoresolve import execute_approved
            execute_approved(db, r, u)
    if r.module == "incident" and not body.approve: r.state = "in_progress"; r.data = {**r.data, "pending_playbook": None}
    notify(db, r.tenant_id, f"{r.number} {'approved' if body.approve else 'rejected'}", "approval", r.requester_id, None, link_for(r))
    audit.log(db, u.id, "approve" if body.approve else "reject", r.module, r.number, {"level": a.level})
    db.commit(); db.refresh(r)
    return _out(r, RecordDetail)

# ---------- catalog ----------
@app.get("/api/catalog", response_model=list[CatalogItemOut])
def catalog(db: Session = Depends(get_db), _=Depends(current_user)):
    return db.scalars(scoped(select(CatalogItem), CatalogItem, _).where(CatalogItem.active == True).order_by(CatalogItem.category, CatalogItem.name)).all()

@app.post("/api/catalog", response_model=CatalogItemOut, status_code=201)
def create_item(body: CatalogItemIn, db: Session = Depends(get_db), u=Depends(admin_only)):
    i = CatalogItem(tenant_id=u.tenant_id, **body.model_dump()); db.add(i); db.flush(); audit.log(db, u.id, "create", "catalog_item", i.id); db.commit()
    return i

@app.post("/api/catalog/{iid}/order", response_model=RecordDetail, status_code=201)
def order(iid: int, body: OrderIn, db: Session = Depends(get_db), u=Depends(current_user)):
    i = get_or_404(db, CatalogItem, iid, u)
    r = Record(tenant_id=u.tenant_id, module="request", number=_next_number(db, "request"), title=f"{i.name} for {u.full_name}",
               description=body.justification, requester_id=u.id, category=i.category, assignment_group_id=i.fulfillment_group_id,
               data={"catalog_item_id": i.id, "item": i.name, "values": body.values}, priority="P4", impact=3, urgency=3, created_at=now())
    if i.requires_approval:
        r.state = "pending_approval"
        ap = _approvers(db, 1, u.tenant_id); r.approvals.append(Approval(level=1, approver_id=ap[0].id if ap else None))
    else:
        r.state = "approved"
    sla.apply_sla(db, r); db.add(r); db.flush()
    audit.log(db, u.id, "order", "request", r.number, {"item": i.name}); db.commit(); db.refresh(r)
    return _out(r, RecordDetail)

# ---------- knowledge ----------
@app.get("/api/kb", response_model=list[KBOut])
def kb_list(q: str | None = None, db: Session = Depends(get_db), u=Depends(current_user)):
    s = scoped(select(KBArticle), KBArticle, u)
    if u.role == "end_user": s = s.where(KBArticle.published == True)
    rows = db.scalars(s.order_by(KBArticle.views.desc())).all()
    if not q: return rows
    toks = set(ai.tokens(q))
    scored = []
    for a in rows:
        hay = ai.tokens(f"{a.title} {a.title} {a.title} {a.tags} {a.tags} {a.body}")
        sc = sum(1 for t in hay if t in toks) + (5 if q.lower() in a.title.lower() else 0)
        if sc: scored.append((sc, a))
    return [a for _, a in sorted(scored, key=lambda x: -x[0])]

@app.get("/api/kb/{aid}", response_model=KBOut)
def kb_get(aid: int, db: Session = Depends(get_db), _=Depends(current_user)):
    a = get_or_404(db, KBArticle, aid, _); a.views += 1; db.commit(); return a

@app.post("/api/kb", response_model=KBOut, status_code=201)
def kb_create(body: KBIn, db: Session = Depends(get_db), u=Depends(staff)):
    n = (db.scalar(select(func.count()).select_from(KBArticle)) or 0) + 1001
    a = KBArticle(tenant_id=u.tenant_id, number=f"KB{n:07d}", **body.model_dump()); db.add(a); db.flush()
    audit.log(db, u.id, "create", "kb", a.number); db.commit(); return a

@app.post("/api/kb/from-incident/{rid}", response_model=KBOut, status_code=201)
def kb_from_incident(rid: int, db: Session = Depends(get_db), u=Depends(staff)):
    """AI-assisted (template) article generation from a resolved ticket."""
    r = _get(db, "incident", rid, u)
    notes = "\n".join(f"- {c.body}" for c in r.comments if c.body) or "- (no work notes)"
    body = f"## Symptoms\n{r.description}\n\n## Resolution\n{r.data.get('resolution_notes', 'See work notes.')}\n\n## Work notes\n{notes}\n\n_Source: {r.number}_"
    n = (db.scalar(select(func.count()).select_from(KBArticle)) or 0) + 1001
    a = KBArticle(tenant_id=u.tenant_id, number=f"KB{n:07d}", title=f"How to resolve: {r.title}", body=body, category=r.category, tags=r.category,
                  published=False, ai_generated=True)
    db.add(a); db.flush(); audit.log(db, u.id, "kb_generate", "kb", a.number, {"from": r.number}); db.commit(); return a

# ---------- SLA ----------
@app.get("/api/sla/policies", response_model=list[SLAOut])
def sla_list(db: Session = Depends(get_db), _=Depends(current_user)):
    return db.scalars(scoped(select(SLAPolicy), SLAPolicy, _).order_by(SLAPolicy.module, SLAPolicy.priority)).all()

@app.post("/api/sla/policies", response_model=SLAOut, status_code=201)
def sla_create(body: SLAIn, db: Session = Depends(get_db), u=Depends(admin_only)):
    p = SLAPolicy(tenant_id=u.tenant_id, **body.model_dump()); db.add(p); db.flush(); audit.log(db, u.id, "create", "sla", p.id); db.commit(); return p

@app.post("/api/sla/refresh")
def sla_refresh(db: Session = Depends(get_db), u=Depends(staff)):
    return {"newly_breached": sla.refresh_breaches(db, u.tenant_id)}

@app.post("/api/sla/escalate")
def sla_escalate(db: Session = Depends(get_db), u=Depends(staff)):
    """Run the background SLA/escalation job now (it also runs every SLA_JOB_SECONDS via APScheduler)."""
    return sla.escalate(db, u.tenant_id)

# ---------- notifications ----------
@app.get("/api/notifications")
def notifications(unread: bool = False, db: Session = Depends(get_db), u=Depends(current_user)):
    s = scoped(select(Notification), Notification, u).where(or_(Notification.user_id == u.id, (Notification.user_id == None) & (Notification.group_id == u.group_id) & (Notification.group_id != None)))
    if unread: s = s.where(Notification.read == False)
    rows = db.scalars(s.order_by(Notification.id.desc()).limit(50)).all()
    return [{"id": n.id, "kind": n.kind, "title": n.title, "link": n.link, "read": n.read, "created_at": n.created_at} for n in rows]

@app.post("/api/notifications/{nid}/read")
def notification_read(nid: int, db: Session = Depends(get_db), u=Depends(current_user)):
    n = get_or_404(db, Notification, nid, u); n.read = True; db.commit(); return {"ok": True}

@app.post("/api/notifications/read-all")
def notification_read_all(db: Session = Depends(get_db), u=Depends(current_user)):
    for n in db.scalars(scoped(select(Notification), Notification, u).where(or_(Notification.user_id == u.id, Notification.group_id == u.group_id))): n.read = True
    db.commit(); return {"ok": True}

# ---------- AI ----------
@app.post("/api/ai/triage")
def ai_triage(body: TriageIn, db: Session = Depends(get_db), _=Depends(current_user)):
    return ai.triage(db, body.title, body.description, _.tenant_id)

@app.get("/api/ai/kb-suggest")
def ai_kb(q: str, db: Session = Depends(get_db), _=Depends(current_user)):
    return ai.kb_suggest(db, q, 5, _.tenant_id)

# ---------- audit ----------
@app.get("/api/audit", response_model=list[AuditOut])
def audit_list(limit: int = 100, db: Session = Depends(get_db), _=Depends(admin_only)):
    return db.scalars(select(AuditLog).where(or_(AuditLog.tenant_id == _.tenant_id, AuditLog.tenant_id == None)).order_by(AuditLog.id.desc()).limit(limit)).all()

@app.get("/api/audit/verify")
def audit_verify(db: Session = Depends(get_db), _=Depends(admin_only)):
    return audit.verify_chain(db)

# ---------- dashboard ----------
@app.get("/api/dashboard/metrics")
def metrics(db: Session = Depends(get_db), _=Depends(staff)):
    sla.refresh_breaches(db, _.tenant_id)
    recs = db.scalars(scoped(select(Record), Record, _)).all()
    inc = [r for r in recs if r.module == "incident"]
    open_inc = [r for r in inc if r.state not in registry.CLOSED]
    resolved = [r for r in inc if r.resolved_at]
    mttr = round(sum((r.resolved_at - r.created_at).total_seconds() for r in resolved) / 3600 / len(resolved), 1) if resolved else 0
    with_sla = [r for r in inc if r.sla_due_at]
    compliance = round(100 * (1 - sum(r.sla_breached for r in with_sla) / len(with_sla)), 1) if with_sla else 100
    ai_routed = [r for r in inc if r.ai_suggestion.get("auto_apply")]
    t = now(); days = [(t - timedelta(days=i)).date() for i in range(13, -1, -1)]
    created = Counter(r.created_at.date() for r in inc); res_c = Counter(r.resolved_at.date() for r in resolved)
    groups = {g.id: g.name for g in db.scalars(scoped(select(Group), Group, _))}
    return {
        "totals": {m: sum(1 for r in recs if r.module == m) for m in ("incident", "problem", "change", "request")},
        "all_totals": {m: n for m, n in Counter(r.module for r in recs).items()},
        "open_incidents": len(open_inc),
        "p1_open": sum(1 for r in open_inc if r.priority == "P1"),
        "sla_breached": sum(1 for r in open_inc if r.sla_breached),
        "sla_at_risk": sum(1 for r in open_inc if sla.sla_status(r) == "at_risk"),
        "sla_compliance_pct": compliance, "mttr_hours": mttr,
        "ai_auto_routed_pct": round(100 * len(ai_routed) / len(inc), 1) if inc else 0,
        "pending_approvals": db.scalar(select(func.count()).select_from(Approval).join(Record, Record.id == Approval.record_id).where(Approval.state == "requested", Record.tenant_id == _.tenant_id)),
        "by_priority": [{"name": p, "value": sum(1 for r in open_inc if r.priority == p)} for p in ("P1", "P2", "P3", "P4")],
        "by_state": [{"name": k, "value": v} for k, v in Counter(r.state for r in inc).items()],
        "by_category": [{"name": k, "value": v} for k, v in Counter(r.category for r in inc).most_common()],
        "by_group": [{"name": groups.get(k, "Unassigned"), "value": v} for k, v in Counter(r.assignment_group_id for r in open_inc).most_common()],
        "trend": [{"date": d.isoformat()[5:], "created": created.get(d, 0), "resolved": res_c.get(d, 0)} for d in days],
    }
