"""Seed data for phases B–E (called from seed.run)."""
import random
from datetime import timedelta
from sqlalchemy import select
from .models import *
from . import hooks, settings_store

def rec(db, module, number, title, state, data, u, t0, **kw):
    r = Record(tenant_id=1, module=module, number=number, title=title, state=state, data=data, requester_id=u.id, created_at=kw.pop("created_at", t0),
               impact=kw.pop("impact", 3), urgency=kw.pop("urgency", 3), priority=kw.pop("priority", "P4"), category=kw.pop("category", "general"), ai_suggestion={}, **kw)
    hooks.compute(r); db.add(r); return r

def seq(prefix, i): return f"{prefix}{1001 + i:07d}"

def phase_b(db, users, g, t0):
    a = users["admin@neurealm.com"]; disc = (t0 - timedelta(days=2)).isoformat()
    cis = [("ERP Application", "application", {"environment": "production", "owner": "Finance IT", "criticality": "high"}),
           ("erp-app-01", "server", {"ip": "10.10.1.11", "os": "RHEL 9", "environment": "production", "owner": "Infra", "serial": "SRV-1001", "location": "Chennai DC1", "criticality": "high"}),
           ("erp-db-01", "database", {"ip": "10.10.1.21", "environment": "production", "owner": "DBA", "criticality": "high"}),
           ("core-sw-01", "network", {"ip": "10.10.0.1", "serial": "NW-77812", "location": "Chennai DC1", "owner": "Network Ops"}),
           ("vpn-gw-01", "network", {"ip": "10.10.0.5", "serial": "NW-77820", "location": "Chennai DC1", "owner": "Network Ops"}),
           ("Email (M365)", "cloud_service", {"environment": "production", "owner": "Collab"}),
           ("hr-portal-01", "server", {"ip": "10.10.2.31", "os": "Ubuntu 22.04", "environment": "production", "owner": "HR IT"}),
           ("san-01", "storage", {"serial": "ST-0091", "location": "Chennai DC1"}),
           ("LAP-MEENA-01", "laptop", {"serial": "5CG1234XYZ", "owner": "user@neurealm.com", "os": "Windows 11"}),
           ("build-srv-02", "server", {"ip": "10.10.3.40", "environment": "development"})]
    objs = {}
    for i, (n, cls, d) in enumerate(cis):
        objs[n] = rec(db, "ci", seq("CI", i), n, "operational", {"ci_class": cls, **d, **({"last_discovered": disc} if i % 4 else {})}, a, t0 - timedelta(days=30), category="cmdb")
    db.flush()
    for p, c, t in [("ERP Application", "erp-app-01", "runs_on"), ("ERP Application", "erp-db-01", "depends_on"), ("erp-app-01", "core-sw-01", "connects_to"),
                    ("erp-db-01", "core-sw-01", "connects_to"), ("erp-db-01", "san-01", "depends_on"), ("vpn-gw-01", "core-sw-01", "connects_to"), ("hr-portal-01", "core-sw-01", "connects_to")]:
        db.add(CIRelation(tenant_id=1, parent_id=objs[p].id, child_id=objs[c].id, rel_type=t))
    assets = [("Dell Latitude 7450 - Meena", "hardware", "in_use", 145000, "2025-11-30"), ("MacBook Pro 14 - Arun", "hardware", "in_use", 210000, "2027-03-01"),
              ("Lenovo T14 - spare", "hardware", "in_stock", 98000, "2026-12-01"), ("HP LaserJet M507 - 3F", "hardware", "in_repair", 62000, "2026-11-15"),
              ("Dell U2723QE Monitor", "hardware", "in_use", 48000, "2028-01-01"), ("Cisco Catalyst 9300", "hardware", "in_use", 640000, "2027-06-30"),
              ("Adobe Acrobat Pro - Finance", "software", "in_use", 24000, ""), ("Old ThinkPad X1 (2019)", "hardware", "retired", 0, "2022-01-01")]
    for i, (n, t, st, cost, w) in enumerate(assets):
        rec(db, "asset", seq("AST", i), n, st, {"asset_type": t, "model": n.split(" - ")[0], "serial": f"AS{i:05d}", "warranty_end": w, "purchase_date": "2024-04-01"}, a, t0)
    for i, (n, v, o, us, c, r) in enumerate([("Microsoft 365 E3", "Microsoft", 250, 231, 23000, "2027-03-31"), ("Atlassian Jira Cloud", "Atlassian", 120, 64, 9000, "2026-12-15"),
                                            ("Adobe Creative Cloud", "Adobe", 20, 26, 60000, "2027-01-31"), ("Zoom Business", "Zoom", 80, 31, 13000, "2026-11-30"), ("Slack Pro", "Salesforce", 150, 142, 7000, "2027-05-01")]):
        rec(db, "license", seq("LIC", i), n, "active", {"product": n, "vendor": v, "seats_owned": o, "seats_used": us, "renewal_date": r}, a, t0)
    for i, (n, v, ty, val, s, e, st) in enumerate([("Dell ProSupport", "Dell", "support", 1800000, "2024-01-01", "2026-12-10", "active"), ("Airtel MPLS", "Airtel", "service", 2400000, "2025-04-01", "2027-03-31", "active"),
                                                 ("Microsoft EA", "Microsoft", "license", 6900000, "2024-04-01", "2027-03-31", "active"), ("Facility AMC - HVAC", "Blue Star", "maintenance", 450000, "2025-11-01", "2026-11-05", "active")]):
        rec(db, "contract", seq("CTR", i), n, st, {"vendor": v, "contract_type": ty, "start_date": s, "end_date": e}, a, t0)
    months = [(t0.replace(day=1) - timedelta(days=31 * k)).strftime("%Y-%m") for k in range(5, -1, -1)]
    random.seed(7)
    svc = [("AWS", "EC2", "cloud", 420000, 0.62), ("AWS", "S3", "cloud", 85000, 0.9), ("AWS", "RDS", "cloud", 160000, 0.55), ("Azure", "Virtual Machines", "cloud", 260000, 0.28),
           ("Azure", "AKS", "cloud", 140000, 0.7), ("GCP", "BigQuery", "cloud", 70000, 0.8), ("SaaS", "Microsoft 365", "saas", 479000, 0.92), ("SaaS", "Zoom", "saas", 86000, 0.39), ("SaaS", "Jira", "saas", 90000, 0.53)]
    for mi, m in enumerate(months):
        for p, s, k, base, ut in svc:
            amt = base * random.uniform(0.93, 1.07)
            if (p, s) == ("AWS", "EC2") and mi == len(months) - 1: amt = base * 1.85  # anomaly
            if (p, s) == ("GCP", "BigQuery") and mi == len(months) - 1: amt = base * 1.6
            db.add(CostRecord(tenant_id=1, provider=p, service=s, kind=k, month=m, amount=round(amt), utilization=ut))
    db.flush()
    return objs

