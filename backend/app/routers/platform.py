"""Phase 9: platform and integrations.
- Email to ticket: inbound endpoint (token in URL, for any mail relay), replies thread onto the ticket by [NUMBER] in the subject.
- Alert ingest with admin rules (suppress / set severity / route) on top of event correlation.
- Directory sync (create, update, deactivate users) with dry run.
- Public REST API /api/v1 using personal API keys (Bearer nrsd_...).
- Tenant export (JSON backup, CSV per module) without secrets or password hashes.
- Error log (server exceptions + browser errors) for admins.
- Offboarding: deactivating a user when their offboarding case resolves (opt-in)."""
import csv, io, json, re, secrets, time, traceback, zipfile
from collections import deque
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Record, Comment, User, Group, KBArticle, Tenant, now
from ..security import current_user, staff, admin_only, hash_pw
from ..schemas import RecordCreate
from ..deps import out
from .. import audit, bus, registry, settings_store

router = APIRouter(prefix="/api", tags=["platform"])

def _cfg(db, tid, key, default): return {**default, **(settings_store.get(db, tid, key).get("v") or {})}
def _put(db, tid, key, v): settings_store.put(db, tid, key, {"v": v})

# ---------------- Email to ticket ----------------
EMAIL_DEF = {"enabled": False, "token": "", "module": "incident", "allow_unknown": False, "address": "support@neurealm.com"}

@router.get("/email/config")
def email_config(db: Session = Depends(get_db), u=Depends(admin_only)):
    c = _cfg(db, u.tenant_id, "email.inbound", EMAIL_DEF)
    return {**c, "token": (c["token"][:4] + "…") if c["token"] else "", "has_token": bool(c["token"]), "endpoint": f"/api/inbound/email/{u.tenant_id}?token=…"}

class EmailCfg(BaseModel):
    enabled: bool = False; module: str = "incident"; allow_unknown: bool = False; address: str = ""; rotate: bool = False

@router.put("/email/config")
def put_email_config(b: EmailCfg, db: Session = Depends(get_db), u=Depends(admin_only)):
    if b.module not in ("incident", "request"): raise HTTPException(400, "Emails can become incidents or requests")
    c = _cfg(db, u.tenant_id, "email.inbound", EMAIL_DEF); new = None
    if b.rotate or not c["token"]: new = c["token"] = secrets.token_urlsafe(24)
    c.update(enabled=b.enabled, module=b.module, allow_unknown=b.allow_unknown, address=b.address.strip())
    _put(db, u.tenant_id, "email.inbound", c); audit.log(db, u.id, "email.config", "settings", "email.inbound"); db.commit()
    return {**email_config(db, u), **({"token_once": new} if new else {})}

class InEmail(BaseModel):
    sender: str = Field(alias="from"); subject: str = ""; text: str = ""
    model_config = {"populate_by_name": True}

NUM = re.compile(r"\[([A-Z]{2,5}\d{5,})\]")

