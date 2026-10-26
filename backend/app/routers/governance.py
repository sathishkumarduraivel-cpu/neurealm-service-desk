"""Phase D — SecOps (SIEM intake, playbooks, vulnerability response), GRC (compliance posture, continuous control monitoring, risk heatmap), SPM/PPM."""
from collections import Counter, defaultdict
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Record, Comment, now
from ..security import staff
from ..schemas import RecordCreate
from ..deps import scoped, get_or_404, out, next_number
from .. import audit, registry, hooks, bus

router = APIRouter(prefix="/api", tags=["governance"])
def _recs(db, u, module): return db.scalars(scoped(select(Record), Record, u).where(Record.module == module)).all()

# ---------------- SecOps ----------------
SEC_PLAYBOOKS = {
    "phishing": ["Quarantine email across mailboxes", "Block sender domain & URLs at gateway", "Reset credentials of users who clicked", "Notify affected users"],
    "ransomware": ["Isolate affected endpoints from network (EDR)", "Disable compromised accounts", "Block C2 IPs on firewall", "Snapshot & preserve evidence", "Restore from immutable backup"],
    "malware": ["Isolate endpoint", "Run full EDR scan", "Remove persistence", "Re-image if needed"],
    "credential_theft": ["Force password reset & revoke sessions", "Enforce MFA re-registration", "Review sign-in logs for lateral movement"],
    "ddos": ["Enable upstream scrubbing", "Rate-limit at WAF", "Scale edge capacity"],
}

class SiemAlert(BaseModel):
    source: str = "sentinel"; rule: str; severity: str = "high"; host: str = ""; user: str = ""; source_ip: str = ""; attack_vector: str = "other"; mitre_tactic: str = ""

@router.post("/secops/siem", status_code=201)
def siem_intake(a: SiemAlert, db: Session = Depends(get_db), u=Depends(staff)):
    from ..main import create_record_core
    imp = {"critical": 1, "high": 1, "medium": 2, "low": 3}.get(a.severity, 2)
    r = create_record_core(db, u, "sec_incident", RecordCreate(title=f"[{a.source}] {a.rule}", description=f"Host {a.host} user {a.user} src {a.source_ip}", impact=imp, urgency=imp, use_ai=False,
                           data={"attack_vector": a.attack_vector, "mitre_tactic": a.mitre_tactic, "affected_ci": a.host, "source_ip": a.source_ip, "siem": a.source}))
    return out(r)

@router.post("/secops/{rid}/playbook")
def run_playbook(rid: int, dry_run: bool = False, db: Session = Depends(get_db), u=Depends(staff)):
    r = get_or_404(db, Record, rid, u)
    if r.module != "sec_incident": raise HTTPException(404)
    vec = r.data.get("attack_vector", "other"); steps = SEC_PLAYBOOKS.get(vec)
    if not steps: raise HTTPException(400, f"No playbook for vector '{vec}'")
    results = [{"step": s, "status": "simulated" if dry_run else "executed"} for s in steps]
    if not dry_run:
        for s in steps: db.add(Comment(record_id=r.id, author_id=u.id, body=f"🛡️ Playbook step executed: {s}", internal=True))
        if r.state in ("new", "analysis"): r.state = "contain"
        r.data = {**r.data, "playbook": f"{vec}-response", "playbook_runs": r.data.get("playbook_runs", 0) + 1}
    audit.log(db, u.id, "playbook_dry_run" if dry_run else "playbook", "sec_incident", r.number, {"vector": vec}); db.commit()
    return {"record": out(r), "dry_run": dry_run, "steps": results}

class VulnFinding(BaseModel):
    cve: str; cvss: float; affected_ci: str; title: str = ""; patch_available: bool = True; scanner: str = "qualys"

