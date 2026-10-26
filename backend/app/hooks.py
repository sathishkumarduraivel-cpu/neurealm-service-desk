"""Computed fields per module (risk scores, data quality, compliance...)."""
from datetime import datetime
from .models import now

def _n(d, k, default=0.0):
    try: return float(d.get(k) or default)
    except (TypeError, ValueError): return default

def change(r):
    d = r.data; ctype = d.get("change_type", "normal")
    score = {"standard": 10, "normal": 35, "emergency": 60}.get(ctype, 35) + (4 - r.impact) * 8
    if d.get("affects_production", True): score += 10
    if not d.get("rollback_plan"): score += 15
    if not d.get("tested", False): score += 10
    if d.get("risk_answers"):
        from .routers.changeops import questionnaire_score
        score = questionnaire_score(d["risk_answers"])
    score = max(0, min(100, score))
    return {"risk_score": score, "risk_level": "high" if score >= 70 else "moderate" if score >= 40 else "low"}

CI_REQUIRED = {"server": ["ip", "os", "environment", "owner", "serial", "location", "criticality"],
               "application": ["environment", "owner", "criticality"], "database": ["ip", "environment", "owner", "criticality"],
               "network": ["ip", "serial", "location", "owner"], "laptop": ["serial", "owner", "os"], "cloud_service": ["environment", "owner"], "storage": ["serial", "location", "owner"]}

def ci(r):
    req = CI_REQUIRED.get(r.data.get("ci_class", "server"), CI_REQUIRED["server"]) + ["ci_class"]
    missing = [f for f in req if not r.data.get(f)]
    completeness = 1 - len(missing) / len(req)
    last = r.data.get("last_discovered"); stale = False
    if last:
        try: stale = (now() - datetime.fromisoformat(last[:19])).days > 90
        except ValueError: stale = True
    score = round(100 * completeness - (10 if not r.data.get("last_discovered") else 0) - (15 if stale else 0))
    return {"dq_score": max(0, score), "dq_missing": missing, "discovered": bool(last)}

def license(r):
    owned, used = _n(r.data, "seats_owned"), _n(r.data, "seats_used")
    status = "over_deployed" if used > owned else "under_utilized" if owned and used / owned < 0.7 else "compliant"
    spare = int(max(0, owned - used)) if status == "under_utilized" else 0
    r.data.pop("cost_per_seat", None); r.data.pop("potential_savings", None)
    return {"compliance": status, "utilization_pct": round(100 * used / owned, 1) if owned else 0, "reclaimable_seats": spare}

def vulnerability(r):
    cvss = _n(r.data, "cvss", 5)
    sev = "critical" if cvss >= 9 else "high" if cvss >= 7 else "medium" if cvss >= 4 else "low"
    r.priority = {"critical": "P1", "high": "P2", "medium": "P3", "low": "P4"}[sev]
    return {"severity": sev, "remediation_days": {"critical": 7, "high": 30, "medium": 90, "low": 180}[sev]}

def risk(r):
    s = int(_n(r.data, "likelihood", 3) * _n(r.data, "consequence", 3))
    lvl = "critical" if s >= 20 else "high" if s >= 12 else "medium" if s >= 6 else "low"
    r.priority = {"critical": "P1", "high": "P2", "medium": "P3", "low": "P4"}[lvl]
    return {"risk_score": s, "risk_level": lvl}

def demand(r):
    v, a, w = _n(r.data, "business_value", 5), _n(r.data, "strategic_alignment", 5), _n(r.data, "effort_weeks", 0)
    score = round(v * 6 + a * 4 - min(30, w * 0.5), 1)
    return {"priority_score": score, "recommendation": "approve" if score >= 60 else "review" if score >= 40 else "defer"}

def project(r):
    plan, pc = _n(r.data, "planned_pct", 0), _n(r.data, "percent_complete")
    gap = plan - pc  # schedule slip, in percentage points (no money involved)
    health = "red" if gap > 25 else "amber" if gap > 10 else "green"
    return {"schedule_gap": round(gap, 1), "health": health}

def reservation(r):
    return {}

# No prices or money anywhere: these keys are dropped from record data.
MONEY_KEYS = ("cost", "value", "cost_estimate", "budget", "spent", "burn_pct", "price", "amount", "cost_per_seat", "potential_savings")
def scrub_money(r):
    if r.module in ("asset", "contract", "demand", "project", "license") and isinstance(r.data, dict) and any(k in r.data for k in MONEY_KEYS):
        r.data = {k: v for k, v in r.data.items() if k not in MONEY_KEYS}

HOOKS = {"change": change, "ci": ci, "license": license, "vulnerability": vulnerability, "risk": risk, "demand": demand, "project": project, "reservation": reservation}

def compute(r):
    from .registry import MODULES
    scrub_money(r)
    h = MODULES[r.module].get("compute")
    if h: r.data = {**(r.data or {}), **HOOKS[h](r)}
    scrub_money(r)