@router.post("/inbound/email/{tid}")
def inbound_email(tid: int, b: InEmail, token: str = "", db: Session = Depends(get_db)):
    c = _cfg(db, tid, "email.inbound", EMAIL_DEF)
    if not (c["enabled"] and c["token"] and secrets.compare_digest(token, c["token"])): raise HTTPException(401, "Invalid inbound token")
    addr = (re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", b.sender) or [""])[0].lower()
    who = db.scalar(select(User).where(User.tenant_id == tid, User.email == addr, User.active == True))  # noqa: E712
    admin = db.scalar(select(User).where(User.tenant_id == tid, User.role == "admin").order_by(User.id))
    body = re.split(r"\n\s*(On .+ wrote:|-----Original Message-----|From: )", b.text)[0].strip()[:20000]
    if (m := NUM.search(b.subject)):
        r = db.scalar(select(Record).where(Record.tenant_id == tid, Record.number == m.group(1)))
        if r and (who or c["allow_unknown"]):
            db.add(Comment(record_id=r.id, author_id=(who or admin).id, body=body or "(empty reply)", internal=False))
            if r.state in ("on_hold", "resolved", "pending"): r.state = "in_progress"
            audit.log(db, (who or admin).id, "email.reply", r.module, r.number, {"from": addr}); db.commit()
            return {"action": "commented", "number": r.number}
    if not who and not c["allow_unknown"]: raise HTTPException(403, "Sender isn't a known user")
    from ..main import create_record_core
    r = create_record_core(db, who or admin, c["module"], RecordCreate(title=(b.subject or "Email request")[:200], description=body, data={"channel": "email", "email_from": addr}))
    audit.log(db, (who or admin).id, "email.create", r.module, r.number, {"from": addr}); db.commit()
    return {"action": "created", "number": r.number, "id": r.id}

# ---------------- Alert rules + ingest ----------------
class Rule(BaseModel):
    name: str = Field(min_length=1, max_length=100); source: str = ""; severity: str = ""; contains: str = ""
    action: str = "create"; set_severity: str = ""; enabled: bool = True

@router.get("/alerts/rules")
def rules(db: Session = Depends(get_db), u=Depends(staff)): return settings_store.get(db, u.tenant_id, "alerts.rules").get("v") or []

@router.put("/alerts/rules")
def put_rules(b: list[Rule], db: Session = Depends(get_db), u=Depends(admin_only)):
    for r in b:
        if r.action not in ("create", "suppress", "set_severity"): raise HTTPException(400, f"Unknown action {r.action}")
        if r.action == "set_severity" and r.set_severity not in ("critical", "major", "minor", "warning", "info"): raise HTTPException(400, "Pick a severity to set")
    _put(db, u.tenant_id, "alerts.rules", [r.model_dump() for r in b[:50]]); audit.log(db, u.id, "alerts.rules", "settings", "alerts.rules"); db.commit()
    return rules(db, u)

def apply_rules(rs, e: dict):
    for r in rs:
        if not r.get("enabled", True): continue
        if r["source"] and r["source"].lower() != e.get("source", "").lower(): continue
        if r["severity"] and r["severity"].lower() != e.get("severity", "").lower(): continue
        if r["contains"] and r["contains"].lower() not in (e.get("message", "") + " " + e.get("metric", "") + " " + e.get("node", "")).lower(): continue
        if r["action"] == "suppress": return None, r["name"]
        if r["action"] == "set_severity": return {**e, "severity": r["set_severity"]}, r["name"]
        return e, r["name"]
    return e, None

@router.post("/alerts/ingest")
def ingest(body: list[dict] | dict, db: Session = Depends(get_db), u=Depends(staff)):
    from .itom import EventIn, ingest_event
    rs = rules(db, u); res = []
    for e in (body if isinstance(body, list) else [body]):
        try: ev_in = EventIn(**{k: e[k] for k in ("source", "node", "metric", "severity", "message") if k in e})
        except Exception: res.append({"action": "rejected", "reason": "node and metric are required"}); continue
        e2, rule = apply_rules(rs, ev_in.model_dump())
        if e2 is None: res.append({"action": "suppressed", "rule": rule}); continue
        ev, action = ingest_event(db, u, EventIn(**e2)); db.flush()
        res.append({"action": action, "rule": rule, "event_id": ev.id if ev else None, "incident_id": ev.incident_id if ev else None})
    db.commit(); return res

@router.post("/alerts/rules/test")
def test_rules(e: dict, db: Session = Depends(get_db), u=Depends(staff)):
    e2, rule = apply_rules(rules(db, u), e)
    return {"result": "suppressed" if e2 is None else "kept", "rule": rule, "event": e2}

# ---------------- Directory sync ----------------
class DirUser(BaseModel):
    email: str; name: str; active: bool = True; group: str = ""; role: str = ""

class DirSync(BaseModel):
    users: list[DirUser] = Field(max_length=2000); dry_run: bool = True; deactivate_missing: bool = False

@router.post("/directory/sync")
def directory_sync(b: DirSync, db: Session = Depends(get_db), u=Depends(admin_only)):
    have = {x.email.lower(): x for x in db.scalars(select(User).where(User.tenant_id == u.tenant_id))}
    groups = {g.name.lower(): g.id for g in db.scalars(select(Group).where(Group.tenant_id == u.tenant_id))}
    plan = {"create": [], "update": [], "deactivate": [], "errors": []}; seen = set()
    for i, d in enumerate(b.users):
        em = d.email.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", em): plan["errors"].append({"row": i, "error": "invalid email"}); continue
        if d.role and d.role not in ("end_user", "agent"): plan["errors"].append({"row": i, "error": "directory sync can't grant admin"}); continue
        seen.add(em); x = have.get(em); gid = groups.get(d.group.lower()) if d.group else None
        if not x:
            if d.active: plan["create"].append(em)
            if not b.dry_run and d.active:
                db.add(User(tenant_id=u.tenant_id, email=em, full_name=d.name, password_hash=hash_pw(secrets.token_urlsafe(18)), role=d.role or "end_user", group_id=gid, active=True))
            continue
        if x.id == u.id: continue
        ch = {}
        if d.name and d.name != x.full_name: ch["full_name"] = d.name
        if d.active != x.active: ch["active"] = d.active
        if gid and gid != x.group_id: ch["group_id"] = gid
        if d.role and d.role != x.role and x.role != "admin": ch["role"] = d.role
        if ch:
            (plan["deactivate"] if ch.get("active") is False else plan["update"]).append(em)
            if not b.dry_run:
                for k, v in ch.items(): setattr(x, k, v)
    if b.deactivate_missing:
        for em, x in have.items():
            if em not in seen and x.active and x.role != "admin" and x.id != u.id:
                plan["deactivate"].append(em)
                if not b.dry_run: x.active = False
    if not b.dry_run:
        audit.log(db, u.id, "directory.sync", "user", "-", {k: len(v) for k, v in plan.items()})
        _put(db, u.tenant_id, "directory.last", {"at": now().isoformat()[:16], **{k: len(v) for k, v in plan.items()}}); db.commit()
    return {"dry_run": b.dry_run, **plan}

@router.get("/directory/last")
def directory_last(db: Session = Depends(get_db), u=Depends(admin_only)): return settings_store.get(db, u.tenant_id, "directory.last").get("v") or {}

# ---------------- Public API v1 ----------------
v1 = APIRouter(prefix="/api/v1", tags=["public api v1"])

def _v1(r): return {"number": r.number, "module": r.module, "title": r.title, "description": r.description, "state": r.state, "priority": r.priority,
                    "category": r.category, "created_at": r.created_at.isoformat() if r.created_at else None, "data": r.data}

def _mod(m):
    if m not in registry.MODULES: raise HTTPException(404, "Unknown module")
    return m

@v1.get("/modules")
def v1_modules(u=Depends(staff)): return [{"key": k, "label": m["label"]} for k, m in registry.MODULES.items()]

@v1.get("/records/{module}")
def v1_list(module: str, state: str | None = None, limit: int = 50, offset: int = 0, db: Session = Depends(get_db), u=Depends(staff)):
    s = select(Record).where(Record.tenant_id == u.tenant_id, Record.module == _mod(module))
    if state: s = s.where(Record.state == state)
    return {"items": [_v1(r) for r in db.scalars(s.order_by(Record.id.desc()).offset(max(0, offset)).limit(min(200, max(1, limit))))], "limit": limit, "offset": offset}

@v1.get("/records/{module}/{number}")
def v1_get(module: str, number: str, db: Session = Depends(get_db), u=Depends(staff)):
    r = db.scalar(select(Record).where(Record.tenant_id == u.tenant_id, Record.module == _mod(module), Record.number == number))
    if not r: raise HTTPException(404, "Not found")
    return _v1(r)

class V1Create(BaseModel):
    title: str = Field(min_length=1, max_length=200); description: str = ""; data: dict = {}

@v1.post("/records/{module}", status_code=201)
def v1_create(module: str, b: V1Create, db: Session = Depends(get_db), u=Depends(staff)):
    from ..main import create_record_core
    r = create_record_core(db, u, _mod(module), RecordCreate(title=b.title, description=b.description, data={**b.data, "channel": "api"}))
    audit.log(db, u.id, "api.create", module, r.number); db.commit(); return _v1(r)

@v1.post("/records/{module}/{number}/comments", status_code=201)
def v1_comment(module: str, number: str, b: dict, db: Session = Depends(get_db), u=Depends(staff)):
    r = db.scalar(select(Record).where(Record.tenant_id == u.tenant_id, Record.module == _mod(module), Record.number == number))
    if not r or not str(b.get("body", "")).strip(): raise HTTPException(404 if not r else 400, "Not found" if not r else "body is required")
    db.add(Comment(record_id=r.id, author_id=u.id, body=str(b["body"])[:20000], internal=bool(b.get("internal")))); db.commit(); return {"ok": True}

# ---------------- Export / backup ----------------
SECRETS = {"api_key", "secret", "token", "password", "key"}
def _scrub(d):
    if isinstance(d, dict): return {k: ("***" if any(s in k.lower() for s in SECRETS) else _scrub(v)) for k, v in d.items()}
    if isinstance(d, list): return [_scrub(x) for x in d]
    return d

@router.get("/admin/export")
def export(fmt: str = "json", db: Session = Depends(get_db), u=Depends(admin_only)):
    recs = db.scalars(select(Record).where(Record.tenant_id == u.tenant_id).order_by(Record.id)).all()
    users = [{"email": x.email, "name": x.full_name, "role": x.role, "active": x.active} for x in db.scalars(select(User).where(User.tenant_id == u.tenant_id))]
    kb = [{"number": k.number, "title": k.title, "body": k.body, "category": k.category} for k in db.scalars(select(KBArticle).where(KBArticle.tenant_id == u.tenant_id))]
    audit.log(db, u.id, "export", "tenant", u.tenant_id, {"fmt": fmt}); db.commit()
    stamp = now().strftime("%Y%m%d-%H%M")
    if fmt == "zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for m in sorted({r.module for r in recs}):
                s = io.StringIO(); w = csv.writer(s); w.writerow(["number", "title", "state", "priority", "category", "created_at", "data"])
                for r in recs:
                    if r.module == m: w.writerow([r.number, r.title, r.state, r.priority, r.category, r.created_at, json.dumps(_scrub(r.data))])
                z.writestr(f"{m}.csv", s.getvalue())
            z.writestr("users.json", json.dumps(users, indent=1)); z.writestr("knowledge.json", json.dumps(kb, indent=1))
        return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="servicedesk-export-{stamp}.zip"'})
    data = {"exported_at": now().isoformat(), "version": 1, "records": [{**_v1(r), "data": _scrub(r.data)} for r in recs], "users": users, "knowledge": kb}
    return Response(json.dumps(data, default=str), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="servicedesk-backup-{stamp}.json"'})

# ---------------- Error log ----------------
ERRORS: deque = deque(maxlen=300)
def record_error(kind, message, path="", detail="", user=None):
    ERRORS.appendleft({"id": int(time.time() * 1000) % 10**10, "at": now().isoformat()[:19], "kind": kind, "message": str(message)[:500], "path": path[:300], "detail": detail[-4000:], "user": user})

@router.post("/errors/client", status_code=202)
def client_error(b: dict, u=Depends(current_user)):
    record_error("browser", b.get("message", "Unknown error"), b.get("path", ""), str(b.get("stack", ""))[:4000], u.email); return {"ok": True}

@router.get("/admin/errors")
def errors(u=Depends(admin_only)): return list(ERRORS)

@router.delete("/admin/errors")
def clear_errors(u=Depends(admin_only)): ERRORS.clear(); return {"ok": True}

def install(app):
    from fastapi.responses import JSONResponse
    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        record_error("server", f"{type(exc).__name__}: {exc}", request.url.path, "".join(traceback.format_exception(exc)))
        return JSONResponse({"detail": "Something went wrong on our side. It has been logged for the admins."}, status_code=500)
    app.include_router(router); app.include_router(v1)

# ---------------- Offboarding: deactivate on completion ----------------
@router.get("/hr/settings")
def hr_settings(db: Session = Depends(get_db), u=Depends(staff)): return _cfg(db, u.tenant_id, "hr.lifecycle", {"deactivate_on_offboard": False})

@router.put("/hr/settings")
def put_hr_settings(b: dict, db: Session = Depends(get_db), u=Depends(admin_only)):
    _put(db, u.tenant_id, "hr.lifecycle", {"deactivate_on_offboard": bool(b.get("deactivate_on_offboard"))}); db.commit(); return hr_settings(db, u)

@bus.subscribe
def offboard_deactivate(db, r, event, actor, changes):
    if r.module != "hr_case" or r.data.get("lifecycle") != "offboarding" or r.state not in ("resolved", "closed"): return
    if not _cfg(db, r.tenant_id, "hr.lifecycle", {"deactivate_on_offboard": False})["deactivate_on_offboard"]: return
    em = str(r.data.get("employee_email") or "").lower()
    x = db.scalar(select(User).where(User.tenant_id == r.tenant_id, User.email == em)) if em else None
    if x and x.active and x.role != "admin":
        x.active = False; audit.log(db, actor.id if actor else None, "offboard.deactivate", "user", x.id, {"case": r.number})
