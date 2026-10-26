"""No-code workflow builder engine.
A workflow targets one module, several modules, or all ("*"). Graph of nodes:
  trigger -> condition {field, op, value} (edges sourceHandle 'true'/'false') -> action {...}
Triggers: created, updated, state_changed, field_changed, field_condition, sla_warning, sla_breach, schedule.
Conditions work on any field incl. form-designer custom fields (stored in record.data).
Actions: set_field, assign (group/user), assign_group, add_comment, notify (group/requester/user), notify_group, notify_requester,
create_record (related record in another module), approval (pauses until decided), webhook, wait (pauses N minutes),
connector, run_autoresolve. Every save creates a version; every execution writes a run (history)."""
from datetime import timedelta
from urllib.parse import urlparse
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import WorkflowDef, WorkflowVersion, WorkflowRun, Record, Group, User, Comment, Approval, now
from .security import staff, admin_only
from .deps import scoped, get_or_404, notify, link_for
from . import bus, audit, registry

TOP = {"title", "description", "state", "priority", "category", "impact", "urgency", "module", "number"}
TRIGGERS = ["created", "updated", "state_changed", "field_changed", "field_condition", "sla_warning", "sla_breach", "schedule"]
ACTIONS = ["set_field", "assign", "assign_group", "add_comment", "notify", "notify_group", "notify_requester", "create_record", "approval", "webhook", "wait", "connector", "run_autoresolve"]
OPS = ["eq", "neq", "contains", "in", "gt", "lt", "empty", "filled", "changed"]
CLOSED = ("resolved", "closed", "cancelled", "canceled", "done", "complete", "completed", "retired")

def _val(r, f):
    if f.startswith("data."): f = f[5:]
    if f == "assignment_group": return r.assignment_group.name if r.assignment_group_id and r.assignment_group else None
    return getattr(r, f) if f in TOP else (r.data or {}).get(f)

def cond(r, d, changes=None):
    f = d.get("field", ""); v, op, x = _val(r, f), d.get("op", "eq"), d.get("value")
    if op == "changed": return bool(changes) and (f in changes or f"data.{f}" in changes)
    vals = [str(i).lower() for i in v] if isinstance(v, list) else [str(v if v is not None else "").lower()]
    s = vals[0] if len(vals) == 1 else ",".join(vals); xs = str(x if x is not None else "").lower()
    ops = {"eq": lambda: xs in vals, "neq": lambda: xs not in vals, "contains": lambda: xs in s, "in": lambda: any(i in [p.strip() for p in xs.split(",")] for i in vals),
           "gt": lambda: float(v or 0) > float(x or 0), "lt": lambda: float(v or 0) < float(x or 0), "empty": lambda: v in (None, "", [], False), "filled": lambda: v not in (None, "", [], False)}
    try: return bool(ops[op]())
    except (ValueError, KeyError, TypeError): return False

def _tpl(text, r):
    try: return (text or "").replace("{number}", r.number or "").replace("{title}", r.title or "").replace("{priority}", r.priority or "").replace("{state}", r.state or "")
    except Exception: return text or ""

class Pause(Exception):
    def __init__(self, kind, minutes=0, approval_id=None): self.kind, self.minutes, self.approval_id = kind, minutes, approval_id

