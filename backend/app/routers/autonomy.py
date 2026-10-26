"""Phase E — Quality audit-style quality auditing, DEX scores, FinOps center, AI patch management (dry-run, kill switch)."""
import hashlib
from collections import Counter, defaultdict
from statistics import mean
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Record, QualityAudit, DexDevice, CostRecord, User, Comment, now
from ..security import staff, admin_only
from ..schemas import RecordCreate
from ..deps import scoped, get_or_404, out, notify, link_for
from .. import ai, audit, registry, hooks, settings_store, sla

router = APIRouter(prefix="/api", tags=["autonomy"])

# ---------------- Quality audit quality auditing ----------------
POS = {"thanks", "thank", "great", "resolved", "working", "perfect", "appreciate", "quick", "helpful", "awesome"}
NEG = {"still", "again", "angry", "frustrated", "unacceptable", "slow", "worst", "not working", "escalate", "disappointed", "waiting"}

def sentiment(texts):
    t = " ".join(texts).lower(); toks = set(ai.tokens(t))
    p = sum(1 for w in POS if w in toks); n = sum(1 for w in NEG if (w in t if " " in w else w in toks))
    return "positive" if p > n else "negative" if n > p else "neutral"

CHECKS = [  # (key, weight, label, finding)
    ("description", 15, "Description is meaningful (≥ 20 chars)", "Capture a clear problem description"),
    ("categorized", 10, "Categorised (not 'general')", "Categorise the ticket correctly"),
    ("priority_aligned", 15, "Priority matches impact × urgency matrix", "Priority deviates from the ITIL matrix"),
    ("assigned", 10, "Assigned to a group", "Route to an assignment group"),
    ("resolution_notes", 20, "Resolution notes documented", "Document resolution notes for knowledge reuse"),
    ("customer_update", 10, "Requester received a public update", "Send at least one customer-visible update"),
    ("sla_met", 20, "Resolved within SLA", "SLA breached — review prioritisation & escalation"),
]

def audit_record(r):
    comments = r.comments or []
    c = {"description": len((r.description or "").strip()) >= 20, "categorized": (r.category or "general") != "general",
         "priority_aligned": r.priority == ai.priority_from(r.impact, r.urgency) or r.data.get("escalated_from") is not None or r.data.get("sn_number") is not None,
         "assigned": bool(r.assignment_group_id), "resolution_notes": bool(r.data.get("resolution_notes")) or any("resol" in (x.body or "").lower() for x in comments),
         "customer_update": any(not x.internal for x in comments), "sla_met": not r.sla_breached}
    score = sum(w for k, w, _, _ in CHECKS if c[k])
    sent = sentiment([x.body for x in comments if not x.internal])
    if sent == "negative": score = max(0, score - 10)
    return score, c, sent, [f for k, _, _, f in CHECKS if not c[k]]

@router.post("/quality/audit")
def run_quality_audit(db: Session = Depends(get_db), u=Depends(staff)):
    """100% audit of resolved/closed ITSM & CSM tickets (Quality audit engine)."""
    recs = db.scalars(scoped(select(Record), Record, u).where(Record.module.in_(["incident", "case", "request", "hr_case"]), Record.state.in_(["resolved", "closed", "fulfilled"]))).all()
    for old in db.scalars(scoped(select(QualityAudit), QualityAudit, u).where(QualityAudit.record_id.in_([r.id for r in recs]))): db.delete(old)
    for r in recs:
        score, c, sent, f = audit_record(r)
        db.add(QualityAudit(tenant_id=u.tenant_id, record_id=r.id, score=score, checks=c, sentiment=sent, findings=f))
        r.data = {**r.data, "quality_score": score}
    audit.log(db, u.id, "quality_audit", "quality_audit", "batch", {"audited": len(recs)}); db.commit()
    return quality_summary(db, u)

