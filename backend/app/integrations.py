"""Integration connector framework: adapters translate Neurealm Service Desk events <-> external systems.
Outbound: bus events -> adapter.format -> HTTP POST to config.url (or 'simulated' when no URL, e.g. air-gapped/demo).
Inbound:  POST /api/integrations/{kind}/webhook  (auth: X-Neurealm Service Desk-Signature = HMAC-SHA256(secret, body) or ?token=secret)."""
import hmac, hashlib, json, secrets, logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import Connector, ConnectorLog, Record, User, now
from .security import staff, admin_only
from .schemas import RecordCreate
from .deps import scoped, get_or_404, out, next_number
from . import bus, audit, registry, sla

def _link(r): return f"/m/{r.module}/{r.id}"
def _base(r): return {"number": r.number, "module": r.module, "title": r.title, "state": r.state, "priority": r.priority, "category": r.category, "link": _link(r)}

class Adapter:
    kind = "webhook"; label = "Generic webhook"; direction = "both"; description = ""
    def format(self, event, r): return {"event": event, "record": _base(r)}
    def inbound(self, p): return ("incident", RecordCreate(title=p.get("title") or "Webhook event", description=p.get("description", ""), data={"source": self.kind}))

class Teams(Adapter):
    kind, label, direction, description = "teams", "Microsoft Teams", "both", "Adaptive-card notifications; create tickets from Teams messages"
    def format(self, event, r): return {"@type": "MessageCard", "summary": r.title, "themeColor": "2b44e0", "title": f"{r.number} {event}: {r.title}",
                                         "sections": [{"facts": [{"name": "Priority", "value": r.priority}, {"name": "State", "value": r.state}]}]}
    def inbound(self, p): return ("incident", RecordCreate(title=p.get("text", "")[:200] or "Teams request", description=p.get("text", ""), data={"channel": "teams", "source_user": p.get("from", "")}))

class Slack(Adapter):
    kind, label, direction, description = "slack", "Slack", "both", "Block-kit notifications; /servicedesk slash command creates tickets"
    def format(self, event, r): return {"text": f"*{r.number}* {event}: {r.title}", "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": f"*{r.number}* · {r.priority} · {r.state}\n{r.title}"}}]}
    def inbound(self, p): return ("incident", RecordCreate(title=(p.get("text") or "Slack request")[:200], description=p.get("text", ""), data={"channel": "slack", "source_user": p.get("user_name", "")}))

class Chatbot(Adapter):
    kind, label, direction, description = "chatbot", "Chatbot (omnichannel AI agent)", "both", "Voice/chat/WhatsApp conversations escalate into incidents or cases with transcript"
    def format(self, event, r): return {"type": "ticket_update", "ticket": _base(r), "notify_user": True}
    def inbound(self, p):
        module = "case" if p.get("customer") else "incident"
        return (module, RecordCreate(title=p.get("summary") or "Conversation escalation", description=p.get("transcript", ""),
                                     data={"channel": p.get("channel", "chat"), "language": p.get("language", "en"), "conversation_id": p.get("conversation_id"), **({"account": p["account"]} if p.get("account") else {})}))

class SlaAssist(Adapter):
    kind, label, direction, description = "sla_assist", "SLA Assist (SLA & assignment)", "both", "Receives SLA risk events; pushes assignment recommendations back"
    def format(self, event, r): return {"event": event, "record": _base(r), "sla_due_at": r.sla_due_at.isoformat() if r.sla_due_at else None, "group_id": r.assignment_group_id}
    def inbound(self, p): return ("assign", p)

class PMO(Adapter):
    kind, label, direction, description = "pmo", "PMO (AI PMO for Jira)", "out", "Syncs projects & demands to PMO portfolios"
    def format(self, event, r): return {"event": event, "project": {**_base(r), "percent_complete": r.data.get("percent_complete"), "health": r.data.get("health")}}