def act(db, r, d, actor, dry):
    t = d.get("action"); desc = f"{t}"
    if dry:
        if t in ("wait", "approval"): return f"{t} (would pause)"
        return f"{t}: {({k: v for k, v in d.items() if k not in ('label', 'action')})}"
    if t == "set_field":
        f, v = d.get("field", ""), d.get("value")
        if f.startswith("data."): f = f[5:]
        if f in ("priority", "category", "state", "title"): setattr(r, f, v)
        elif f in ("impact", "urgency"): setattr(r, f, int(v))
        else:
            from . import forms
            r.data = forms.apply(db, r.tenant_id, r.module, {**(r.data or {}), f: v})
        desc = f"set {f} = {v}"
    elif t in ("assign_group", "assign"):
        if d.get("group"):
            g = db.scalar(select(Group).where(Group.tenant_id == r.tenant_id, Group.name == d.get("group")))
            if g: r.assignment_group_id = g.id; desc = f"assigned to group {g.name}"
        if d.get("user_id"):
            u = db.get(User, int(d["user_id"]))
            if u and u.tenant_id == r.tenant_id: r.assignee_id = u.id; desc = f"assigned to {u.full_name}"
    elif t == "add_comment":
        db.add(Comment(record_id=r.id, author_id=actor.id if actor else None, body=f"⚙️ {_tpl(d.get('text', ''), r)}", internal=bool(d.get("internal", True))))
    elif t in ("notify", "notify_group", "notify_requester"):
        to = d.get("to") or ("requester" if t == "notify_requester" else "group")
        text = _tpl(d.get("text"), r) or f"Workflow update on {r.number}"
        if to == "requester": notify(db, r.tenant_id, text, "info", r.requester_id, None, link_for(r))
        elif to == "user" and d.get("user_id"): notify(db, r.tenant_id, text, "info", int(d["user_id"]), None, link_for(r))
        else:
            g = db.scalar(select(Group).where(Group.tenant_id == r.tenant_id, Group.name == d.get("group"))) if d.get("group") else None
            notify(db, r.tenant_id, text, "info", None, g.id if g else r.assignment_group_id, link_for(r))
        desc = f"notified {to}"
    elif t == "create_record":
        m = d.get("module")
        if m not in registry.MODULES: raise ValueError(f"unknown module {m}")
        from .main import create_record_core
        from .schemas import RecordCreate
        who = actor or db.get(User, r.requester_id)
        nr = create_record_core(db, who, m, RecordCreate(title=_tpl(d.get("title") or f"Follow-up for {{number}}", r), description=_tpl(d.get("text") or r.description, r), use_ai=False, data={}), emit=True)
        r.linked.append(nr); desc = f"created {nr.number} in {m}"
    elif t == "approval":
        ap = Approval(record_id=r.id, approver_id=int(d["approver_id"]) if d.get("approver_id") else None, level=int(d.get("level", 1)), state="requested")
        db.add(ap); db.flush()
        if ap.approver_id: notify(db, r.tenant_id, f"Approval needed: {r.number} {r.title}", "approval", ap.approver_id, None, link_for(r))
        raise Pause("approval", approval_id=ap.id)
    elif t == "wait":
        raise Pause("wait", minutes=float(d.get("minutes", 5)))
    elif t == "webhook":
        url = d.get("url", "")
        if urlparse(url).scheme not in ("http", "https"): raise ValueError("webhook needs an http(s) URL")
        payload = {"event": "workflow", "number": r.number, "module": r.module, "title": r.title, "state": r.state, "priority": r.priority, "data": r.data}
        try: resp = httpx.post(url, json=payload, timeout=5); desc = f"webhook {resp.status_code}"
        except Exception as e: desc = f"webhook error: {str(e)[:80]}"
    elif t == "connector":
        from .integrations import send
        send(db, r.tenant_id, d.get("kind", "webhook"), "workflow", r)
    elif t == "run_autoresolve" and actor:
        from .autoresolve import run
        run(db, r, actor)
    return desc

