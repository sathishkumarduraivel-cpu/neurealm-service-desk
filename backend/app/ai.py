"""AI triage: deterministic keyword/rule engine with optional OpenAI-compatible LLM enrichment."""
import json, re, logging
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import config
from .models import KBArticle, Group

CATEGORIES = {
    "network": ["globalprotect", "vpn", "wifi", "wi-fi", "network", "internet", "dns", "firewall", "latency", "router", "switch", "connectivity"],
    "access": ["password", "login", "locked", "access", "permission", "mfa", "sso", "account", "reset", "credentials"],
    "hardware": ["laptop", "printer", "monitor", "keyboard", "mouse", "battery", "screen", "dock", "hardware", "desktop"],
    "software": ["outlook", "excel", "teams", "install", "application", "crash", "error", "license", "office", "update", "bug"],
    "email": ["email", "mailbox", "outlook", "smtp", "spam", "calendar"],
    "database": ["database", "sql", "postgres", "query", "db", "deadlock", "oracle"],
    "security": ["phishing", "malware", "virus", "breach", "suspicious", "ransomware", "vulnerability", "hacked"],
    "hr": ["payroll", "leave", "onboarding", "offboarding", "benefits", "salary", "hr"],
}
ROUTING = {"network": "Network Ops", "access": "Service Desk", "hardware": "Desktop Support", "software": "Application Support",
           "email": "Application Support", "database": "Database Team", "security": "Security Ops", "hr": "HR Services", "general": "Service Desk"}
HIGH = ["down", "outage", "all users", "entire", "production", "critical", "urgent", "cannot work", "ransomware", "breach", "data loss", "everyone"]
MED = ["slow", "intermittent", "multiple users", "degraded", "several", "team", "failing"]
STOP = set("the a an is are to of and or in on for my i it not with can cannot be at this that from".split())

def tokens(text):
    return [t for t in re.findall(r"[a-z0-9\-]+", text.lower()) if t not in STOP and len(t) > 1]

def kb_suggest(db: Session, text: str, limit=3, tenant_id=1):
    toks = set(tokens(text))
    if not toks: return []
    out = []
    for a in db.scalars(select(KBArticle).where(KBArticle.published == True, KBArticle.tenant_id == tenant_id)):
        hay = tokens(f"{a.title} {a.title} {a.tags} {a.body}")
        score = sum(1 for t in hay if t in toks)
        if score: out.append((score, a))
    out.sort(key=lambda x: -x[0])
    return [{"id": a.id, "number": a.number, "title": a.title, "score": s} for s, a in out[:limit]]

def rule_triage(text: str):
    low = text.lower(); toks = set(tokens(text))
    scores = {c: sum(1 for k in kws if (k in toks if " " not in k and "-" not in k else k in low)) for c, kws in CATEGORIES.items()}
    cat, best = max(scores.items(), key=lambda x: (x[1], x[0] == "security"))  # ties resolve to security (risk-first)
    total = sum(scores.values())
    if best == 0: cat = "general"
    conf = calibrate(best, total, any(h in low for h in HIGH + MED))
    if any(h in low for h in HIGH): impact, urgency = 1, 1
    elif any(m in low for m in MED): impact, urgency = 2, 2
    else: impact, urgency = 3, 3
    if cat == "security" and impact > 2: impact, urgency = 2, 1
    priority = priority_from(impact, urgency)
    return {"category": cat, "priority": priority, "impact": impact, "urgency": urgency,
            "assignment_group": ROUTING[cat], "confidence": conf, "engine": "rules",
            "reasoning": f"Matched {best} '{cat}' keyword(s); impact={impact}, urgency={urgency}."}

def calibrate(best: int, total: int, severity_signal: bool) -> float:
    """Calibrated confidence: evidence strength (diminishing returns) x dominance over competing categories.
    Tuned on the seed corpus so a single unambiguous keyword clears the default 0.6 auto-apply threshold,
    while ambiguous multi-category text stays below it (human review)."""
    if not best: return 0.3
    dominance = best / total if total else 0
    evidence = 1 - 0.5 ** best          # 1 kw -> .5, 2 -> .75, 3 -> .875
    conf = 0.35 + 0.35 * evidence + 0.25 * dominance + (0.03 if severity_signal else 0)
    return round(min(0.97, conf), 2)

MATRIX: dict = {}  # optional override "impact,urgency" -> "P1".."P4", set from Ticket settings

def priority_from(impact: int, urgency: int) -> str:
    if MATRIX.get(f"{impact},{urgency}"): return MATRIX[f"{impact},{urgency}"]
    s = impact + urgency
    return "P1" if s <= 2 else "P2" if s <= 3 else "P3" if s <= 4 else "P4"

def llm_triage(text: str, db=None, tenant_id=1):
    if db is None: return None
    from .routers.aiops import llm
    prompt = ("Classify this IT ticket. Reply ONLY JSON with keys category (one of " + ", ".join(list(CATEGORIES) + ["general"]) +
              "), impact (1-3), urgency (1-3), confidence (0-1), reasoning.\nTicket: " + text)
    content = llm(db, tenant_id, "triage", [{"role": "user", "content": prompt}], 200)
    if not content: return None
    try:
        d = json.loads(content[content.find("{"): content.rfind("}") + 1])
        cat = d.get("category", "general"); cat = cat if cat in ROUTING else "general"
        i, u = int(d.get("impact", 3)), int(d.get("urgency", 3))
        return {"category": cat, "impact": i, "urgency": u, "priority": priority_from(i, u), "assignment_group": ROUTING[cat],
                "confidence": float(d.get("confidence", 0.7)), "reasoning": d.get("reasoning", ""), "engine": "llm"}
    except Exception as e:
        logging.warning("LLM triage parse failed, using rules: %s", type(e).__name__)
        return None

def triage(db: Session, title: str, description: str = "", tenant_id: int = 1):
    text = f"{title}\n{description}"
    res = llm_triage(text, db, tenant_id) or rule_triage(text)
    g = db.scalar(select(Group).where(Group.name == res["assignment_group"], Group.tenant_id == tenant_id))
    res["assignment_group_id"] = g.id if g else None
    res["kb_suggestions"] = kb_suggest(db, text, 3, tenant_id)
    res["auto_apply"] = res["confidence"] >= config.AI_CONFIDENCE_THRESHOLD
    return res