class QualityAudit(Adapter):
    kind, label, direction, description = "quality_audit", "Quality audit (quality auditing)", "both", "Sends resolved tickets for audit; receives quality scores"
    def format(self, event, r): return {"audit_request": _base(r), "description": r.description}
    def inbound(self, p): return ("quality", p)

class WorkflowHub(Adapter):
    kind, label, direction, description = "workflow_hub", "Workflow connector (no-code workflows)", "both", "Triggers Workflow connector flows; Workflow connector can create any Neurealm Service Desk record"
    def inbound(self, p):
        m = p.get("module", "incident")
        if m not in registry.MODULES: raise HTTPException(400, "Unknown module")
        return (m, RecordCreate(title=p.get("title", "Workflow connector record"), description=p.get("description", ""), data=p.get("data", {})))

class Jira(Adapter):
    kind, label, direction, description = "jira", "Jira", "both", "Escalate incidents to Jira bugs; Jira webhooks create/update linked records"
    def format(self, event, r): return {"fields": {"project": {"key": "OPS"}, "summary": f"[{r.number}] {r.title}", "description": r.description, "issuetype": {"name": "Bug"},
                                                    "priority": {"name": {"P1": "Highest", "P2": "High", "P3": "Medium", "P4": "Low"}[r.priority]}}}
    def inbound(self, p):
        i = p.get("issue", {}); f = i.get("fields", {})
        return ("incident", RecordCreate(title=f.get("summary", "Jira issue"), description=f.get("description") or "", data={"jira_key": i.get("key"), "source": "jira"}))

class ServiceNow(Adapter):
    kind, label, direction, description = "servicenow", "ServiceNow (migration)", "in", "Bulk-import ServiceNow tables (incident, problem, change_request, sc_req_item, kb_knowledge)"

ADAPTERS = {a.kind: a for a in [Adapter(), Teams(), Slack(), Chatbot(), SlaAssist(), PMO(), QualityAudit(), WorkflowHub(), Jira(), ServiceNow()]}

def send(db, tenant_id, kind, event, r):
    for c in db.scalars(select(Connector).where(Connector.tenant_id == tenant_id, Connector.kind == kind, Connector.enabled == True)):
        _deliver(db, c, event, r)

def _deliver(db, c, event, r):
    payload = ADAPTERS[c.kind].format(event, r); url = c.config.get("url"); status = "simulated"
    if url:
        try:
            body = json.dumps(payload, default=str).encode()
            sig = hmac.new(c.secret.encode(), body, hashlib.sha256).hexdigest()
            resp = httpx.post(url, content=body, headers={"Content-Type": "application/json", "X-Neurealm Service Desk-Signature": sig}, timeout=5); status = f"http_{resp.status_code}"
        except Exception as e:
            status = "error"; payload = {**payload, "_error": str(e)[:200]}
    db.add(ConnectorLog(tenant_id=c.tenant_id, connector_id=c.id, direction="out", status=status, payload=payload))

@bus.subscribe
def on_event(db, r, event, actor, changes):
    for c in db.scalars(select(Connector).where(Connector.tenant_id == r.tenant_id, Connector.enabled == True)):
        evs, mods = c.config.get("events", []), c.config.get("modules", [])
        if ADAPTERS.get(c.kind) and ADAPTERS[c.kind].direction != "in" and event in evs and (not mods or r.module in mods):
            if c.config.get("min_priority") and r.priority > c.config["min_priority"]: continue
            _deliver(db, c, event, r)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])
class ConnIn(BaseModel):
    kind: str; name: str; config: dict = {}; enabled: bool = True

def _co(c): return {"id": c.id, "kind": c.kind, "name": c.name, "config": c.config, "enabled": c.enabled, "secret_hint": c.secret[:4] + "…" if c.secret else ""}

@router.get("/adapters")
def adapters(_=Depends(staff)):
    return [{"kind": a.kind, "label": a.label, "direction": a.direction, "description": a.description} for a in ADAPTERS.values()]

@router.get("/connectors")
def connectors(db: Session = Depends(get_db), u=Depends(staff)):
    return [_co(c) for c in db.scalars(scoped(select(Connector), Connector, u).order_by(Connector.id))]