def phase_c(db, users, g, t0):
    a = users["admin@neurealm.com"]; cu = users["user@neurealm.com"]; agent = users["agent@neurealm.com"]
    accts = [("Chola Finance Ltd", "BFSI", "platinum", "South"), ("Sundaram Motors", "Manufacturing", "gold", "South"), ("Nila Retail", "Retail", "silver", "West")]
    for i, (n, ind, tier, reg) in enumerate(accts):
        rec(db, "account", seq("ACC", i), n, "active", {"industry": ind, "tier": tier, "region": reg, "website": n.split()[0].lower() + ".example"}, a, t0)
    for i, (n, acc, e) in enumerate([("Ravi Shankar", 0, "ravi@chola.example"), ("Lakshmi Narayanan", 0, "lakshmi@chola.example"), ("Gopal Krishnan", 1, "gopal@sundaram.example"), ("Fatima Sheikh", 2, "fatima@nila.example")]):
        rec(db, "contact", seq("CON", i), n, "active", {"account": seq("ACC", acc), "email": e, "phone": "+91 98400 0000" + str(i), "job_title": "IT Manager"}, a, t0)
    for i, (acc, tier, hrs, used) in enumerate([(0, "24x7", 500, 312), (1, "business_hours", 200, 188)]):
        rec(db, "entitlement", seq("ENT", i), f"{accts[acc][0]} — {tier} support", "active", {"account": seq("ACC", acc), "sla_tier": tier, "support_hours": hrs, "used_hours": used, "end_date": "2027-03-31"}, a, t0)
    cs = [("Payment gateway timeout on Chatbot bot", 0, "in_progress", "P2"), ("WhatsApp channel not delivering messages", 0, "new", "P2"), ("Request: add Tamil language to IVR", 1, "awaiting_customer", "P3"),
          ("Dashboard export failing", 2, "resolved", "P3"), ("SSO login loop for store managers", 2, "in_progress", "P3")]
    for i, (t, acc, st, p) in enumerate(cs):
        r = rec(db, "case", seq("CS", i), t, st, {"account": seq("ACC", acc), "contact": "", "product": "Chatbot", "channel": ["portal", "email", "whatsapp"][i % 3], "entitled": acc < 2},
                cu if i % 2 == 0 else users["user2@neurealm.com"], t0 - timedelta(days=i), priority=p, assignment_group_id=g["Customer Support"].id, assignee_id=agent.id if st != "new" else None)
        sla_apply(db, r)
    hr = [("Payslip discrepancy for September", "payroll", "in_progress"), ("Maternity leave policy query", "leave", "new"), ("Address proof letter", "documents", "resolved")]
    for i, (t, c, st) in enumerate(hr):
        r = rec(db, "hr_case", seq("HRC", i), t, st, {"hr_category": c, "employee": cu.full_name, "confidential": c == "payroll"}, cu, t0 - timedelta(days=i), assignment_group_id=g["HR Services"].id); sla_apply(db, r)
    ob = rec(db, "hr_case", seq("HRC", 3), "Onboarding: Kavya Ramesh", "in_progress", {"hr_category": "onboarding", "employee": "Kavya Ramesh", "lifecycle": "onboarding", "date": (t0 + timedelta(days=7)).date().isoformat()}, a, t0, assignment_group_id=g["HR Services"].id)
    db.flush()
    for i, (t, grp) in enumerate([("Create AD / M365 account", "Service Desk"), ("Provision laptop", "Desktop Support"), ("Grant VPN & app access", "Network Ops"), ("Allocate desk & ID badge", "Facilities"), ("Collect documents & sign policies", "HR Services")]):
        rec(db, "task", seq("TSK", i), f"{t} — Kavya Ramesh", "done" if i < 2 else "open", {"parent_number": ob.number}, a, t0, parent_id=ob.id, assignment_group_id=g[grp].id)
    for i, (t, b, fl, ty, st) in enumerate([("AC not cooling in Board Room", "Chennai HQ", "3", "hvac", "assigned"), ("Flickering lights near pantry", "Chennai HQ", "2", "electrical", "new"), ("Chair replacement", "Bengaluru", "1", "furniture", "completed")]):
        r = rec(db, "facility_request", seq("FAC", i), t, st, {"building": b, "floor": fl, "facility_type": ty}, cu, t0 - timedelta(days=i), assignment_group_id=g["Facilities"].id); sla_apply(db, r)
    d = t0.date().isoformat()
    for i, (sp, s, e, n, who) in enumerate([("Board Room", "10:00", "11:00", "QBR with Chola Finance", a), ("Huddle 1", "11:30", "12:00", "Standup", agent), ("Training Hall", "14:00", "17:00", "Neurealm Service Desk agent training", a), ("Desk A-12", "09:00", "18:00", "Hot desk", cu)]):
        rec(db, "reservation", seq("RSV", i), n, "confirmed", {"space": sp, "start": f"{d}T{s}", "end": f"{d}T{e}", "attendees": 8 if sp != "Desk A-12" else 1}, who, t0)
    for i, (n, c, h, st) in enumerate([("Rajesh Iyer", "Chola Finance", "Priya Raman", "checked_in"), ("Emily Carter", "Okta", "Arun Kumar", "expected"), ("Sanjay Gupta", "Dell", "Divya Srinivasan", "expected")]):
        rec(db, "visitor", seq("VIS", i), f"{n} ({c})", st, {"visitor_name": n, "company": c, "host": h, "visit_date": d, "nda_signed": st == "checked_in"}, a, t0)
    t1, t2 = users["tech1@neurealm.com"], users["tech2@neurealm.com"]
    for i, (t, cust, sk, st, tech, pr) in enumerate([("Install CCTV cameras - Ambattur branch", "Chola Finance - Ambattur", "cctv", "scheduled", t1, "P3"), ("Replace switch in server room", "Sundaram Motors - Hosur", "network", "dispatched", t1, "P2"),
                                                    ("Printer fuser replacement", "Nila Retail - T Nagar", "printer", "new", None, "P3"), ("UPS electrical check", "Chennai HQ", "electrical", "new", None, "P2"), ("Laptop motherboard swap", "Chennai HQ", "hardware", "new", None, "P4")]):
        start = (t0 + timedelta(days=1)).replace(hour=10 + i, minute=0, second=0, microsecond=0).isoformat(timespec="minutes") if tech else ""
        r = rec(db, "work_order", seq("WO", i), t, st, {"customer": cust, "location": cust.split(" - ")[-1], "skill": sk, "duration_h": 2, "scheduled_start": start, "technician": tech.full_name if tech else ""},
                a, t0 - timedelta(hours=i), priority=pr, assignee_id=tech.id if tech else None, assignment_group_id=g["Field Services"].id); sla_apply(db, r)

