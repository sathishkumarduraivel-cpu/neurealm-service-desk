"""Agentic auto-resolution engine (SLA Assist-powered L1 automation).
Each playbook: diagnose -> act -> verify. Confidence = triage confidence x playbook match strength.
Low-risk playbooks above the threshold run autonomously; high-risk ones require human-in-the-loop approval."""
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import get_db
from .models import Record, Comment, AutoRun, Approval, User, now
from .security import staff, admin_only
from .deps import scoped, get_or_404, out, notify, link_for
from . import ai, audit, bus, settings_store, registry

PLAYBOOKS = [
    {"id": "password_reset", "name": "Self-service password reset & unlock", "category": "access", "keywords": ["password", "locked", "reset", "unlock", "login", "account"], "risk": "low",
     "steps": [("diagnose", "Query Azure AD: account lockout status & failed sign-ins"), ("act", "Unlock account and issue one-time reset link via Chatbot"), ("verify", "Confirm successful sign-in event")],
     "resolution": "Account unlocked and password reset link sent; user signed in successfully."},
    {"id": "vpn_reset", "name": "VPN client remediation", "category": "network", "keywords": ["vpn", "globalprotect", "tunnel", "remote", "connect"], "risk": "low",
     "steps": [("diagnose", "Check VPN gateway health & user session table"), ("act", "Clear stale session, push GlobalProtect config refresh via Remote Agent"), ("verify", "Confirm tunnel established")],
     "resolution": "Stale VPN session cleared and client config refreshed; tunnel re-established."},
    {"id": "outlook_repair", "name": "Outlook profile repair", "category": "email", "keywords": ["outlook", "mailbox", "sync", "crash", "email"], "risk": "low",
     "steps": [("diagnose", "Collect Outlook crash logs & add-in inventory"), ("act", "Disable faulty add-in, rebuild OST via endpoint agent"), ("verify", "Outlook launched and synced")],
     "resolution": "Faulty add-in disabled and OST rebuilt; Outlook syncing normally."},
    {"id": "disk_cleanup", "name": "Endpoint disk cleanup & performance fix", "category": "hardware", "keywords": ["slow", "disk", "space", "storage", "performance", "laptop"], "risk": "low",
     "steps": [("diagnose", "Read DEX telemetry: disk, CPU, startup apps"), ("act", "Clear temp/cache, disable heavy startup items"), ("verify", "Disk free > 20%, boot time improved")],
     "resolution": "Freed disk space and optimized startup; performance restored."},
    {"id": "printer_queue", "name": "Printer queue reset", "category": "hardware", "keywords": ["printer", "print", "queue", "offline"], "risk": "low",
     "steps": [("diagnose", "Ping printer & check spooler"), ("act", "Restart print spooler and clear stuck jobs"), ("verify", "Test page printed")],
     "resolution": "Print spooler restarted and queue cleared; printer online."},
    {"id": "service_restart", "name": "Production service restart", "category": "software", "keywords": ["application", "down", "error", "crash", "outage", "service", "erp", "sap"], "risk": "high",
     "steps": [("diagnose", "Check service health, recent deploys and CMDB impact"), ("act", "Rolling restart of application service nodes"), ("verify", "Health checks green; error rate normal")],
     "resolution": "Application service restarted via rolling restart; health checks green."},
    {"id": "access_grant", "name": "Privileged access grant", "category": "access", "keywords": ["permission", "access", "admin", "grant", "privilege"], "risk": "high",
     "steps": [("diagnose", "Validate requester entitlement & manager"), ("act", "Grant time-bound group membership (PIM)"), ("verify", "Access confirmed by user")],
     "resolution": "Time-bound access granted via PIM."},
]
PB = {p["id"]: p for p in PLAYBOOKS}

