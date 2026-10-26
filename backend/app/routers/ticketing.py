"""Phase 2 — ticketing core: categories, custom fields, priority matrix, canned replies, tasks, watchers,
saved views, bulk edit, merge, spam, duplicate detection, history, live updates (SSE), notification templates."""
import asyncio, json, re, threading, time
from collections import deque
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from .. import audit, ai, bus, registry, settings_store
from ..db import get_db
from ..deps import get_record, out, notify, link_for
from ..models import Record, Comment, AuditLog, User
from ..schemas import RecordDetail
from ..security import current_user, staff, admin_only, decode

router = APIRouter(prefix="/api")

DEFAULT_CATEGORIES = ["Hardware", "Software", "Network", "Access", "Email", "Security", "General"]
DEFAULT_CANNED = [
    {"id": 1, "title": "Looking into it", "body": "Thanks for letting us know. I'm looking into this now and will update you shortly."},
    {"id": 2, "title": "Need more detail", "body": "Could you share a screenshot and the exact time this happened? That will help us fix it faster."},
    {"id": 3, "title": "Resolved", "body": "This should be fixed now. Please reply if anything still looks wrong, and we'll jump back in."},
]
DEFAULT_TEMPLATES = {
    "assigned": "{number} has been assigned to you: {title}",
    "resolved": "Good news! {number} has been resolved: {title}",
    "commented": "There's a new reply on {number}: {title}",
}

def _cfg(db, tid, key, default):
    v = settings_store.get(db, tid, key).get("v")
    return default if v is None else v

def _put(db, tid, key, value):
    settings_store.put(db, tid, key, {"v": value})

def load_matrix(db):
    try: ai.MATRIX.clear(); ai.MATRIX.update(_cfg(db, 1, "ticket.matrix", {}) or {})
    except Exception: pass

# ---------- configuration (field manager, categories, matrix, canned, templates) ----------
@router.get("/ticketing/config")
def get_config(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"categories": _cfg(db, u.tenant_id, "ticket.categories", DEFAULT_CATEGORIES),
            "fields": _cfg(db, u.tenant_id, "ticket.fields", []),
            "matrix": {f"{i},{j}": ai.priority_from(i, j) for i in range(1, 4) for j in range(1, 4)},
            "canned": _cfg(db, u.tenant_id, "ticket.canned", DEFAULT_CANNED),
            "templates": {**DEFAULT_TEMPLATES, **(_cfg(db, u.tenant_id, "ticket.templates", {}) or {})}}

FIELD_TYPES = {"text", "number", "select", "date", "checkbox"}
class ConfigIn(BaseModel):
    categories: list[str] | None = None; fields: list[dict] | None = None; matrix: dict[str, str] | None = None
    canned: list[dict] | None = None; templates: dict[str, str] | None = None

@router.put("/ticketing/config")
def put_config(body: ConfigIn, u: User = Depends(admin_only), db: Session = Depends(get_db)):
    if body.categories is not None:
        cats = [c.strip() for c in body.categories if c.strip()]
        if not cats: raise HTTPException(400, "Keep at least one category.")
        _put(db, u.tenant_id, "ticket.categories", list(dict.fromkeys(cats)))
    if body.fields is not None:
        clean = []
        for f in body.fields:
            key = re.sub(r"[^a-z0-9_]", "_", str(f.get("label", "")).strip().lower()).strip("_")
            if not key: continue
            t = f.get("type", "text")
            if t not in FIELD_TYPES: raise HTTPException(400, f"Unknown field type: {t}")
            clean.append({"key": f.get("key") or key, "label": f["label"].strip(), "type": t, "options": [o for o in f.get("options", []) if o],
                          "required": bool(f.get("required")), "modules": f.get("modules") or ["incident"]})
        _put(db, u.tenant_id, "ticket.fields", clean)
    if body.matrix is not None:
        m = {k: v for k, v in body.matrix.items() if re.fullmatch(r"[1-3],[1-3]", k) and v in ("P1", "P2", "P3", "P4")}
        _put(db, u.tenant_id, "ticket.matrix", m); ai.MATRIX.clear(); ai.MATRIX.update(m)
    if body.canned is not None:
        _put(db, u.tenant_id, "ticket.canned", [{"id": i + 1, "title": c["title"].strip(), "body": c["body"].strip()} for i, c in enumerate(body.canned) if c.get("title", "").strip()])
    if body.templates is not None:
        _put(db, u.tenant_id, "ticket.templates", {k: v for k, v in body.templates.items() if k in DEFAULT_TEMPLATES and v.strip()})
    audit.log(db, u.id, "ticketing.config", "settings", 0, {k: True for k, v in body.model_dump().items() if v is not None}); db.commit()
    return get_config(u, db)