@router.post("/connectors", status_code=201)
def create_connector(b: ConnIn, db: Session = Depends(get_db), u=Depends(admin_only)):
    if b.kind not in ADAPTERS: raise HTTPException(400, "Unknown adapter")
    c = Connector(tenant_id=u.tenant_id, kind=b.kind, name=b.name, config=b.config, enabled=b.enabled, secret=secrets.token_hex(16)); db.add(c); db.flush()
    audit.log(db, u.id, "create", "connector", c.id, {"kind": b.kind}); db.commit()
    return {**_co(c), "secret": c.secret}

@router.patch("/connectors/{cid}")
def update_connector(cid: int, b: dict, db: Session = Depends(get_db), u=Depends(admin_only)):
    c = get_or_404(db, Connector, cid, u)
    for k in ("name", "config", "enabled"):
        if k in b: setattr(c, k, b[k])
    audit.log(db, u.id, "update", "connector", c.id); db.commit(); return _co(c)

@router.post("/connectors/{cid}/test")
def test_connector(cid: int, db: Session = Depends(get_db), u=Depends(staff)):
    c = get_or_404(db, Connector, cid, u)
    r = db.scalar(scoped(select(Record), Record, u).where(Record.module == "incident").limit(1))
    if not r: raise HTTPException(400, "No record to test with")
    _deliver(db, c, "test", r); db.commit()
    return logs(db, u)[0]

@router.get("/logs")
def logs(db: Session = Depends(get_db), u=Depends(staff)):
    names = {c.id: c.name for c in db.scalars(scoped(select(Connector), Connector, u))}
    return [{"id": l.id, "connector": names.get(l.connector_id, "-"), "direction": l.direction, "status": l.status, "payload": l.payload, "created_at": l.created_at}
            for l in db.scalars(scoped(select(ConnectorLog), ConnectorLog, u).order_by(ConnectorLog.id.desc()).limit(100))]

@router.post("/{kind}/webhook")
async def webhook(kind: str, request: Request, token: str | None = None, db: Session = Depends(get_db)):
    if kind not in ADAPTERS: raise HTTPException(404)
    raw = await request.body(); sig = request.headers.get("X-Neurealm Service Desk-Signature")
    conn = None
    for c in db.scalars(select(Connector).where(Connector.kind == kind, Connector.enabled == True)):
        if (token and hmac.compare_digest(token, c.secret)) or (sig and hmac.compare_digest(sig, hmac.new(c.secret.encode(), raw, hashlib.sha256).hexdigest())): conn = c; break
    if not conn: raise HTTPException(401, "Invalid connector signature/token")
    p = json.loads(raw or b"{}")
    actor = db.scalar(select(User).where(User.tenant_id == conn.tenant_id, User.role == "admin").order_by(User.id))
    db.add(ConnectorLog(tenant_id=conn.tenant_id, connector_id=conn.id, direction="in", status="received", payload=p))
    module, body = ADAPTERS[kind].inbound(p)
    if module == "assign":
        r = db.scalar(select(Record).where(Record.tenant_id == conn.tenant_id, Record.number == p.get("number")))
        if not r: raise HTTPException(404, "Record not found")
        u = db.scalar(select(User).where(User.tenant_id == conn.tenant_id, User.email == p.get("assignee_email")))
        if u: r.assignee_id = u.id
        r.data = {**r.data, "sla_assist_recommendation": p}; audit.log(db, actor.id, "sla_assist_assign", r.module, r.number, p); db.commit(); return {"updated": r.number}
    if module == "quality":
        r = db.scalar(select(Record).where(Record.tenant_id == conn.tenant_id, Record.number == p.get("number")))
        if not r: raise HTTPException(404, "Record not found")
        r.data = {**r.data, "quality_audit_score": p.get("score"), "quality_audit_findings": p.get("findings", [])}; db.commit(); return {"updated": r.number}
    from .main import create_record_core
    r = create_record_core(db, actor, module, body)
    r.data = {**r.data, "source": kind}; audit.log(db, actor.id, "inbound", kind, r.number); db.commit()
    return {"created": r.number, "id": r.id, "module": r.module}