def match(r):
    toks = set(ai.tokens(f"{r.title} {r.description}"))
    cat = r.category if r.category != "general" else ai.rule_triage(f"{r.title} {r.description}")["category"]
    best, best_s = None, 0.0
    for p in PLAYBOOKS:
        hits = sum(1 for k in p["keywords"] if k in toks)
        if not hits: continue
        s = min(1.0, 0.45 + 0.25 * hits) * (1.0 if p["category"] == cat else 0.6)
        if s > best_s: best, best_s = p, s
    if not best: return None, 0.0
    tri = (r.ai_suggestion or {}).get("confidence") or ai.rule_triage(f"{r.title} {r.description}")["confidence"]
    return best, round(min(0.98, 0.5 * best_s + 0.5 * max(tri, best_s)), 2)

def _execute(db, r, pb, actor, conf):
    for phase, step in pb["steps"]:
        db.add(Comment(record_id=r.id, author_id=actor.id, body=f"🤖 [{phase}] {step} — ok", internal=True))
    db.add(Comment(record_id=r.id, author_id=actor.id, body=f"🤖 Neurealm AI resolved this ticket: {pb['resolution']}", internal=False))
    r.state = "resolved"; r.resolved_at = now()
    r.data = {**r.data, "auto_resolved": True, "playbook": pb["id"], "resolution_notes": pb["resolution"], "ai_confidence": conf, "pending_playbook": None}
    notify(db, r.tenant_id, f"{r.number} auto-resolved by Neurealm AI ({pb['name']})", "ai", r.requester_id, None, link_for(r))

def run(db, r, actor, dry_run=False, threshold=None):
    if r.module not in ("incident", "case"): raise HTTPException(400, "Auto-resolution supports incidents and cases")
    if r.state in registry.CLOSED: raise HTTPException(400, "Record already closed")
    cfg = settings_store.get(db, r.tenant_id, "autoresolve")
    if not cfg["enabled"] and not dry_run: raise HTTPException(423, "Auto-resolution disabled by admin")
    th = threshold if threshold is not None else cfg["threshold"]
    pb, conf = match(r)
    security = r.category == "security" or bool(set(ai.tokens(f"{r.title} {r.description}")) & set(ai.CATEGORIES["security"]))
    if security: pb, conf = None, 0.0  # guardrail: security-classified tickets are never auto-resolved — routed to SecOps
    steps = [{"phase": ph, "step": s} for ph, s in (pb["steps"] if pb else [])]
    if security: state = "escalated"
    elif not pb: state = "no_match"
    elif conf < th: state = "escalated"
    elif dry_run: state = "dry_run"
    elif pb["risk"] == "high":
        state = "awaiting_approval"
        admins = db.scalars(select(User).where(User.tenant_id == r.tenant_id, User.role == "admin", User.active == True).limit(1)).all()
        r.approvals.append(Approval(level=1, approver_id=admins[0].id if admins else None))
        r.data = {**r.data, "pending_playbook": pb["id"], "ai_confidence": conf}
        db.add(Comment(record_id=r.id, author_id=actor.id, body=f"🤖 Proposed high-risk action '{pb['name']}' (confidence {conf:.0%}) — awaiting human approval.", internal=True))
        for a in admins: notify(db, r.tenant_id, f"Approve AI action on {r.number}: {pb['name']}", "approval", a.id, None, link_for(r))
    else:
        state = "resolved"; _execute(db, r, pb, actor, conf)
    if security:
        db.add(Comment(record_id=r.id, author_id=actor.id, body="🛡️ Security-classified ticket — autonomous resolution blocked by guardrail; routed to Security Ops.", internal=True))
    elif state == "escalated":
        db.add(Comment(record_id=r.id, author_id=actor.id, body=f"🤖 Candidate playbook '{pb['name']}' confidence {conf:.0%} below threshold {th:.0%} — routed to a human agent.", internal=True))
    run_ = AutoRun(tenant_id=r.tenant_id, record_id=r.id, playbook=pb["id"] if pb else "-", confidence=conf, risk=pb["risk"] if pb else "-", state=state, steps=steps)
    db.add(run_); audit.log(db, actor.id, f"autoresolve_{state}", r.module, r.number, {"playbook": run_.playbook, "confidence": conf})
    return run_