@router.post("/secops/vulns/import")
def vuln_import(items: list[VulnFinding], db: Session = Depends(get_db), u=Depends(staff)):
    existing = {(v.data.get("cve"), v.data.get("affected_ci")): v for v in _recs(db, u, "vulnerability")}
    created = updated = 0
    for f in items:
        v = existing.get((f.cve, f.affected_ci))
        if v: v.data = {**v.data, "cvss": f.cvss, "patch_available": f.patch_available, "last_seen": now().isoformat()}; hooks.compute(v); updated += 1
        else:
            v = Record(tenant_id=u.tenant_id, module="vulnerability", number=next_number(db, "vulnerability"), title=f.title or f"{f.cve} on {f.affected_ci}", state="open", requester_id=u.id,
                       impact=3, urgency=3, category="security", ai_suggestion={}, created_at=now(), data={**f.model_dump(), "last_seen": now().isoformat()})
            hooks.compute(v); db.add(v); db.flush(); created += 1
    audit.log(db, u.id, "vuln_import", "vulnerability", "batch", {"created": created, "updated": updated}); db.commit()
    return {"created": created, "updated": updated}

def overdue_vulns(vulns):
    return [v for v in vulns if v.state not in registry.CLOSED and (now() - v.created_at).days > v.data.get("remediation_days", 90)]

@router.get("/secops/summary")
def secops_summary(db: Session = Depends(get_db), u=Depends(staff)):
    sirs, vulns = _recs(db, u, "sec_incident"), _recs(db, u, "vulnerability")
    open_v = [v for v in vulns if v.state not in registry.CLOSED]
    return {"open_incidents": sum(s.state not in registry.CLOSED for s in sirs), "by_vector": dict(Counter(s.data.get("attack_vector") for s in sirs)),
            "open_vulns": len(open_v), "vulns_by_severity": dict(Counter(v.data.get("severity") for v in open_v)), "overdue_vulns": len(overdue_vulns(vulns)),
            "top_vulns": [out(v) for v in sorted(open_v, key=lambda v: -float(v.data.get("cvss") or 0))[:6]], "playbooks": list(SEC_PLAYBOOKS)}

# ---------------- GRC ----------------
FRAMEWORKS = ["ISO27001", "SOC2", "GDPR"]

def _automated_checks(db, u):
    from .itom import cmdb_quality
    from .. import audit as _a
    vulns = _recs(db, u, "vulnerability"); sirs = _recs(db, u, "sec_incident"); changes = _recs(db, u, "change")
    crit_overdue = [v for v in overdue_vulns(vulns) if v.data.get("severity") in ("critical", "high")]
    stale_sir = [s for s in sirs if s.state not in registry.CLOSED and (now() - s.created_at).days > 30]
    unapproved = [c for c in changes if c.state in ("implement", "review", "closed") and c.data.get("change_type") != "standard" and c.approvals and not all(a.state == "approved" for a in c.approvals)]
    dq = cmdb_quality(db, u)["avg_dq_score"]
    chain = _a.verify_chain(db)["valid"]
    return {
        "vuln_mgmt": (not crit_overdue, f"{len(crit_overdue)} critical/high vulnerabilities past remediation SLA"),
        "incident_response": (not stale_sir, f"{len(stale_sir)} security incidents open > 30 days"),
        "change_mgmt": (not unapproved, f"{len(unapproved)} non-standard changes implemented without full approval"),
        "asset_inventory": (dq >= 70, f"CMDB average data quality {dq} (threshold 70)"),
        "log_integrity": (chain, "Audit log hash chain valid" if chain else "Audit log hash chain BROKEN"),
    }

@router.post("/grc/controls/monitor")
def monitor_controls(db: Session = Depends(get_db), u=Depends(staff)):
    """Continuous control monitoring: controls with data.auto_check are evaluated against live platform evidence."""
    checks = _automated_checks(db, u); results = []
    for c in _recs(db, u, "control"):
        key = c.data.get("auto_check")
        if key in checks:
            ok, evidence = checks[key]; new = "effective" if ok else "ineffective"
            if c.state != new: c.state = new
            c.data = {**c.data, "evidence": evidence, "last_tested": now().isoformat(timespec="minutes")}
            results.append({"control": c.data.get("control_id"), "framework": c.data.get("framework"), "status": new, "evidence": evidence})
    audit.log(db, u.id, "control_monitoring", "grc", "batch", {"evaluated": len(results)}); db.commit()
    return results