@router.get("/quality/summary")
def quality_summary(db: Session = Depends(get_db), u=Depends(staff)):
    rows = db.scalars(scoped(select(QualityAudit), QualityAudit, u)).all()
    recs = {r.id: r for r in db.scalars(select(Record).where(Record.id.in_([q.record_id for q in rows])))}
    users = {x.id: x.full_name for x in db.scalars(scoped(select(User), User, u))}
    by_agent = defaultdict(list)
    for q in rows: by_agent[users.get(recs[q.record_id].assignee_id, "Unassigned")].append(q)
    findings = Counter(f for q in rows for f in q.findings)
    return {"audited": len(rows), "avg_score": round(mean(q.score for q in rows), 1) if rows else 0, "coverage_pct": 100.0 if rows else 0,
            "sentiment": dict(Counter(q.sentiment for q in rows)),
            "checks": [{"key": k, "label": l, "pass_pct": round(100 * sum(q.checks.get(k, False) for q in rows) / len(rows), 1) if rows else 0} for k, _, l, _ in CHECKS],
            "by_agent": sorted([{"agent": a, "tickets": len(v), "avg_score": round(mean(x.score for x in v), 1), "training_gaps": [f for f, _ in Counter(f for x in v for f in x.findings).most_common(2)]} for a, v in by_agent.items()], key=lambda x: x["avg_score"]),
            "top_findings": [{"finding": f, "count": n} for f, n in findings.most_common(6)],
            "lowest": [{"record_id": q.record_id, "number": recs[q.record_id].number, "title": recs[q.record_id].title, "module": recs[q.record_id].module, "score": q.score, "findings": q.findings} for q in sorted(rows, key=lambda q: q.score)[:8]]}

# ---------------- DEX ----------------
def dex_score(d):
    parts = {"boot": max(0, 100 - max(0, d.boot_seconds - 30) * 2), "stability": max(0, 100 - d.crashes_7d * 15), "cpu": max(0, 100 - max(0, d.cpu_pct - 50) * 2),
             "memory": max(0, 100 - max(0, d.mem_pct - 60) * 2), "disk": min(100, d.disk_free_pct * 4), "sentiment": (d.sentiment - 1) * 25}
    w = {"boot": 0.15, "stability": 0.25, "cpu": 0.15, "memory": 0.15, "disk": 0.1, "sentiment": 0.2}
    score = round(sum(parts[k] * w[k] for k in w))
    issues = []
    if d.disk_free_pct < 15: issues.append({"issue": "Low disk space", "remediation": "disk_cleanup"})
    if d.boot_seconds > 60: issues.append({"issue": "Slow boot", "remediation": "startup_optimize"})
    if d.crashes_7d >= 3: issues.append({"issue": "Frequent app crashes", "remediation": "app_repair"})
    if d.mem_pct > 85: issues.append({"issue": "Memory pressure", "remediation": "memory_upgrade_ticket"})
    if d.sentiment < 3: issues.append({"issue": "Poor user sentiment", "remediation": "proactive_outreach"})
    return score, {k: round(v) for k, v in parts.items()}, issues

def _dex(d):
    s, parts, issues = dex_score(d)
    return {"id": d.id, "hostname": d.hostname, "user": d.user_email, "os": d.os, "score": s, "parts": parts, "issues": issues,
            **{k: getattr(d, k) for k in ("boot_seconds", "crashes_7d", "cpu_pct", "mem_pct", "disk_free_pct", "sentiment")}}

class Telemetry(BaseModel):
    hostname: str; user_email: str = ""; os: str = "Windows 11"; boot_seconds: float = 40; crashes_7d: int = 0; cpu_pct: float = 30; mem_pct: float = 50; disk_free_pct: float = 40; sentiment: float = 4

@router.post("/dex/telemetry")
def dex_telemetry(items: list[Telemetry], db: Session = Depends(get_db), u=Depends(staff)):
    for t in items:
        d = db.scalar(scoped(select(DexDevice), DexDevice, u).where(DexDevice.hostname == t.hostname))
        if not d: d = DexDevice(tenant_id=u.tenant_id, hostname=t.hostname); db.add(d)
        for k, v in t.model_dump().items(): setattr(d, k, v)
        d.updated_at = now()
    db.commit(); return {"ingested": len(items)}

@router.get("/dex/devices")
def dex_devices(db: Session = Depends(get_db), u=Depends(staff)):
    return sorted([_dex(d) for d in db.scalars(scoped(select(DexDevice), DexDevice, u))], key=lambda x: x["score"])