def execute(db, wf, r, actor, dry=False, start=None, changes=None, run=None, event="manual", branch=None):
    nodes = {n["id"]: n for n in wf.nodes}; trace = list(run.trace) if run else []
    out_edges = {}
    for e in wf.edges: out_edges.setdefault(e["source"], []).append(e)
    def nxt(nid, handle=None): return [e["target"] for e in out_edges.get(nid, []) if handle is None or (e.get("sourceHandle") or "true") == handle]
    frontier = list(start) if start is not None else [n["id"] for n in wf.nodes if n.get("type") == "trigger"]
    seen = set(); steps = 0; pause = None; resume = []
    while frontier and steps < 60:
        nid = frontier.pop(0)
        if nid in seen or nid not in nodes: continue
        seen.add(nid); steps += 1; n = nodes[nid]; d = n.get("data", {}); typ = n.get("type"); handle = None
        if typ == "condition":
            ok = cond(r, d, changes); handle = "true" if ok else "false"; trace.append({"node": nid, "type": typ, "result": ok})
        elif typ == "action":
            try: trace.append({"node": nid, "type": typ, "did": act(db, r, d, actor, dry)})
            except Pause as p:
                trace.append({"node": nid, "type": typ, "did": f"paused: {p.kind}"}); pause = p; resume += [nid] if p.kind == "approval" else nxt(nid); continue
            except Exception as e:
                trace.append({"node": nid, "type": typ, "error": str(e)[:200]})
                if run is None and not dry: _save_run(db, wf, r, event, "failed", trace)
                elif run: run.status = "failed"; run.trace = trace; run.finished_at = now()
                return trace
        else:
            trace.append({"node": nid, "type": typ})
        frontier += nxt(nid, handle)
    if dry: return trace
    status = "done" if not pause else ("awaiting_approval" if pause.kind == "approval" else "waiting")
    if run is None: run = _save_run(db, wf, r, event, status, trace)
    run.trace = trace; run.status = status; run.resume_nodes = resume
    run.resume_at = now() + timedelta(minutes=pause.minutes) if pause and pause.kind == "wait" else None
    run.approval_id = pause.approval_id if pause and pause.kind == "approval" else None
    run.finished_at = now() if status == "done" else None
    return trace

def _save_run(db, wf, r, event, status, trace):
    run = WorkflowRun(tenant_id=wf.tenant_id, workflow_id=wf.id, version=wf.version or 1, record_id=r.id if r else None, event=event, status=status, trace=trace, created_at=now())
    db.add(run); wf.runs = (wf.runs or 0) + 1; db.flush(); return run

def targets(wf): return wf.modules or [wf.module]
def applies(wf, module): t = targets(wf); return "*" in t or module in t

def _fires(wf, r, event, changes):
    trig = wf.trigger; c = wf.trigger_cfg or {}
    if event == "created": ok = trig in ("created", "field_condition")
    elif event == "updated":
        ok = trig == "updated" or (trig == "state_changed" and "state" in (changes or {}) and (not c.get("to_state") or r.state == c["to_state"])) \
             or (trig == "field_changed" and c.get("field") and (c["field"] in (changes or {}) or f"data.{c['field']}" in (changes or {}))) \
             or (trig == "field_condition" and bool(changes))
    else: ok = trig == event
    if ok and c.get("field") and trig in ("field_condition", "field_changed", "sla_warning", "sla_breach", "created", "updated") and c.get("op") and c.get("op") != "changed":
        ok = cond(r, c, changes)
    return ok

@bus.subscribe
def on_event(db, r, event, actor, changes=None):
    if getattr(r, "_wf_running", False) or getattr(db, "_wf_depth", 0) > 2: return
    r._wf_running = True; db._wf_depth = getattr(db, "_wf_depth", 0) + 1
    try:
        for wf in db.scalars(select(WorkflowDef).where(WorkflowDef.tenant_id == r.tenant_id, WorkflowDef.active == True)).all():
            if applies(wf, r.module) and _fires(wf, r, event, changes): execute(db, wf, r, actor, changes=changes, event=event)
    finally:
        r._wf_running = False; db._wf_depth -= 1

