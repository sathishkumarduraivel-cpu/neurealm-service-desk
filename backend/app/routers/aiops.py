"""Phase 7 (AI): Neurealm AI provider settings (OpenAI-compatible, off by default), assistant, ticket AI,
writing help and an AI report builder. Every feature works without a provider using rules."""
import json, logging, re
from collections import Counter
from datetime import timedelta
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Record, Comment, CatalogItem, now
from ..security import current_user, staff, admin_only
from ..deps import get_record
from .. import ai, audit, config, registry, settings_store

router = APIRouter(prefix="/api/ai", tags=["ai"])
FEATURES = ["assistant", "ticket", "writing", "reports", "triage"]

def provider(db, tid):
    p = settings_store.get(db, tid, "ai.provider").get("v") or {}
    key = p.get("api_key") or (config.LLM_API_KEY if p.get("use_env_key", True) else None)
    return {"enabled": bool(p.get("enabled")), "base_url": p.get("base_url") or config.LLM_BASE_URL, "model": p.get("model") or config.LLM_MODEL,
            "key": key, "features": {f: p.get("features", {}).get(f, True) for f in FEATURES}}

def llm(db, tid, feature, messages, max_tokens=500, client=None):
    """Return model text, or None so callers fall back to rules. Never raises."""
    p = provider(db, tid)
    if not (p["enabled"] and p["key"] and p["features"].get(feature)): return None
    try:
        r = (client or httpx).post(f"{p['base_url'].rstrip('/')}/chat/completions", timeout=20, headers={"Authorization": f"Bearer {p['key']}"},
                                   json={"model": p["model"], "messages": messages, "temperature": 0.2, "max_tokens": max_tokens})
        r.raise_for_status(); return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.warning("Neurealm AI provider call failed, using rules: %s", type(e).__name__); return None

SYSTEM = "You are Neurealm AI, a friendly, humble IT service desk helper for Neurealm. Keep answers short and practical."

# ---------- provider settings ----------
class ProviderIn(BaseModel):
    enabled: bool = False; base_url: str = ""; model: str = ""; api_key: str | None = None; clear_key: bool = False; features: dict[str, bool] = {}

@router.get("/provider")
def get_provider(u=Depends(admin_only), db: Session = Depends(get_db)):
    p = provider(db, u.tenant_id); raw = settings_store.get(db, u.tenant_id, "ai.provider").get("v") or {}
    return {"enabled": p["enabled"], "base_url": p["base_url"], "model": p["model"], "features": p["features"], "has_key": bool(p["key"]),
            "key_source": "saved" if raw.get("api_key") else "environment" if p["key"] else None}

@router.put("/provider")
def put_provider(b: ProviderIn, u=Depends(admin_only), db: Session = Depends(get_db)):
    if b.base_url and not re.match(r"^https://", b.base_url) and not b.base_url.startswith("http://localhost"): raise HTTPException(400, "Please use an https:// address.")
    cur = settings_store.get(db, u.tenant_id, "ai.provider").get("v") or {}
    v = {**cur, "enabled": b.enabled, "base_url": b.base_url.strip(), "model": b.model.strip(), "features": {f: b.features.get(f, True) for f in FEATURES}}
    if b.api_key: v["api_key"] = b.api_key.strip()
    if b.clear_key: v.pop("api_key", None)
    settings_store.put(db, u.tenant_id, "ai.provider", {"v": v}); audit.log(db, u.id, "update", "ai_provider", None, {"enabled": b.enabled}); db.commit()
    return get_provider(u, db)

@router.post("/provider/test")
def test_provider(u=Depends(admin_only), db: Session = Depends(get_db)):
    p = provider(db, u.tenant_id)
    if not p["enabled"]: return {"ok": False, "message": "Neurealm AI is off. Rules are being used, and everything still works."}
    if not p["key"]: return {"ok": False, "message": "No API key yet."}
    t = llm(db, u.tenant_id, "assistant", [{"role": "user", "content": "Reply with the word OK."}], 5)
    return {"ok": bool(t), "message": "Connected." if t else "Couldn't reach the provider. Neurealm AI will keep using rules."}