def sla_apply(db, r):
    from . import sla as _s
    _s.apply_sla(db, r)

def phase_d(db, users, g, t0):
    a = users["admin@neurealm.com"]
    for i, (t, vec, st, tac, ci, p, age) in enumerate([("Phishing campaign targeting finance team", "phishing", "contain", "Initial Access", "Email (M365)", "P2", 2),
                                                       ("Ransomware beacon detected on file server", "ransomware", "analysis", "Command and Control", "san-01", "P1", 1),
                                                       ("Impossible-travel sign-in for admin account", "credential_theft", "new", "Credential Access", "", "P2", 0),
                                                       ("Malware on LAP-MEENA-01", "malware", "closed", "Execution", "LAP-MEENA-01", "P3", 9)]):
        r = rec(db, "sec_incident", seq("SIR", i), t, st, {"attack_vector": vec, "mitre_tactic": tac, "affected_ci": ci, "source_ip": f"185.220.10.{i + 4}"}, a, t0 - timedelta(days=age), priority=p, category="security", assignment_group_id=g["Security Ops"].id)
        sla_apply(db, r)
    for i, (cve, cvss, ci, pa, st, age) in enumerate([("CVE-2024-3400", 10.0, "vpn-gw-01", True, "remediating", 12), ("CVE-2023-4966", 9.4, "core-sw-01", True, "open", 3), ("CVE-2024-21413", 9.8, "Email (M365)", True, "resolved", 20),
                                                     ("CVE-2023-38545", 7.5, "erp-app-01", True, "triaged", 40), ("CVE-2024-6387", 8.1, "hr-portal-01", True, "open", 5), ("CVE-2022-0778", 5.9, "build-srv-02", False, "open", 100), ("CVE-2021-44228", 10.0, "erp-app-01", True, "resolved", 300)]):
        rec(db, "vulnerability", seq("VUL", i), f"{cve} on {ci}", st, {"cve": cve, "cvss": cvss, "affected_ci": ci, "patch_available": pa, "scanner": "qualys"}, a, t0 - timedelta(days=age), category="security")
    pols = [("Information Security Policy", "ISO27001", "published", "3.1", "2027-01-15"), ("Acceptable Use Policy", "Internal", "published", "2.0", "2026-10-01"), ("Data Protection & Privacy Policy", "GDPR", "review", "1.4", "2026-12-31"), ("Access Control Policy", "SOC2", "published", "1.2", "2027-04-01")]
    for i, (t, f, st, v, rd) in enumerate(pols):
        rec(db, "policy", seq("POL", i), t, st, {"framework": f, "version": v, "owner": "CISO", "review_date": rd}, a, t0)
    risks = [("Ransomware disrupts ERP operations", 3, 5, "mitigate", "treating"), ("Third-party SaaS data breach", 3, 4, "transfer", "assessed"), ("Key-person dependency in DBA team", 4, 3, "mitigate", "treating"),
             ("Non-compliance with DPDP Act 2023", 2, 5, "mitigate", "assessed"), ("Data-centre power outage", 2, 4, "mitigate", "monitored"), ("Shadow IT SaaS adoption", 4, 2, "accept", "accepted")]
    for i, (t, l, c, tr, st) in enumerate(risks):
        rec(db, "risk", seq("RSK", i), t, st, {"likelihood": l, "consequence": c, "treatment": tr, "owner": "Priya Raman", "framework": "ISO27001"}, a, t0, category="grc")
    ctrls = [("ISO27001", "A.8.8", "Management of technical vulnerabilities", "vuln_mgmt"), ("ISO27001", "A.5.9", "Inventory of information assets", "asset_inventory"), ("ISO27001", "A.8.15", "Logging", "log_integrity"),
             ("ISO27001", "A.5.24", "Incident management planning", "incident_response"), ("ISO27001", "A.8.32", "Change management", "change_mgmt"), ("ISO27001", "A.5.15", "Access control", None),
             ("SOC2", "CC7.1", "Vulnerability detection & monitoring", "vuln_mgmt"), ("SOC2", "CC7.3", "Security incident evaluation", "incident_response"), ("SOC2", "CC8.1", "Change management", "change_mgmt"), ("SOC2", "CC6.1", "Logical access", None),
             ("GDPR", "Art.30", "Records of processing", None), ("GDPR", "Art.32", "Security of processing (integrity)", "log_integrity"), ("GDPR", "Art.33", "Breach notification within 72h", "incident_response")]
    for i, (f, cid, t, ac) in enumerate(ctrls):
        rec(db, "control", seq("CTL", i), f"{cid} {t}", "effective" if ac is None and i % 2 else "not_tested", {"framework": f, "control_id": cid, "owner": "GRC", **({"auto_check": ac} if ac else {})}, a, t0, category="grc")
    for i, (t, f, st, fi) in enumerate([("ISO 27001 surveillance audit 2026", "ISO27001", "fieldwork", 3), ("SOC 2 Type II FY26", "SOC2", "planned", 0), ("GDPR / DPDP readiness review", "GDPR", "reporting", 5)]):
        rec(db, "audit_engagement", seq("AUD", i), t, st, {"framework": f, "auditor": "BSI" if f == "ISO27001" else "Deloitte", "scope": "Neurealm Chennai operations", "findings": fi}, a, t0)
    for i, (t, v, al, c, st) in enumerate([("WhatsApp self-service for HR queries", 8, 9, 1500000, "screening"), ("Migrate legacy ticketing to Neurealm Service Desk", 9, 10, 4000000, "approved"),
                                           ("Data lake for FinOps analytics", 6, 6, 9000000, "submitted"), ("Office relocation to OMR", 4, 3, 25000000, "submitted")]):
        rec(db, "demand", seq("DMD", i), t, st, {"business_value": v, "strategic_alignment": al, "effort_weeks": c // 250000}, a, t0)
    for i, (t, pm, b, sp, pc, st, team) in enumerate([("Neurealm Service Desk rollout - Phase 2", "Rahul Menon", 6000000, 3100000, 55, "executing", "rahul@neurealm.com:60, arun@neurealm.com:50, divya@neurealm.com:40"),
                                                      ("Chatbot Tamil voice bot", "Divya Srinivasan", 2500000, 2300000, 60, "executing", "divya@neurealm.com:50, rahul@neurealm.com:30"),
                                                      ("SOC 2 readiness", "Priya Raman", 1800000, 400000, 30, "planning", "priya@neurealm.com:40, arun@neurealm.com:20"),
                                                      ("Network refresh Chennai DC", "Divya Srinivasan", 9000000, 9500000, 85, "closing", "divya@neurealm.com:30")]):
        rec(db, "project", seq("PRJ", i), t, st, {"pm": pm, "planned_pct": round(pc * sp / b) if b else pc, "percent_complete": pc, "start_date": "2026-06-01", "end_date": "2027-03-31", "team": team}, a, t0)

def phase_e(db, users, g, t0):
    a = users["admin@neurealm.com"]
    random.seed(11)
    for i, (h, u_, o) in enumerate([("LAP-MEENA-01", "user@neurealm.com", "Windows 11"), ("LAP-VIKRAM-02", "user2@neurealm.com", "Windows 11"), ("LAP-ARUN-03", "agent@neurealm.com", "macOS 15"),
                                    ("LAP-DIVYA-04", "netops@neurealm.com", "Windows 11"), ("LAP-RAHUL-05", "appsupport@neurealm.com", "Windows 10"), ("LAP-PRIYA-06", "admin@neurealm.com", "macOS 15"),
                                    ("LAP-FIN-07", "finance1@neurealm.com", "Windows 11"), ("LAP-FIN-08", "finance2@neurealm.com", "Windows 10"), ("LAP-HR-09", "hr1@neurealm.com", "Windows 11"), ("LAP-SALES-10", "sales1@neurealm.com", "Windows 11")]):
        bad = i in (1, 4, 7)
        db.add(DexDevice(tenant_id=1, hostname=h, user_email=u_, os=o, boot_seconds=random.uniform(70, 110) if bad else random.uniform(18, 45), crashes_7d=random.randint(3, 6) if bad else random.randint(0, 1),
                         cpu_pct=random.uniform(55, 80) if bad else random.uniform(15, 45), mem_pct=random.uniform(86, 95) if bad else random.uniform(40, 70),
                         disk_free_pct=random.uniform(4, 12) if bad else random.uniform(25, 60), sentiment=random.uniform(1.8, 2.8) if bad else random.uniform(3.6, 4.9)))
    for i, (n, o, env) in enumerate([("LAP-VIKRAM-02", "Windows 11", None), ("LAP-RAHUL-05", "Windows 10", None), ("LAP-FIN-07", "Windows 11", None)]):
        rec(db, "ci", seq("CI", 10 + i), n, "operational", {"ci_class": "laptop", "os": o, "serial": f"5CG{i}ABC", "owner": "user"}, a, t0, category="cmdb")
    rec(db, "patch_job", seq("PAT", 0), "October Patch Tuesday — Windows endpoints", "draft", {"os": "Windows", "environment": "production", "patches": "KB5044284, KB5044285", "window": (t0 + timedelta(days=2)).isoformat(timespec="minutes")}, a, t0)
    rec(db, "patch_job", seq("PAT", 1), "OpenSSH CVE-2024-6387 — Linux servers", "draft", {"os": "Linux", "environment": "production", "patches": "openssh-9.8p1", "window": (t0 + timedelta(days=1)).isoformat(timespec="minutes")}, a, t0)
    wf_nodes = [{"id": "t", "type": "trigger", "position": {"x": 0, "y": 80}, "data": {"label": "Incident created", "module": "incident", "event": "created"}},
                {"id": "c1", "type": "condition", "position": {"x": 260, "y": 80}, "data": {"label": "Priority is P1?", "field": "priority", "op": "eq", "value": "P1"}},
                {"id": "a1", "type": "action", "position": {"x": 540, "y": 0}, "data": {"label": "Notify CAB / major incident team", "action": "notify_group", "group": "CAB", "text": "Major incident raised"}},
                {"id": "a2", "type": "action", "position": {"x": 540, "y": 110}, "data": {"label": "Add major-incident note", "action": "add_comment", "text": "Major incident process initiated: bridge call opened.", "internal": True}},
                {"id": "c2", "type": "condition", "position": {"x": 540, "y": 230}, "data": {"label": "Category is security?", "field": "category", "op": "eq", "value": "security"}},
                {"id": "a3", "type": "action", "position": {"x": 820, "y": 230}, "data": {"label": "Route to Security Ops", "action": "assign_group", "group": "Security Ops"}}]
    wf_edges = [{"id": "e1", "source": "t", "target": "c1"}, {"id": "e2", "source": "c1", "target": "a1", "sourceHandle": "true"}, {"id": "e3", "source": "c1", "target": "a2", "sourceHandle": "true"},
                {"id": "e4", "source": "c1", "target": "c2", "sourceHandle": "false"}, {"id": "e5", "source": "c2", "target": "a3", "sourceHandle": "true"}]
    db.add(WorkflowDef(tenant_id=1, name="Major incident & security routing", module="incident", trigger="created", nodes=wf_nodes, edges=wf_edges, active=True))
    db.add(WorkflowDef(tenant_id=1, name="Remote workers: notify on state change", module="incident", modules=["incident", "request"], trigger="state_changed", trigger_cfg={},
        nodes=[{"id": "t", "type": "trigger", "position": {"x": 0, "y": 100}, "data": {"label": "State changes (Incidents, Requests)"}},
               {"id": "c", "type": "condition", "position": {"x": 240, "y": 100}, "data": {"label": "Office site is Remote", "field": "site", "op": "eq", "value": "Remote"}},
               {"id": "n", "type": "action", "position": {"x": 500, "y": 40}, "data": {"label": "Tell the requester", "action": "notify", "to": "requester", "text": "{number} is now {state}. We'll keep you posted."}},
               {"id": "a", "type": "action", "position": {"x": 500, "y": 180}, "data": {"label": "Note for the desk", "action": "add_comment", "text": "On-site follow-up may be needed."}}],
        edges=[{"source": "t", "target": "c"}, {"source": "c", "target": "n", "sourceHandle": "true"}, {"source": "c", "target": "a", "sourceHandle": "false"}], active=True))
    for kind, name, cfg in [("teams", "Teams — #it-major-incidents", {"events": ["created"], "modules": ["incident", "sec_incident"], "min_priority": "P2"}),
                            ("slack", "Slack — #service-desk", {"events": ["created", "updated"], "modules": ["incident"]}),
                            ("chatbot", "Chatbot omnichannel bot", {"events": ["updated"], "modules": ["incident", "case"]}),
                            ("sla_assist", "SLA Assist SLA engine", {"events": ["created"], "modules": ["incident", "case"]}),
                            ("pmo", "PMO portfolio sync", {"events": ["project_created", "updated"], "modules": ["project", "demand"]}),
                            ("quality_audit", "Quality audit quality auditor", {"events": ["updated"], "modules": ["incident"]}),
                            ("workflow_hub", "Workflow connector flows", {"events": ["created"], "modules": ["request"]}),
                            ("jira", "Jira — OPS project", {"events": [], "modules": ["incident"]}),
                            ("servicenow", "ServiceNow migration", {})]:
        db.add(Connector(tenant_id=1, kind=kind, name=name, config=cfg, enabled=True, secret=f"demo-{kind}-secret"))
    db.flush()
    from . import autoresolve
    for r in db.scalars(select(Record).where(Record.tenant_id == 1, Record.module == "incident", Record.state == "new")).all():
        autoresolve.run(db, r, a)

def phase_f(db, users, g, t0):
    """Phase 4 demo: multi-step approvals, fulfilment tasks, entitlements, CSAT ratings, KB feedback."""
    db.flush()
    lead = next((u for u in users.values() if u.role == "agent"), None)
    for it in db.scalars(select(CatalogItem)):
        n = it.name.lower()
        if "laptop" in n:
            it.approval_stages = [{"name": "Team lead", "approver": f"user:{lead.id}" if lead else "admin"}, {"name": "IT approval", "approver": "admin"}]
            it.fulfilment_tasks = ["Reserve device from stock", "Image and enrol device", "Hand over to employee"]
        elif it.requires_approval:
            it.approval_stages = [{"name": "Approval", "approver": "admin"}]; it.fulfilment_tasks = ["Set up access", "Confirm with requester"]
        else:
            it.fulfilment_tasks = ["Complete request"]
    comments = ["Quick and friendly, thank you!", "Sorted in no time.", "Took a while but it works now.", "", "Great help from the desk."]
    done = [r for r in db.scalars(select(Record).where(Record.state.in_(["resolved", "closed", "fulfilled"]))) if r.requester_id][:14]
    for i, r in enumerate(done):
        r.data = {**(r.data or {}), "csat": {"score": [5, 4, 5, 3, 4, 5, 2][i % 7], "comment": comments[i % 5], "at": t0.isoformat()}}
    for i, a in enumerate(db.scalars(select(KBArticle))):
        a.helpful = random.randint(3, 40); a.not_helpful = random.randint(0, 6) + (8 if i == 2 else 0)

def phase_g(db, users, g, t0):
    """Phase 5 demo: change calendar, freeze window, CAB meeting, PIRs, a major incident with updates."""
    from . import settings_store
    db.flush(); tid = 1
    base = t0.replace(hour=22, minute=0, second=0, microsecond=0, tzinfo=None)
    fz = base + timedelta(days=40)
    settings_store.put(db, tid, "change.freeze", {"v": [{"name": "Year-end close", "start": fz.isoformat(), "end": (fz + timedelta(days=7)).isoformat(), "reason": "Finance close: please keep systems steady."}]})
    chs = db.scalars(select(Record).where(Record.module == "change").order_by(Record.id)).all()
    for i, c in enumerate(chs):
        st = base + timedelta(days=(i % 12) - 3)
        c.data = {**c.data, "planned_start": st.isoformat(timespec="minutes"), "planned_end": (st + timedelta(hours=2)).isoformat(timespec="minutes")}
        if c.state == "closed": c.data["pir"] = {"successful": i % 4 != 1, "notes": "Completed in the window." if i % 4 else "Rolled back once, second try worked.", "lessons": "", "by": "Priya Raman", "at": t0.isoformat()}
    settings_store.put(db, tid, "cab.meetings", {"v": [{"id": 1, "title": "Weekly CAB", "date": (base - timedelta(days=7)).isoformat(timespec="minutes"), "change_ids": [c.id for c in chs[:3]], "minutes": "All three approved. Firewall change moved to Saturday night.", "decisions": {}}]})
    inc = db.scalars(select(Record).where(Record.module == "incident", Record.state.in_(["in_progress", "new"])).order_by(Record.id)).first()
    if inc:
        inc.priority = "P1"
        inc.data = {**inc.data, "major": True, "major_at": (t0 - timedelta(hours=2)).isoformat(), "bridge": "Teams bridge: #it-major-incidents",
                    "comms": [{"at": (t0 - timedelta(hours=2)).isoformat(), "by": "Priya Raman", "audience": "everyone", "message": "We know about this and the team is on it."},
                              {"at": (t0 - timedelta(hours=1)).isoformat(), "by": "Priya Raman", "audience": "leadership", "message": "Cause found, fix rolling out. Next update in 30 minutes."}]}

def phase_h(db, users, g, t0):
    """Phase 6 demo: purchase orders at different stages."""
    a = users["admin@neurealm.com"]
    for i, (t, v, it, q, st) in enumerate([("Laptops for October joiners", "Dell", "Latitude 7450", 6, "ordered"), ("Meeting room screens", "LG", "55in display", 2, "approved"),
                                          ("Spare docking stations", "Lenovo", "ThinkPad dock", 10, "received"), ("Firewall support renewal", "Fortinet", "Support subscription", 1, "submitted")]):
        rec(db, "purchase_order", seq("PO", i), t, st, {"vendor": v, "item": it, "quantity": q, "received": q if st == "received" else 0, "expected_date": (t0 + timedelta(days=7 + i * 5)).date().isoformat()}, a, t0)
    for r, ci in zip(db.scalars(select(Record).where(Record.module == "incident", Record.state.in_(["new", "in_progress"])).order_by(Record.id.desc())).all()[:3], ["erp-db-01", "erp-db-01", "vpn-gw-01"]):
        r.data = {**r.data, "ci": ci}

def phase_i(db, users, g, t0):
    """Phase 8: a few saved reports from templates and a 'Service desk overview' board."""
    from .routers.analytics import TEMPLATES
    a = users["admin@neurealm.com"]; reps = []
    for i, t in enumerate(TEMPLATES[:5]):
        spec = {"days": 30, "cols": None, "metric": "count", "filter": {}, "chart": "bar", "rows": "priority", **t["spec"]}
        reps.append({"id": f"seed{i}", "name": t["name"], "spec": spec, "shared": True, "owner": a.id, "owner_name": a.full_name, "created": t0.isoformat()[:16]})
    settings_store.put(db, 1, "analytics.reports", {"v": reps})
    settings_store.put(db, 1, "analytics.boards", {"v": [{"id": "seedboard", "name": "Service desk overview", "shared": True, "owner": a.id, "owner_name": a.full_name,
                                                          "widgets": [{"report": r["id"], "size": "full" if i == 1 else "half"} for i, r in enumerate(reps)]}]})