@router.get("/dex/summary")
def dex_summary(db: Session = Depends(get_db), u=Depends(staff)):
    ds = dex_devices(db, u)
    return {"devices": len(ds), "avg_score": round(mean(d["score"] for d in ds), 1) if ds else 0, "poor": sum(d["score"] < 60 for d in ds),
            "issues": dict(Counter(i["issue"] for d in ds for i in d["issues"]))}

REMEDIATE = {"disk_cleanup": ("disk_free_pct", lambda v: min(100, v + 25)), "startup_optimize": ("boot_seconds", lambda v: max(20, v * 0.55)),
             "app_repair": ("crashes_7d", lambda v: 0), "memory_upgrade_ticket": None, "proactive_outreach": None}

@router.post("/dex/{did}/remediate")
def dex_remediate(did: int, action: str, db: Session = Depends(get_db), u=Depends(staff)):
    d = get_or_404(db, DexDevice, did, u)
    if action not in REMEDIATE: raise HTTPException(400, "Unknown remediation")
    before = dex_score(d)[0]; created = None
    if REMEDIATE[action]:
        f, fn = REMEDIATE[action]; setattr(d, f, fn(getattr(d, f)))
    else:
        from ..main import create_record_core
        title = f"DEX: {'Memory upgrade for' if action == 'memory_upgrade_ticket' else 'Proactive outreach to user of'} {d.hostname}"
        created = create_record_core(db, u, "incident", RecordCreate(title=title, description=f"Raised automatically by DEX engine. Score {before}.", data={"dex_device": d.hostname}, use_ai=False, impact=3, urgency=3)).number
    audit.log(db, u.id, "dex_remediate", "dex", d.hostname, {"action": action}); db.commit()
    return {"device": _dex(d), "before": before, "after": dex_score(d)[0], "ticket": created}

# ---------------- FinOps center ----------------
def _impact(weight, total):
    share = weight / total if total else 0
    return "high" if share >= 0.05 else "medium" if share >= 0.01 else "low"

def recommendations(db, u):
    """Optimisation ideas ranked by impact (high / medium / low). No monetary values are exposed."""
    from .itom import anomalies, cost_rows
    rows = cost_rows(db, u); recs = []
    last = max((r.month for r in rows), default=None); total = sum(r.amount for r in rows if r.month == last)
    for r in rows:
        if r.month == last and r.kind == "cloud" and r.utilization < 0.4:
            recs.append({"id": f"rightsize:{r.provider}:{r.service}", "type": "rightsizing", "title": f"Rightsize {r.provider} {r.service} ({round(r.utilization * 100)}% utilised)", "_w": r.amount * (1 - r.utilization) * 0.6, "action": "change"})
        if r.month == last and r.kind == "saas" and r.utilization < 0.6:
            recs.append({"id": f"saas:{r.service}", "type": "saas_harvest", "title": f"Harvest unused {r.service} seats ({round(r.utilization * 100)}% active)", "_w": r.amount * (1 - r.utilization) * 0.8, "action": "task"})
    for l in db.scalars(scoped(select(Record), Record, u).where(Record.module == "license")):
        lic = hooks.license(l)
        if lic["reclaimable_seats"]: recs.append({"id": f"license:{l.number}", "type": "license_reclaim", "title": f"Reclaim {lic['reclaimable_seats']} {l.title} seats", "_w": total * 0.01 * min(5, lic["reclaimable_seats"] / 10), "action": "task"})
        if lic["compliance"] == "over_deployed": recs.append({"id": f"true-up:{l.number}", "type": "compliance", "title": f"True-up {l.title}: over-deployed ({lic['utilization_pct']}%)", "_w": 0, "action": "task"})
    for a in anomalies(rows):
        recs.append({"id": f"anomaly:{a['provider']}:{a['service']}", "type": "anomaly", "title": f"Investigate {a['provider']} {a['service']} usage +{a['increase_pct']}%", "_w": a["_delta"], "action": "incident"})
    applied = set(settings_store.get(db, u.tenant_id, "finops.applied").get("ids", []))
    recs.sort(key=lambda r: -r["_w"])
    return [{**{k: v for k, v in r.items() if k != "_w"}, "impact": _impact(r["_w"], total) if r["_w"] else "low", "applied": r["id"] in applied} for r in recs]