def render_template(db, tid, key, r):
    t = {**DEFAULT_TEMPLATES, **(_cfg(db, tid, "ticket.templates", {}) or {})}[key]
    return t.format(number=r.number, title=r.title, state=r.state, priority=r.priority)

# ---------- tasks & watchers ----------
def _rec(db, module, rid, u):
    r = get_record(db, module, rid, u); r.data = dict(r.data or {}); return r

def _save(db, r):
    flag_modified(r, "data"); db.commit(); db.refresh(r); return out(r, RecordDetail)

class TaskIn(BaseModel):
    title: str; assignee_id: int | None = None

@router.post("/records/{module}/{rid}/tasks", response_model=RecordDetail)
def add_task(module: str, rid: int, body: TaskIn, u=Depends(staff), db: Session = Depends(get_db)):
    r = _rec(db, module, rid, u)
    if not body.title.strip(): raise HTTPException(400, "Give the task a short title.")
    tasks = list(r.data.get("tasks", []))
    tasks.append({"id": max([t["id"] for t in tasks] or [0]) + 1, "title": body.title.strip(), "done": False, "assignee_id": body.assignee_id})
    r.data["tasks"] = tasks; audit.log(db, u.id, "task.add", module, r.number, {"title": body.title.strip()})
    return _save(db, r)

@router.post("/records/{module}/{rid}/tasks/{tid}/toggle", response_model=RecordDetail)
def toggle_task(module: str, rid: int, tid: int, u=Depends(staff), db: Session = Depends(get_db)):
    r = _rec(db, module, rid, u); tasks = [dict(t) for t in r.data.get("tasks", [])]
    t = next((t for t in tasks if t["id"] == tid), None)
    if not t: raise HTTPException(404, "Not found")
    t["done"] = not t["done"]; r.data["tasks"] = tasks
    audit.log(db, u.id, "task.done" if t["done"] else "task.reopen", module, r.number, {"title": t["title"]})
    flag_modified(r, "data"); bus.emit(db, r, "updated", u, {"data.tasks": [None, None]})
    return _save(db, r)

@router.post("/records/{module}/{rid}/watch", response_model=RecordDetail)
def watch(module: str, rid: int, on: bool = True, user_id: int | None = None, u=Depends(current_user), db: Session = Depends(get_db)):
    r = _rec(db, module, rid, u); who = user_id if (user_id and u.role != "end_user") else u.id
    w = set(r.data.get("watchers", []))
    (w.add if on else w.discard)(who); r.data["watchers"] = sorted(w)
    return _save(db, r)

# ---------- history ----------
@router.get("/records/{module}/{rid}/history")
def history(module: str, rid: int, u=Depends(current_user), db: Session = Depends(get_db)):
    r = get_record(db, module, rid, u)
    rows = db.scalars(select(AuditLog).where(AuditLog.entity == module, AuditLog.entity_id == r.number).order_by(AuditLog.id)).all()
    names = {x.id: x.full_name for x in db.scalars(select(User).where(User.id.in_({a.actor_id for a in rows if a.actor_id})))}
    return [{"ts": a.ts, "action": a.action, "actor": names.get(a.actor_id, "Neurealm Service Desk"), "details": a.details} for a in rows]

# ---------- duplicates ----------
_STOP = set("the a an is to of and in on for my with not cannot can't can i it at from be".split())
def _tokens(s): return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 2 and w not in _STOP}

def find_duplicates(db, r, limit=5):
    a = _tokens(r.title + " " + (r.description or "")[:200]); res = []
    if not a: return res
    for o in db.scalars(select(Record).where(Record.module == r.module, Record.tenant_id == r.tenant_id, Record.id != r.id).order_by(Record.id.desc()).limit(500)):
        if o.state in registry.CLOSED: continue
        b = _tokens(o.title + " " + (o.description or "")[:200])
        score = len(a & b) / len(a | b) if b else 0
        if score >= 0.3: res.append({"id": o.id, "number": o.number, "title": o.title, "state": o.state, "score": round(score, 2)})
    return sorted(res, key=lambda x: -x["score"])[:limit]

@router.get("/records/{module}/{rid}/duplicates")
def duplicates(module: str, rid: int, u=Depends(staff), db: Session = Depends(get_db)):
    return find_duplicates(db, get_record(db, module, rid, u))

def _close_state(module):
    flow = registry.MODULES[module].get("flow", {})
    for s in ("cancelled", "closed", "resolved"):
        if s in flow or any(s in v for v in flow.values()): return s
    return "closed"