# ---------------- ServiceNow migration ----------------
SN_TABLES = {"incident": "incident", "problem": "problem", "change_request": "change", "sc_req_item": "request"}
SN_STATE = {"incident": {"1": "new", "2": "in_progress", "3": "on_hold", "6": "resolved", "7": "closed", "8": "cancelled"},
            "problem": {"101": "new", "102": "assessment", "103": "root_cause_analysis", "104": "fix_in_progress", "106": "resolved", "107": "closed"},
            "change": {"-5": "new", "-4": "assess", "-3": "authorize", "-2": "scheduled", "-1": "implement", "0": "review", "3": "closed", "4": "cancelled"},
            "request": {"1": "pending_approval", "2": "in_progress", "3": "closed", "4": "cancelled"}}
SN_PRIO = {"1": "P1", "2": "P2", "3": "P3", "4": "P4", "5": "P4"}

class SNImport(BaseModel):
    table: str = "incident"; records: list[dict]; dry_run: bool = False

@router.post("/servicenow/import")
def sn_import(b: SNImport, db: Session = Depends(get_db), u=Depends(admin_only)):
    from datetime import datetime
    from .models import Group, KBArticle
    if b.table == "kb_knowledge":
        n = 0; base = db.query(KBArticle).count()
        for x in b.records:
            if not b.dry_run:
                db.add(KBArticle(tenant_id=u.tenant_id, number=f"KB{9000000 + base + n}", title=x.get("short_description", "Imported"), body=x.get("text", ""), category=x.get("category", "general"), tags="servicenow"))
            n += 1
        db.commit(); return {"table": b.table, "imported": n, "skipped": 0, "errors": []}
    module = SN_TABLES.get(b.table)
    if not module: raise HTTPException(400, f"Unsupported table {b.table}")
    groups = {g.name.lower(): g.id for g in db.scalars(scoped(select(Group), Group, u))}
    have = {r.data.get("sn_number") for r in db.scalars(scoped(select(Record), Record, u).where(Record.module == module)) if r.data.get("sn_number")}
    imported, skipped, errors, preview = 0, 0, [], []
    for i, x in enumerate(b.records):
        sn = x.get("number")
        if not sn or not x.get("short_description"): errors.append({"row": i, "error": "number and short_description are required"}); continue
        if sn in have: skipped += 1; continue
        state = SN_STATE[module].get(str(x.get("state", "")), registry.initial(module))
        try: created = datetime.fromisoformat(str(x.get("sys_created_on", "")).replace(" ", "T")[:19]) if x.get("sys_created_on") else now()
        except ValueError: created = now()
        r = Record(tenant_id=u.tenant_id, module=module, number=next_number(db, module), title=x["short_description"], description=x.get("description", ""), state=state,
                   priority=SN_PRIO.get(str(x.get("priority", "3")), "P3"), impact=int(x.get("impact", 3) or 3), urgency=int(x.get("urgency", 3) or 3), category=x.get("category") or "general",
                   assignment_group_id=groups.get(str(x.get("assignment_group", "")).lower()), requester_id=u.id, created_at=created, ai_suggestion={},
                   data={"sn_number": sn, "migrated_from": "servicenow", "resolution_notes": x.get("close_notes", "")})
        if state in registry.CLOSED: r.resolved_at = created
        if registry.MODULES[module].get("sla"): sla.apply_sla(db, r)
        preview.append({"sn_number": sn, "state": state, "priority": r.priority})
        if not b.dry_run: db.add(r); db.flush(); have.add(sn)
        imported += 1
    if not b.dry_run: audit.log(db, u.id, "servicenow_import", module, b.table, {"imported": imported, "skipped": skipped}); db.commit()
    else: db.rollback()
    return {"table": b.table, "module": module, "imported": imported, "skipped": skipped, "errors": errors, "dry_run": b.dry_run, "preview": preview[:10]}