@router.get("/finops/center")
def finops_center(db: Session = Depends(get_db), u=Depends(staff)):
    from .itom import costs
    c = costs(db, u); recs = recommendations(db, u)
    open_ = [r for r in recs if not r["applied"]]
    return {"current_month": c["current_month"], "current_index": c["current_index"], "unit": c["unit"], "trend": c["trend"], "providers": c["providers"], "by_kind": c["by_kind"],
            "anomalies": c["anomalies"], "recommendations": recs, "open_count": len(open_), "high_impact_open": sum(1 for r in open_ if r["impact"] == "high"),
            "applied_count": len(recs) - len(open_)}

@router.post("/finops/apply")
def finops_apply(rec_id: str, db: Session = Depends(get_db), u=Depends(staff)):
    rec = next((r for r in recommendations(db, u) if r["id"] == rec_id), None)
    if not rec: raise HTTPException(404, "Recommendation not found")
    if rec["applied"]: raise HTTPException(400, "Already applied")
    from ..main import create_record_core
    module = {"change": "change", "task": "task", "incident": "incident"}[rec["action"]]
    data = {"finops_recommendation": rec_id, "impact": rec["impact"]}
    if module == "change": data.update({"change_type": "normal", "rollback_plan": "Scale back to previous size", "tested": True})
    r = create_record_core(db, u, module, RecordCreate(title=f"Optimise: {rec['title']}", description="Optimisation opportunity found by Neurealm Service Desk", data=data, use_ai=False))
    ids = settings_store.get(db, u.tenant_id, "finops.applied").get("ids", []) + [rec_id]
    settings_store.put(db, u.tenant_id, "finops.applied", {"ids": ids}); audit.log(db, u.id, "finops_apply", "finops", rec_id, {"record": r.number}); db.commit()
    return {"record": out(r), "recommendation": {**rec, "applied": True}}

# ---------------- Patch management ----------------
OS_MATCH = {"Windows": ["windows"], "Linux": ["rhel", "ubuntu", "debian", "linux", "centos"], "macOS": ["macos", "mac os"]}

def _patch(db, u, pid):
    j = get_or_404(db, Record, pid, u)
    if j.module != "patch_job": raise HTTPException(404)
    return j

def targets(db, u, j):
    keys = OS_MATCH.get(j.data.get("os", "Windows"), []); env = j.data.get("environment")
    cis = db.scalars(scoped(select(Record), Record, u).where(Record.module == "ci", Record.state == "operational")).all()
    return [c for c in cis if c.data.get("ci_class") in ("server", "laptop") and any(k in str(c.data.get("os", "")).lower() for k in keys) and (not env or c.data.get("environment", env) == env or c.data.get("ci_class") == "laptop")]