class MergeIn(BaseModel):
    into: int

@router.post("/records/{module}/{rid}/merge", response_model=RecordDetail)
def merge(module: str, rid: int, body: MergeIn, u=Depends(staff), db: Session = Depends(get_db)):
    src = _rec(db, module, rid, u); dst = _rec(db, module, body.into, u)
    if src.id == dst.id: raise HTTPException(400, "A ticket can't be merged into itself.")
    if src.state in registry.CLOSED: raise HTTPException(400, "This ticket is already closed.")
    for c in src.comments:
        db.add(Comment(record_id=dst.id, author_id=c.author_id, body=f"[from {src.number}] {c.body}", internal=c.internal, created_at=c.created_at))
    db.add(Comment(record_id=dst.id, author_id=u.id, body=f"Merged {src.number} into this ticket: {src.title}", internal=True))
    db.add(Comment(record_id=src.id, author_id=u.id, body=f"Merged into {dst.number}. Updates will continue there.", internal=False))
    w = set(dst.data.get("watchers", [])) | set(src.data.get("watchers", [])) | ({src.requester_id} if src.requester_id else set())
    dst.data["watchers"] = sorted(w); flag_modified(dst, "data")
    src.data["merged_into"] = dst.number; src.state = _close_state(module); flag_modified(src, "data")
    if dst not in src.linked: src.linked.append(dst)
    audit.log(db, u.id, "merge", module, src.number, {"into": dst.number})
    bus.emit(db, src, "updated", u, {"state": ["", src.state]}); db.commit(); db.refresh(dst)
    return out(dst, RecordDetail)

@router.post("/records/{module}/{rid}/spam", response_model=RecordDetail)
def spam(module: str, rid: int, u=Depends(staff), db: Session = Depends(get_db)):
    r = _rec(db, module, rid, u); r.data["spam"] = True; r.state = _close_state(module)
    audit.log(db, u.id, "spam", module, r.number); return _save(db, r)

# ---------- bulk ----------
class BulkIn(BaseModel):
    ids: list[int]; state: str | None = None; priority: str | None = None; assignee_id: int | None = None
    assignment_group_id: int | None = None; category: str | None = None

@router.post("/records/{module}/bulk")
def bulk(module: str, body: BulkIn, u=Depends(staff), db: Session = Depends(get_db)):
    if not body.ids: raise HTTPException(400, "Pick at least one ticket.")
    if len(body.ids) > 200: raise HTTPException(400, "Please update up to 200 tickets at a time.")
    done, skipped = [], []
    for rid in body.ids:
        r = get_record(db, module, rid, u); ch = {}
        if body.state and body.state != r.state:
            if body.state not in registry.allowed(module, r.state): skipped.append({"number": r.number, "reason": f"can't move from {r.state}"}); continue
            ch["state"] = [r.state, body.state]; r.state = body.state
        for k in ("priority", "assignee_id", "assignment_group_id", "category"):
            v = getattr(body, k)
            if v is not None and getattr(r, k) != v: ch[k] = [getattr(r, k), v]; setattr(r, k, v)
        if ch:
            if "assignee_id" in ch and r.assignee_id: notify(db, u.tenant_id, render_template(db, u.tenant_id, "assigned", r), "info", r.assignee_id, None, link_for(r))
            audit.log(db, u.id, "bulk.update", module, r.number, {k: [str(a), str(b)] for k, (a, b) in ch.items()}); bus.emit(db, r, "updated", u, ch)
            done.append(r.number)
    db.commit()
    return {"updated": done, "skipped": skipped}

# ---------- saved views ----------
class ViewIn(BaseModel):
    name: str; module: str = "incident"; filters: dict = {}

@router.get("/views")
def list_views(u=Depends(current_user), db: Session = Depends(get_db)):
    return _cfg(db, u.tenant_id, f"views.{u.id}", [])

@router.post("/views")
def save_view(body: ViewIn, u=Depends(current_user), db: Session = Depends(get_db)):
    if not body.name.strip(): raise HTTPException(400, "Give the view a name.")
    vs = [v for v in _cfg(db, u.tenant_id, f"views.{u.id}", []) if v["name"] != body.name.strip()]
    allowed = {k: v for k, v in body.filters.items() if k in ("state", "priority", "q", "mine", "unassigned", "category")}
    vs.append({"id": max([v["id"] for v in vs] or [0]) + 1, "name": body.name.strip(), "module": body.module, "filters": allowed})
    _put(db, u.tenant_id, f"views.{u.id}", vs); db.commit(); return vs