@router.get("/grc/compliance")
def compliance(db: Session = Depends(get_db), u=Depends(staff)):
    ctrls, risks, audits, pols = _recs(db, u, "control"), _recs(db, u, "risk"), _recs(db, u, "audit_engagement"), _recs(db, u, "policy")
    fw = []
    for f in FRAMEWORKS:
        cs = [c for c in ctrls if c.data.get("framework") == f]; st = Counter(c.state for c in cs)
        fw.append({"framework": f, "controls": len(cs), "effective": st["effective"], "ineffective": st["ineffective"] + st["remediating"], "not_tested": st["not_tested"],
                   "compliance_pct": round(100 * st["effective"] / len(cs), 1) if cs else 0})
    heat = [[0] * 5 for _ in range(5)]
    for r in risks:
        if r.state == "closed": continue
        l, c = int(float(r.data.get("likelihood") or 3)), int(float(r.data.get("consequence") or 3)); heat[5 - max(1, min(5, l))][max(1, min(5, c)) - 1] += 1
    today = now().date().isoformat()
    return {"frameworks": fw, "risk_heatmap": heat, "top_risks": [out(r) for r in sorted(risks, key=lambda r: -r.data.get("risk_score", 0))[:6]],
            "open_findings": sum(int(float(a.data.get("findings") or 0)) for a in audits if a.state != "closed"),
            "policies_due_review": [out(p) for p in pols if (p.data.get("review_date") or "9") <= today]}

# ---------------- SPM / PPM ----------------
@router.get("/spm/portfolio")
def portfolio(db: Session = Depends(get_db), u=Depends(staff)):
    dem, prj = _recs(db, u, "demand"), _recs(db, u, "project")
    for r in dem + prj: hooks.compute(r)
    db.commit()
    num = lambda r, k: float(r.data.get(k) or 0)
    return {"demands": [out(d) for d in sorted(dem, key=lambda d: -d.data.get("priority_score", 0))],
            "projects": [out(p) for p in prj],
            "health": dict(Counter(p.data.get("health") for p in prj if p.state != "closed"))}

def parse_team(s):
    out_ = []
    for part in str(s or "").split(","):
        if ":" in part:
            who, pct = part.rsplit(":", 1)
            try: out_.append((who.strip(), float(pct.strip().rstrip("%"))))
            except ValueError: pass
    return out_

@router.get("/spm/resources")
def resources(db: Session = Depends(get_db), u=Depends(staff)):
    alloc = defaultdict(list)
    for p in _recs(db, u, "project"):
        if p.state in ("closed",): continue
        for who, pct in parse_team(p.data.get("team")): alloc[who].append({"project": p.number, "title": p.title, "pct": pct})
    return [{"person": k, "total_pct": sum(x["pct"] for x in v), "over_allocated": sum(x["pct"] for x in v) > 100, "assignments": v} for k, v in sorted(alloc.items())]

@router.post("/spm/demands/{did}/convert", status_code=201)
def convert_demand(did: int, db: Session = Depends(get_db), u=Depends(staff)):
    d = get_or_404(db, Record, did, u)
    if d.module != "demand" or d.state != "approved": raise HTTPException(400, "Only approved demands can be converted")
    from ..main import create_record_core
    p = create_record_core(db, u, "project", RecordCreate(title=d.title, description=d.description, data={"planned_pct": 0, "percent_complete": 0, "demand": d.number}))
    p.linked = [d]; d.data = {**d.data, "project": p.number}
    bus.emit(db, p, "project_created", u)  # PMO connector picks this up
    db.commit()
    return out(p)