def tick(db, tenant_id=None):
    """Resume waits/approvals and run scheduled workflows. Called by the scheduler every minute and via POST /api/workflows/tick."""
    resumed = scheduled = 0; t = now()
    q = select(WorkflowRun).where(WorkflowRun.status.in_(["waiting", "awaiting_approval"]))
    if tenant_id: q = q.where(WorkflowRun.tenant_id == tenant_id)
    for run in db.scalars(q).all():
        wf = db.get(WorkflowDef, run.workflow_id); r = db.get(Record, run.record_id) if run.record_id else None
        if not wf or not r: run.status = "failed"; continue
        if run.status == "waiting" and run.resume_at and run.resume_at <= t:
            run.status = "running"; execute(db, wf, r, None, start=run.resume_nodes, run=run); resumed += 1
        elif run.status == "awaiting_approval":
            ap = db.get(Approval, run.approval_id) if run.approval_id else None
            if ap and ap.state in ("approved", "rejected"):
                node = run.resume_nodes[0] if run.resume_nodes else None
                handle = "true" if ap.state == "approved" else "false"
                nxt = [e["target"] for e in wf.edges if e["source"] == node and (e.get("sourceHandle") or "true") == handle]
                run.trace = [*run.trace, {"node": node, "type": "approval", "result": ap.state == "approved"}]
                run.status = "running"; execute(db, wf, r, None, start=nxt, run=run); resumed += 1
    q = select(WorkflowDef).where(WorkflowDef.active == True, WorkflowDef.trigger == "schedule")
    if tenant_id: q = q.where(WorkflowDef.tenant_id == tenant_id)
    for wf in db.scalars(q).all():
        every = float((wf.trigger_cfg or {}).get("every_minutes", 60))
        if wf.last_scheduled_at and wf.last_scheduled_at + timedelta(minutes=every) > t: continue
        wf.last_scheduled_at = t; c = wf.trigger_cfg or {}
        rq = select(Record).where(Record.tenant_id == wf.tenant_id, Record.state.not_in(CLOSED))
        if "*" not in targets(wf): rq = rq.where(Record.module.in_(targets(wf)))
        for r in db.scalars(rq.limit(200)).all():
            if c.get("field") and not cond(r, c): continue
            execute(db, wf, r, None, event="schedule"); scheduled += 1
    db.commit()
    return {"resumed": resumed, "scheduled": scheduled}

router = APIRouter(prefix="/api/workflows", tags=["workflows"])
class WfIn(BaseModel):
    name: str; module: str | None = None; modules: list[str] = []; trigger: str = "created"; trigger_cfg: dict = {}
    nodes: list = []; edges: list = []; active: bool = True; description: str = ""

def _o(w): return {"id": w.id, "name": w.name, "module": w.module, "modules": targets(w), "trigger": w.trigger, "trigger_cfg": w.trigger_cfg or {}, "nodes": w.nodes,
                   "edges": w.edges, "active": w.active, "runs": w.runs, "version": w.version or 1, "description": w.description or ""}

def _validate(b):
    mods = b.modules or ([b.module] if b.module else [])
    if not mods or any(m != "*" and m not in registry.MODULES for m in mods): raise HTTPException(400, "Pick at least one valid module (or all modules).")
    b.modules = mods; b.module = mods[0] if mods[0] != "*" else "*"
    if b.trigger not in TRIGGERS: raise HTTPException(400, f"Unknown trigger. Choose one of: {', '.join(TRIGGERS)}")
    if b.trigger in ("field_changed", "field_condition") and not (b.trigger_cfg or {}).get("field"): raise HTTPException(400, "This trigger needs a field.")
    ids = {n.get("id") for n in b.nodes}
    if sum(1 for n in b.nodes if n.get("type") == "trigger") != 1: raise HTTPException(400, "Exactly one trigger node required")
    if any(e.get("source") not in ids or e.get("target") not in ids for e in b.edges): raise HTTPException(400, "Edge references unknown node")
    for n in b.nodes:
        d = n.get("data", {})
        if n.get("type") == "action" and d.get("action") not in ACTIONS: raise HTTPException(400, f"Unknown action: {d.get('action')}")
        if n.get("type") == "condition" and d.get("op", "eq") not in OPS: raise HTTPException(400, f"Unknown operator: {d.get('op')}")
        if d.get("action") == "create_record" and d.get("module") not in registry.MODULES: raise HTTPException(400, "Create record needs a target module.")
        if d.get("action") == "webhook" and urlparse(d.get("url", "")).scheme not in ("http", "https"): raise HTTPException(400, "Webhook needs an http(s) URL.")

def _snap(db, w, uid):
    db.add(WorkflowVersion(workflow_id=w.id, version=w.version, snapshot={k: v for k, v in _o(w).items() if k not in ("id", "runs", "version")}, created_by=uid))

@router.get("/meta")
def wf_meta(_=Depends(staff)): return {"triggers": TRIGGERS, "actions": ACTIONS, "ops": OPS}

@router.get("")
def list_wf(db: Session = Depends(get_db), u=Depends(staff)):
    return [_o(w) for w in db.scalars(scoped(select(WorkflowDef), WorkflowDef, u).order_by(WorkflowDef.id))]