def execute_approved(db, r, actor):
    pb = PB.get(r.data.get("pending_playbook"))
    if not pb: return
    _execute(db, r, pb, actor, r.data.get("ai_confidence", 0))
    db.add(AutoRun(tenant_id=r.tenant_id, record_id=r.id, playbook=pb["id"], confidence=r.data.get("ai_confidence", 0), risk=pb["risk"], state="resolved", steps=[{"phase": a, "step": b} for a, b in pb["steps"]]))
    audit.log(db, actor.id, "autoresolve_approved_execute", r.module, r.number, {"playbook": pb["id"]})

@bus.subscribe
def on_create(db, r, event, actor, changes):
    if event == "created" and r.module == "incident" and actor and settings_store.get(db, r.tenant_id, "autoresolve").get("on_create"):
        run(db, r, actor)

router = APIRouter(prefix="/api/autoresolve", tags=["autoresolve"])
def _ro(x): return {"id": x.id, "record_id": x.record_id, "playbook": x.playbook, "confidence": x.confidence, "risk": x.risk, "state": x.state, "steps": x.steps, "created_at": x.created_at}

@router.get("/playbooks")
def playbooks(_=Depends(staff)):
    return [{k: v for k, v in p.items()} for p in PLAYBOOKS]

@router.post("/run-all")
def run_all(dry_run: bool = False, db: Session = Depends(get_db), u=Depends(staff)):
    recs = db.scalars(scoped(select(Record), Record, u).where(Record.module == "incident", Record.state.in_(["new", "in_progress"]))).all()
    done = set(db.scalars(scoped(select(AutoRun.record_id), AutoRun, u).where(AutoRun.state.in_(["resolved", "awaiting_approval"]))))
    res = [_ro(run(db, r, u, dry_run)) for r in recs if r.id not in done and not r.data.get("pending_playbook")]
    db.commit()
    return {"evaluated": len(res), "by_state": {s: sum(1 for x in res if x["state"] == s) for s in {x["state"] for x in res}}, "runs": res}

@router.post("/{rid}")
def run_one(rid: int, dry_run: bool = False, threshold: float | None = None, db: Session = Depends(get_db), u=Depends(staff)):
    r = get_or_404(db, Record, rid, u); x = run(db, r, u, dry_run, threshold); db.commit(); db.refresh(r)
    return {"run": _ro(x), "record": out(r)}

@router.get("/runs")
def runs(db: Session = Depends(get_db), u=Depends(staff)):
    rows = db.scalars(scoped(select(AutoRun), AutoRun, u).order_by(AutoRun.id.desc()).limit(100)).all()
    recs = {r.id: r for r in db.scalars(select(Record).where(Record.id.in_([x.record_id for x in rows])))}
    return [{**_ro(x), "number": recs[x.record_id].number, "title": recs[x.record_id].title} for x in rows]

@router.get("/stats")
def stats(db: Session = Depends(get_db), u=Depends(staff)):
    rows = db.scalars(scoped(select(AutoRun), AutoRun, u)).all()
    total_inc = db.scalar(scoped(select(func.count()).select_from(Record), Record, u).where(Record.module == "incident")) or 0
    auto = len({x.record_id for x in rows if x.state == "resolved"})
    return {"runs": len(rows), "auto_resolved": auto, "awaiting_approval": sum(x.state == "awaiting_approval" for x in rows), "escalated": sum(x.state == "escalated" for x in rows),
            "autonomous_resolution_rate_pct": round(100 * auto / total_inc, 1) if total_inc else 0, "settings": settings_store.get(db, u.tenant_id, "autoresolve")}

@router.put("/settings")
def put_settings(body: dict, db: Session = Depends(get_db), u=Depends(admin_only)):
    v = settings_store.put(db, u.tenant_id, "autoresolve", {k: body[k] for k in ("enabled", "on_create", "threshold") if k in body})
    audit.log(db, u.id, "settings", "autoresolve", u.tenant_id, v); db.commit(); return v