@router.delete("/views/{vid}")
def delete_view(vid: int, u=Depends(current_user), db: Session = Depends(get_db)):
    vs = [v for v in _cfg(db, u.tenant_id, f"views.{u.id}", []) if v["id"] != vid]
    _put(db, u.tenant_id, f"views.{u.id}", vs); db.commit(); return vs

# ---------- live updates ----------
_events: deque = deque(maxlen=500); _seq = [0]; _lock = threading.Lock()

@bus.subscribe
def _publish(db, r, event, actor, changes):
    with _lock:
        _seq[0] += 1
        _events.append({"seq": _seq[0], "tenant_id": r.tenant_id, "module": r.module, "id": r.id, "number": r.number, "event": event,
                        "by": getattr(actor, "full_name", None), "by_id": getattr(actor, "id", None), "fields": sorted(changes.keys()), "at": time.time()})

def events_since(tid, cursor):
    with _lock: return [e for e in _events if e["seq"] > cursor and e["tenant_id"] == tid]

@router.get("/live/since")
def live_since(cursor: int = 0, u=Depends(current_user)):
    return {"cursor": _seq[0], "events": events_since(u.tenant_id, cursor)}

@router.get("/live/stream")
async def live_stream(request: Request, token: str, db: Session = Depends(get_db)):
    p = decode(token); u = db.get(User, int(p["sub"]))
    if not u or not u.active: raise HTTPException(401)
    tid = u.tenant_id; db.close()
    async def gen():
        cur = _seq[0]; yield f"event: hello\ndata: {json.dumps({'cursor': cur})}\n\n"; ticks = 0
        while not await request.is_disconnected():
            evs = events_since(tid, cur)
            for e in evs: cur = e["seq"]; yield f"data: {json.dumps(e)}\n\n"
            ticks += 1
            if ticks % 15 == 0: yield ": ping\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ---------- attachments (Phase 2 remainder) ----------
from fastapi import UploadFile, File
from fastapi.responses import Response
from ..models import Attachment
MAX_ATTACH = 5 * 1024 * 1024
BLOCKED_EXT = (".exe", ".bat", ".cmd", ".sh", ".js", ".msi", ".scr", ".ps1")

def _att(a): return {"id": a.id, "filename": a.filename, "content_type": a.content_type, "size": a.size, "created_at": a.created_at, "uploaded_by": a.uploaded_by}

@router.get("/records/{module}/{rid}/attachments")
def list_attachments(module: str, rid: int, u=Depends(current_user), db: Session = Depends(get_db)):
    r = get_record(db, module, rid, u)
    return [_att(a) for a in db.scalars(select(Attachment).where(Attachment.record_id == r.id).order_by(Attachment.id))]

@router.post("/records/{module}/{rid}/attachments", status_code=201)
async def upload_attachment(module: str, rid: int, file: UploadFile = File(...), u=Depends(current_user), db: Session = Depends(get_db)):
    r = get_record(db, module, rid, u); data = await file.read()
    name = (file.filename or "file").replace("/", "_").replace("\\", "_")[:200]
    if len(data) > MAX_ATTACH: raise HTTPException(413, "That file is over 5 MB. Please attach something smaller.")
    if not data: raise HTTPException(400, "That file is empty.")
    if name.lower().endswith(BLOCKED_EXT): raise HTTPException(400, "For safety, program and script files can't be attached.")
    a = Attachment(tenant_id=u.tenant_id, record_id=r.id, filename=name, content_type=(file.content_type or "application/octet-stream")[:100], size=len(data), blob=data, uploaded_by=u.id)
    db.add(a); db.flush(); audit.log(db, u.id, "attachment.add", module, r.number, {"file": name, "size": len(data)}); db.commit(); return _att(a)

@router.get("/attachments/{aid}")
def download_attachment(aid: int, u=Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Attachment, aid)
    if not a or a.tenant_id != u.tenant_id: raise HTTPException(404, "Not found")
    r = db.get(Record, a.record_id); get_record(db, r.module, r.id, u)
    return Response(a.blob, media_type=a.content_type, headers={"Content-Disposition": f'attachment; filename="{a.filename}"', "X-Content-Type-Options": "nosniff"})

@router.delete("/attachments/{aid}")
def delete_attachment(aid: int, u=Depends(staff), db: Session = Depends(get_db)):
    a = db.get(Attachment, aid)
    if not a or a.tenant_id != u.tenant_id: raise HTTPException(404, "Not found")
    r = db.get(Record, a.record_id); db.delete(a); audit.log(db, u.id, "attachment.remove", r.module, r.number, {"file": a.filename}); db.commit(); return {"ok": True}