@router.post("", status_code=201)
def create_wf(b: WfIn, db: Session = Depends(get_db), u=Depends(admin_only)):
    _validate(b); w = WorkflowDef(tenant_id=u.tenant_id, version=1, **b.model_dump()); db.add(w); db.flush(); _snap(db, w, u.id)
    audit.log(db, u.id, "create", "workflow", w.id); db.commit(); return _o(w)

@router.put("/{wid}")
def update_wf(wid: int, b: WfIn, db: Session = Depends(get_db), u=Depends(admin_only)):
    _validate(b); w = get_or_404(db, WorkflowDef, wid, u)
    for k, v in b.model_dump().items(): setattr(w, k, v)
    w.version = (w.version or 1) + 1; _snap(db, w, u.id)
    audit.log(db, u.id, "update", "workflow", w.id, {"version": w.version}); db.commit(); return _o(w)

@router.post("/{wid}/toggle")
def toggle_wf(wid: int, db: Session = Depends(get_db), u=Depends(admin_only)):
    w = get_or_404(db, WorkflowDef, wid, u); w.active = not w.active
    audit.log(db, u.id, "enable" if w.active else "disable", "workflow", w.id); db.commit(); return _o(w)

@router.get("/{wid}/versions")
def versions(wid: int, db: Session = Depends(get_db), u=Depends(staff)):
    get_or_404(db, WorkflowDef, wid, u)
    return [{"version": v.version, "created_at": v.created_at, "created_by": v.created_by, "snapshot": v.snapshot} for v in db.scalars(select(WorkflowVersion).where(WorkflowVersion.workflow_id == wid).order_by(WorkflowVersion.version.desc()))]

@router.post("/{wid}/restore/{version}")
def restore(wid: int, version: int, db: Session = Depends(get_db), u=Depends(admin_only)):
    w = get_or_404(db, WorkflowDef, wid, u)
    v = db.scalar(select(WorkflowVersion).where(WorkflowVersion.workflow_id == wid, WorkflowVersion.version == version))
    if not v: raise HTTPException(404, "Version not found")
    for k, val in v.snapshot.items():
        if hasattr(w, k): setattr(w, k, val)
    w.version += 1; _snap(db, w, u.id); audit.log(db, u.id, "restore", "workflow", w.id, {"from": version}); db.commit(); return _o(w)

@router.get("/{wid}/runs")
def runs(wid: int, limit: int = 50, db: Session = Depends(get_db), u=Depends(staff)):
    get_or_404(db, WorkflowDef, wid, u)
    rows = db.scalars(select(WorkflowRun).where(WorkflowRun.workflow_id == wid).order_by(WorkflowRun.id.desc()).limit(limit)).all()
    nums = {r.id: r.number for r in db.scalars(select(Record).where(Record.id.in_({x.record_id for x in rows if x.record_id})))}
    return [{"id": x.id, "version": x.version, "record_id": x.record_id, "record": nums.get(x.record_id), "event": x.event, "status": x.status, "trace": x.trace,
             "resume_at": x.resume_at, "created_at": x.created_at, "finished_at": x.finished_at} for x in rows]

@router.post("/tick")
def tick_now(db: Session = Depends(get_db), u=Depends(admin_only)): return tick(db, u.tenant_id)

@router.delete("/{wid}")
def delete_wf(wid: int, db: Session = Depends(get_db), u=Depends(admin_only)):
    w = get_or_404(db, WorkflowDef, wid, u)
    for m in (WorkflowRun, WorkflowVersion):
        for x in db.scalars(select(m).where(m.workflow_id == wid)): db.delete(x)
    db.delete(w); audit.log(db, u.id, "delete", "workflow", wid); db.commit(); return {"ok": True}

@router.post("/{wid}/test")
def test_wf(wid: int, record_id: int, db: Session = Depends(get_db), u=Depends(staff)):
    w = get_or_404(db, WorkflowDef, wid, u); r = get_or_404(db, Record, record_id, u)
    return {"trace": execute(db, w, r, u, dry=True)}