def status(db, tid):
    p = provider(db, tid); on = p["enabled"] and bool(p["key"])
    return {"name": "Neurealm AI", "llm_enabled": on, "mode": "llm" if on else "rules", "features": p["features"]}

# ---------- assistant ----------
class AskIn(BaseModel):
    message: str; history: list[dict] = []

NUM = re.compile(r"\b([A-Z]{2,4}\d{7})\b", re.I)

@router.post("/assistant")
def assistant(b: AskIn, u=Depends(current_user), db: Session = Depends(get_db)):
    q = b.message.strip()
    if not q: raise HTTPException(400, "Ask me anything about IT help.")
    kb = ai.kb_suggest(db, q, 3, u.tenant_id); sources = [{"type": "kb", "id": k["id"], "title": k["title"]} for k in kb]; actions = []
    mine = db.scalars(select(Record).where(Record.tenant_id == u.tenant_id, Record.requester_id == u.id, Record.state.notin_(list(registry.CLOSED))).order_by(Record.id.desc()).limit(5)).all()
    found = None
    if (m := NUM.search(q)):
        r = db.scalar(select(Record).where(Record.tenant_id == u.tenant_id, Record.number == m.group(1).upper()))
        if r and (u.role != "end_user" or r.requester_id == u.id): found = r
    cats = [c for c in db.scalars(select(CatalogItem).where(CatalogItem.tenant_id == u.tenant_id, CatalogItem.active == True)) if any(w in q.lower() for w in c.name.lower().split() if len(w) > 3)]
    for c in cats[:2]: actions.append({"type": "catalog", "id": c.id, "label": f"Request “{c.name}”"})
    ql = q.lower()
    if any(w in ql for w in ("broken", "not working", "error", "can't", "cannot", "issue", "down", "crash")): actions.append({"type": "create_incident", "title": q[:120], "label": "Report this as an issue"})
    ctx = "\n".join([f"KB: {k['title']}" for k in kb] + [f"Open ticket {r.number}: {r.title} ({r.state})" for r in mine] + ([f"Ticket {found.number}: {found.title}, state {found.state}, priority {found.priority}"] if found else []))
    msgs = [{"role": "system", "content": SYSTEM + "\nContext:\n" + ctx}] + [m for m in b.history[-6:] if m.get("role") in ("user", "assistant")] + [{"role": "user", "content": q}]
    text = llm(db, u.tenant_id, "assistant", msgs)
    if text: return {"answer": text, "sources": sources, "actions": actions, "engine": "llm"}
    if found: ans = f"{found.number} “{found.title}” is {found.state.replace('_', ' ')} with priority {found.priority}."
    elif any(w in ql for w in ("my tickets", "my requests", "status", "open tickets")):
        ans = ("Here's what you have open: " + "; ".join(f"{r.number} {r.title} ({r.state.replace('_', ' ')})" for r in mine)) if mine else "You don't have anything open right now."
    elif kb: ans = f"This article might help: “{kb[0]['title']}”." + (" I've listed a couple more below." if len(kb) > 1 else "")
    elif actions: ans = "I couldn't find an article for that, but I can help you raise it."
    else: ans = "I'm not sure about that one yet. You can report an issue and a person from the desk will help."
    return {"answer": ans, "sources": sources, "actions": actions, "engine": "rules"}

# ---------- ticket AI ----------
def _ctx(db, r, internal=True):
    cs = db.scalars(select(Comment).where(Comment.record_id == r.id).order_by(Comment.id)).all()
    return [c for c in cs if internal or not c.internal]

def _sent(t, n=1):
    s = re.split(r"(?<=[.!?])\s+", (t or "").strip()); return " ".join(s[:n]).strip()