@router.post("/patch/{pid}/dry-run")
def patch_dry_run(pid: int, db: Session = Depends(get_db), u=Depends(staff)):
    from .itom import impacted
    j = _patch(db, u, pid); ts = targets(db, u, j)
    patches = [p.strip() for p in str(j.data.get("patches", "")).split(",") if p.strip()]
    imp = set().union(*[impacted(db, u, t.id) for t in ts]) if ts else set()
    services = [r.title for r in db.scalars(select(Record).where(Record.id.in_(imp)))]
    conflicts = [c.number for c in db.scalars(scoped(select(Record), Record, u).where(Record.module == "change", Record.state.in_(["scheduled", "implement"])))
                 if j.data.get("window") and str(c.data.get("planned_start", ""))[:10] == str(j.data.get("window"))[:10]]
    prod = j.data.get("environment") == "production"
    risk = min(100, 10 * len(ts) + 15 * len(services) + (25 if prod else 0) + 10 * len(conflicts))
    result = {"targets": [{"id": t.id, "name": t.title, "os": t.data.get("os")} for t in ts], "patch_count": len(patches), "impacted_services": services, "change_conflicts": conflicts,
              "reboot_required": any(p.upper().startswith("KB") for p in patches) or j.data.get("os") == "Linux", "risk_score": risk, "requires_admin_approval": prod or risk >= 50,
              "waves": [{"wave": "canary", "targets": [t.title for t in ts[:max(1, len(ts) // 10)]]}, {"wave": "broad", "targets": [t.title for t in ts[max(1, len(ts) // 10):]]}], "simulated_at": now().isoformat(timespec="seconds")}
    j.data = {**j.data, "dry_run": result}
    if j.state == "draft": j.state = "dry_run_complete"
    audit.log(db, u.id, "patch_dry_run", "patch_job", j.number, {"targets": len(ts), "risk": risk}); db.commit()
    return {"job": out(j), "dry_run": result}

@router.post("/patch/{pid}/approve")
def patch_approve(pid: int, db: Session = Depends(get_db), u=Depends(staff)):
    j = _patch(db, u, pid)
    if j.state != "dry_run_complete": raise HTTPException(400, "Run a dry-run first")
    if j.data["dry_run"]["requires_admin_approval"] and u.role != "admin": raise HTTPException(403, "Production / high-risk patch jobs need admin approval")
    j.state = "approved"; j.data = {**j.data, "approved_by": u.full_name}
    audit.log(db, u.id, "patch_approve", "patch_job", j.number); db.commit(); return out(j)

def _kill(db, u): return settings_store.get(db, u.tenant_id, "patch.kill_switch")

@router.post("/patch/{pid}/deploy")
def patch_deploy(pid: int, db: Session = Depends(get_db), u=Depends(staff)):
    j = _patch(db, u, pid); ks = _kill(db, u)
    if ks["engaged"]: raise HTTPException(423, f"Kill switch engaged: {ks.get('reason') or 'patching halted'}")
    if j.state not in ("approved", "halted"): raise HTTPException(400, "Job must be approved before deployment")
    j.state = "deploying"; results = []; ts = j.data.get("dry_run", {}).get("targets", [])
    fail_threshold = 0.2
    for i, t in enumerate(ts):
        ok = int(hashlib.sha256(f"{j.number}{t['name']}".encode()).hexdigest(), 16) % 10 != 0  # deterministic ~10% failure
        results.append({"target": t["name"], "status": "success" if ok else "failed", "wave": "canary" if i < max(1, len(ts) // 10) else "broad"})
        failed = sum(r["status"] == "failed" for r in results)
        if len(results) >= 2 and failed / len(results) > fail_threshold:
            j.state = "halted"; break
    else:
        j.state = "completed"
    j.data = {**j.data, "deployment": {"results": results, "finished_at": now().isoformat(timespec="seconds"), "auto_halted": j.state == "halted"}}
    audit.log(db, u.id, "patch_deploy", "patch_job", j.number, {"state": j.state, "targets": len(results)}); db.commit()
    return out(j)

class KillIn(BaseModel):
    engaged: bool; reason: str = ""

@router.get("/patch/kill-switch")
def kill_get(db: Session = Depends(get_db), u=Depends(staff)): return _kill(db, u)

@router.post("/patch/kill-switch")
def kill_set(b: KillIn, db: Session = Depends(get_db), u=Depends(admin_only)):
    v = settings_store.put(db, u.tenant_id, "patch.kill_switch", {"engaged": b.engaged, "reason": b.reason, "by": u.full_name, "at": now().isoformat(timespec="seconds")})
    halted = []
    if b.engaged:
        for j in db.scalars(scoped(select(Record), Record, u).where(Record.module == "patch_job", Record.state == "deploying")): j.state = "halted"; halted.append(j.number)
    for a in db.scalars(scoped(select(User), User, u).where(User.role == "admin")):
        notify(db, u.tenant_id, f"Patch kill switch {'ENGAGED' if b.engaged else 'released'} by {u.full_name}", "escalation", a.id, None, "/patch")
    audit.log(db, u.id, "kill_switch", "patch", "global", {"engaged": b.engaged, "halted": halted}); db.commit()
    return {**v, "halted_jobs": halted}