@router.post("/tickets/{module}/{rid}/summary")
def summary(module: str, rid: int, u=Depends(staff), db: Session = Depends(get_db)):
    r = get_record(db, module, rid, u); cs = _ctx(db, r)
    text = llm(db, u.tenant_id, "ticket", [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Summarise this ticket in 3 short bullet points.\nTitle: {r.title}\nDescription: {r.description}\nState: {r.state}\n" + "\n".join(f"- {c.body}" for c in cs[-10:])}])
    if text: return {"summary": text, "engine": "llm"}
    pts = [f"{r.title}: {_sent(r.description) or 'no description'}", f"Now {r.state.replace('_', ' ')}, priority {r.priority}" + (f", with {len(cs)} comment(s)" if cs else "")]
    if cs: pts.append(f"Latest: {_sent(cs[-1].body)}")
    return {"summary": "\n".join(f"• {p}" for p in pts), "engine": "rules"}

@router.post("/tickets/{module}/{rid}/reply")
def suggest_reply(module: str, rid: int, u=Depends(staff), db: Session = Depends(get_db)):
    r = get_record(db, module, rid, u); kb = ai.kb_suggest(db, f"{r.title} {r.description}", 1, u.tenant_id)
    name = (r.requester.full_name.split()[0] if getattr(r, "requester", None) else "there")
    text = llm(db, u.tenant_id, "ticket", [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Draft a short, warm reply to {name} about: {r.title}. {r.description}. " + (f"Mention KB article '{kb[0]['title']}'." if kb else "")}])
    if text: return {"reply": text, "engine": "llm"}
    body = f"Hi {name},\n\nThanks for letting us know about “{r.title}”. " + (f"While we look into it, this guide may help: “{kb[0]['title']}”. " if kb else "We're looking into it now. ")
    return {"reply": body + "We'll keep you posted here.\n\nThanks for your patience,\n" + u.full_name, "engine": "rules"}

@router.get("/tickets/{module}/{rid}/similar")
def similar(module: str, rid: int, u=Depends(staff), db: Session = Depends(get_db)):
    r = get_record(db, module, rid, u); t = set(ai.tokens(f"{r.title} {r.description}"))
    out = []
    for o in db.scalars(select(Record).where(Record.tenant_id == u.tenant_id, Record.module == module, Record.id != r.id)):
        s = len(t & set(ai.tokens(f"{o.title} {o.description}")))
        if s >= 2: out.append((s, o))
    return [{"id": o.id, "number": o.number, "title": o.title, "state": o.state, "score": s} for s, o in sorted(out, key=lambda x: -x[0])[:5]]

# ---------- writing help ----------
class WriteIn(BaseModel):
    text: str; mode: str = "improve"

def _tidy(t):
    t = re.sub(r"[ \t]+", " ", t.strip()); t = re.sub(r"\s+([,.!?])", r"\1", t); t = re.sub(r"\bi\b", "I", t)
    t = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    return t if re.search(r"[.!?]$", t) else t + "."

@router.post("/write")
def write(b: WriteIn, u=Depends(staff), db: Session = Depends(get_db)):
    if b.mode not in ("improve", "shorten", "friendly", "formal"): raise HTTPException(400, "Pick improve, shorten, friendly or formal.")
    if not b.text.strip(): raise HTTPException(400, "Write something first.")
    text = llm(db, u.tenant_id, "writing", [{"role": "system", "content": SYSTEM + " Rewrite the user's text. Return only the rewritten text."}, {"role": "user", "content": f"Make this {b.mode}: {b.text}"}])
    if text: return {"text": text, "engine": "llm"}
    t = _tidy(b.text)
    if b.mode == "shorten": t = _sent(t, 2)
    if b.mode == "friendly": t = ("Hi! " if not re.match(r"(?i)^(hi|hello|dear)", t) else "") + t + " Thanks so much!"
    if b.mode == "formal": t = re.sub(r"(?i)\b(hi|hey)\b!?", "Hello", t).replace("can't", "cannot").replace("won't", "will not").replace("don't", "do not") + " Kind regards."
    return {"text": t, "engine": "rules"}

# ---------- AI report builder ----------
class ReportQ(BaseModel):
    question: str

GROUPS = {"priority": "priority", "state": "state", "status": "state", "category": "category", "group": "assignment_group", "team": "assignment_group", "assignee": "assignee", "month": "month", "day": "day", "week": "week"}

def parse_question(q):
    ql = q.lower(); spec = {"module": "incident", "group_by": "priority", "days": 30, "filter": {}}
    for m, meta in registry.MODULES.items():
        lab = meta["label"].lower()
        if lab in ql or lab.rstrip("s") in ql or m.replace("_", " ") in ql: spec["module"] = m; break
    if (g := re.search(r"\bby (\w+)", ql)) and g.group(1) in GROUPS: spec["group_by"] = GROUPS[g.group(1)]
    if (d := re.search(r"last (\d+) (day|week|month)s?", ql)): spec["days"] = int(d.group(1)) * {"day": 1, "week": 7, "month": 30}[d.group(2)]
    elif "this week" in ql: spec["days"] = 7
    elif "this year" in ql or "last year" in ql: spec["days"] = 365
    for p in ("p1", "p2", "p3", "p4"):
        if re.search(rf"\b{p}\b", ql): spec["filter"]["priority"] = p.upper()
    if "open" in ql: spec["filter"]["open"] = True
    if "breach" in ql: spec["filter"]["breached"] = True
    return spec

def run_spec(db, u, spec):
    if spec.get("module") not in registry.MODULES: raise HTTPException(400, "Unknown module")
    since = now() - timedelta(days=int(spec.get("days") or 30))
    rows = db.scalars(select(Record).where(Record.tenant_id == u.tenant_id, Record.module == spec["module"])).all()
    rows = [r for r in rows if r.created_at and r.created_at.replace(tzinfo=None) >= since.replace(tzinfo=None)]
    f = spec.get("filter") or {}
    if f.get("priority"): rows = [r for r in rows if r.priority == f["priority"]]
    if f.get("open"): rows = [r for r in rows if r.state not in registry.CLOSED]
    if f.get("breached"): rows = [r for r in rows if r.sla_breached]
    g = spec.get("group_by", "priority")
    def key(r):
        if g == "assignment_group": return r.assignment_group.name if r.assignment_group else "Unassigned"
        if g == "assignee": return r.assignee.full_name if r.assignee else "Unassigned"
        if g == "month": return r.created_at.strftime("%Y-%m")
        if g == "week": return r.created_at.strftime("%G-W%V")
        if g == "day": return r.created_at.strftime("%Y-%m-%d")
        return str(getattr(r, g, None) or "none")
    c = Counter(key(r) for r in rows)
    data = sorted(c.items()) if g in ("month", "week", "day") else c.most_common()
    return {"rows": [{"label": k, "count": v} for k, v in data], "total": len(rows), "chart": "line" if g in ("month", "week", "day") else "bar"}

@router.post("/report")
def ai_report(b: ReportQ, u=Depends(staff), db: Session = Depends(get_db)):
    if not b.question.strip(): raise HTTPException(400, "Ask a question, like “incidents by priority last 30 days”.")
    spec, engine = None, "rules"
    t = llm(db, u.tenant_id, "reports", [{"role": "system", "content": "Turn the question into JSON with keys module (one of " + ", ".join(registry.MODULES) + "), group_by (priority, state, category, assignment_group, assignee, day, week, month), days (int), filter ({priority?, open?, breached?}). Reply only JSON."}, {"role": "user", "content": b.question}], 200)
    if t:
        try:
            s = json.loads(t[t.find("{"): t.rfind("}") + 1])
            if s.get("module") in registry.MODULES and s.get("group_by") in set(GROUPS.values()): spec, engine = {"filter": {}, "days": 30, **s}, "llm"
        except Exception: pass
    spec = spec or parse_question(b.question)
    res = run_spec(db, u, spec)
    title = f"{registry.MODULES[spec['module']]['label']} by {spec['group_by'].replace('_', ' ')}, last {spec['days']} days"
    return {"title": title, "spec": spec, "engine": engine, **res}
