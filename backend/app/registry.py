"""Module registry: every BRD module is a configuration over the generic Record + workflow engine.

Each module defines: label, number prefix, nav section, state machine, initial state, typed data fields,
who may create it, whether AI triage / SLA apply, and an optional compute hook (see hooks.py).
"""
F = lambda name, label, type="text", options=None, **kw: {"name": name, "label": label, "type": type, **({"options": options} if options else {}), **kw}

def linear(*states, extra=None):
    """Linear flow s0 -> s1 -> ... with optional cancel from non-terminal states."""
    flow = {s: [states[i + 1]] if i + 1 < len(states) else [] for i, s in enumerate(states)}
    for k, v in (extra or {}).items(): flow.setdefault(k, []); flow[k] = flow[k] + v
    return flow

STAFF, ALL = ("admin", "agent"), ("admin", "agent", "end_user")

MODULES = {
    # ---------- ITSM ----------
    "incident": dict(label="Incidents", prefix="INC", section="ITSM", ai=True, sla=True, create=ALL,
        flow={"new": ["in_progress", "cancelled"], "in_progress": ["on_hold", "resolved"], "on_hold": ["in_progress"],
              "resolved": ["closed", "in_progress"], "closed": [], "cancelled": []}, fields=[F("resolution_notes", "Resolution notes", "textarea")]),
    "problem": dict(label="Problems", prefix="PRB", section="ITSM", create=STAFF,
        flow={"new": ["assessment"], "assessment": ["root_cause_analysis", "cancelled"], "root_cause_analysis": ["fix_in_progress", "known_error"],
              "known_error": ["fix_in_progress", "resolved"], "fix_in_progress": ["resolved"], "resolved": ["closed"], "closed": [], "cancelled": []},
        fields=[F("root_cause", "Root cause", "textarea"), F("workaround", "Workaround", "textarea")]),
    "change": dict(label="Changes", prefix="CHG", section="ITSM", create=STAFF, compute="change",
        flow={"new": ["assess", "cancelled"], "assess": ["authorize", "cancelled"], "authorize": [], "scheduled": ["implement"],
              "implement": ["review"], "review": ["closed"], "closed": [], "cancelled": [], "rejected": []},
        fields=[F("change_type", "Change type", "select", ["standard", "normal", "emergency"]), F("rollback_plan", "Rollback plan"),
                F("tested", "Tested", "bool"), F("planned_start", "Planned start", "datetime-local"), F("planned_end", "Planned end", "datetime-local")]),
    "request": dict(label="Requests", prefix="REQ", section="ITSM", create=(), sla=True,
        flow={"pending_approval": [], "approved": ["in_progress"], "in_progress": ["fulfilled"], "fulfilled": ["closed"], "closed": [], "rejected": [], "cancelled": []}, initial="pending_approval", fields=[]),
    "task": dict(label="Tasks", prefix="TSK", section="ITSM", create=STAFF, hidden=True,
        flow=linear("open", "in_progress", "done", extra={"open": ["cancelled"]}), fields=[F("parent_number", "Parent")]),
    # ---------- ITOM / ITAM ----------
    "ci": dict(label="CMDB", prefix="CI", section="ITOM", create=STAFF, compute="ci", custom_page="/cmdb",
        flow={"planned": ["operational"], "operational": ["maintenance", "retired"], "maintenance": ["operational", "retired"], "retired": []}, initial="operational",
        fields=[F("ci_class", "Class", "select", ["server", "application", "database", "network", "laptop", "cloud_service", "storage"]), F("ip", "IP address"),
                F("os", "OS"), F("environment", "Environment", "select", ["production", "staging", "development"]), F("owner", "Owner"),
                F("serial", "Serial"), F("location", "Location"), F("criticality", "Criticality", "select", ["high", "medium", "low"])]),
    "asset": dict(label="Assets", prefix="AST", section="ITAM", create=STAFF,
        flow={"on_order": ["in_stock"], "in_stock": ["in_use", "retired"], "in_use": ["in_repair", "in_stock", "retired"], "in_repair": ["in_use", "retired"], "retired": []}, initial="in_stock",
        fields=[F("asset_type", "Type", "select", ["hardware", "software"]), F("model", "Model"), F("serial", "Serial"), F("purchase_date", "Purchase date", "date"), F("warranty_end", "Warranty end", "date"), F("assigned_to", "Assigned to")]),
    "license": dict(label="Licenses", prefix="LIC", section="ITAM", create=STAFF, compute="license",
        flow={"active": ["expired"], "expired": ["active"]}, initial="active",
        fields=[F("product", "Product"), F("vendor", "Vendor"), F("seats_owned", "Seats owned", "number"), F("seats_used", "Seats used", "number"),
                F("renewal_date", "Renewal date", "date")]),
    "contract": dict(label="Contracts", prefix="CTR", section="ITAM", create=STAFF,
        flow={"draft": ["active"], "active": ["expired", "renewed"], "renewed": ["active"], "expired": []}, initial="draft",
        fields=[F("vendor", "Vendor"), F("contract_type", "Type", "select", ["support", "lease", "license", "service", "maintenance"]),
                F("start_date", "Start", "date"), F("end_date", "End", "date")]),
    "purchase_order": dict(label="Purchase Orders", prefix="PO", section="ITAM", create=STAFF,
        flow={"draft": ["submitted", "cancelled"], "submitted": ["approved", "rejected"], "approved": ["ordered"], "ordered": ["received"], "received": [], "rejected": [], "cancelled": []}, initial="draft",
        fields=[F("vendor", "Vendor"), F("item", "Item"), F("quantity", "Quantity", "number"), F("contract", "Contract"), F("expected_date", "Expected delivery", "date")]),
    # ---------- CSM ----------
    "account": dict(label="Accounts", prefix="ACC", section="Customer Service", create=STAFF,
        flow={"active": ["inactive"], "inactive": ["active"]}, initial="active",
        fields=[F("industry", "Industry"), F("tier", "Tier", "select", ["platinum", "gold", "silver"]), F("region", "Region"), F("website", "Website")]),
    "contact": dict(label="Contacts", prefix="CON", section="Customer Service", create=STAFF,
        flow={"active": ["inactive"], "inactive": ["active"]}, initial="active",
        fields=[F("account", "Account number"), F("email", "Email"), F("phone", "Phone"), F("job_title", "Job title")]),
    "case": dict(label="Cases", prefix="CS", section="Customer Service", create=ALL, ai=True, sla=True,
        flow={"new": ["in_progress", "cancelled"], "in_progress": ["awaiting_customer", "resolved"], "awaiting_customer": ["in_progress"],
              "resolved": ["closed", "in_progress"], "closed": [], "cancelled": []},
        fields=[F("account", "Account number"), F("contact", "Contact"), F("product", "Product"), F("channel", "Channel", "select", ["portal", "email", "phone", "chat", "whatsapp"])]),
    "entitlement": dict(label="Entitlements", prefix="ENT", section="Customer Service", create=STAFF,
        flow={"active": ["expired"], "expired": ["active"]}, initial="active",
        fields=[F("account", "Account number"), F("sla_tier", "SLA tier", "select", ["24x7", "business_hours", "best_effort"]), F("support_hours", "Support hours", "number"),
                F("used_hours", "Used hours", "number"), F("end_date", "End date", "date")]),
    # ---------- HRSD ----------
    "hr_case": dict(label="HR Cases", prefix="HRC", section="HR Service Delivery", create=ALL, sla=True,
        flow={"new": ["in_progress", "cancelled"], "in_progress": ["awaiting_employee", "resolved"], "awaiting_employee": ["in_progress"], "resolved": ["closed"], "closed": [], "cancelled": []},
        fields=[F("hr_category", "HR category", "select", ["payroll", "benefits", "leave", "onboarding", "offboarding", "policy", "documents"]), F("employee", "Employee"),
                F("confidential", "Confidential", "bool")]),
    # ---------- Workplace ----------
    "facility_request": dict(label="Facilities", prefix="FAC", section="Workplace", create=ALL, sla=True,
        flow=linear("new", "assigned", "in_progress", "completed", "closed", extra={"new": ["cancelled"]}),
        fields=[F("building", "Building"), F("floor", "Floor"), F("facility_type", "Type", "select", ["hvac", "electrical", "cleaning", "furniture", "plumbing", "other"])]),
    "reservation": dict(label="Reservations", prefix="RSV", section="Workplace", create=ALL, compute="reservation",
        flow={"confirmed": ["checked_in", "cancelled"], "checked_in": ["completed"], "completed": [], "cancelled": [], "conflict": ["cancelled"]}, initial="confirmed",
        fields=[F("space", "Space", "select", ["Board Room", "Huddle 1", "Huddle 2", "Desk A-12", "Desk A-14", "Training Hall"]), F("start", "Start", "datetime-local"),
                F("end", "End", "datetime-local"), F("attendees", "Attendees", "number")]),
    "visitor": dict(label="Visitors", prefix="VIS", section="Workplace", create=ALL,
        flow=linear("expected", "checked_in", "checked_out", extra={"expected": ["cancelled"]}), initial="expected",
        fields=[F("visitor_name", "Visitor name"), F("company", "Company"), F("host", "Host"), F("visit_date", "Visit date", "date"), F("nda_signed", "NDA signed", "bool")]),
    # ---------- FSM ----------
    "work_order": dict(label="Work Orders", prefix="WO", section="Field Service", create=STAFF, sla=True, custom_page="/fsm",
        flow={"new": ["scheduled", "cancelled"], "scheduled": ["dispatched", "new"], "dispatched": ["on_site"], "on_site": ["completed"], "completed": ["closed"], "closed": [], "cancelled": []},
        fields=[F("customer", "Customer / site"), F("location", "Location"), F("skill", "Required skill", "select", ["network", "hardware", "electrical", "printer", "cctv"]),
                F("scheduled_start", "Scheduled start", "datetime-local"), F("duration_h", "Duration (h)", "number"), F("technician", "Technician")]),
    # ---------- SecOps ----------
    "sec_incident": dict(label="Security Incidents", prefix="SIR", section="Security Ops", create=STAFF, sla=True, ai=True,
        flow=linear("new", "analysis", "contain", "eradicate", "recover", "review", "closed", extra={"new": ["false_positive"]}),
        fields=[F("attack_vector", "Attack vector", "select", ["phishing", "malware", "ransomware", "credential_theft", "ddos", "insider", "other"]),
                F("mitre_tactic", "MITRE tactic"), F("affected_ci", "Affected CI"), F("source_ip", "Source IP"), F("playbook", "Playbook")]),
    "vulnerability": dict(label="Vulnerabilities", prefix="VUL", section="Security Ops", create=STAFF, compute="vulnerability",
        flow=linear("open", "triaged", "remediating", "resolved", extra={"open": ["accepted_risk"], "triaged": ["accepted_risk"]}), initial="open",
        fields=[F("cve", "CVE"), F("cvss", "CVSS", "number"), F("affected_ci", "Affected CI"), F("patch_available", "Patch available", "bool"), F("scanner", "Scanner")]),
    # ---------- GRC ----------
    "policy": dict(label="Policies", prefix="POL", section="GRC", create=STAFF,
        flow=linear("draft", "review", "published", "retired"), initial="draft",
        fields=[F("framework", "Framework", "select", ["ISO27001", "SOC2", "GDPR", "Internal"]), F("version", "Version"), F("owner", "Owner"), F("review_date", "Next review", "date")]),
    "risk": dict(label="Risks", prefix="RSK", section="GRC", create=STAFF, compute="risk",
        flow={"identified": ["assessed"], "assessed": ["treating", "accepted"], "treating": ["monitored"], "monitored": ["closed", "treating"], "accepted": ["closed"], "closed": []}, initial="identified",
        fields=[F("likelihood", "Likelihood (1-5)", "number"), F("consequence", "Consequence (1-5)", "number"),
                F("treatment", "Treatment", "select", ["mitigate", "transfer", "avoid", "accept"]), F("owner", "Owner"), F("framework", "Framework", "select", ["ISO27001", "SOC2", "GDPR", "Internal"])]),
    "control": dict(label="Controls", prefix="CTL", section="GRC", create=STAFF,
        flow={"not_tested": ["effective", "ineffective"], "effective": ["not_tested", "ineffective"], "ineffective": ["remediating"], "remediating": ["effective", "ineffective"]}, initial="not_tested",
        fields=[F("framework", "Framework", "select", ["ISO27001", "SOC2", "GDPR"]), F("control_id", "Control ID"), F("owner", "Owner"), F("evidence", "Evidence", "textarea")]),
    "audit_engagement": dict(label="Audits", prefix="AUD", section="GRC", create=STAFF,
        flow=linear("planned", "fieldwork", "reporting", "closed"), initial="planned",
        fields=[F("framework", "Framework", "select", ["ISO27001", "SOC2", "GDPR", "Internal"]), F("auditor", "Auditor"), F("scope", "Scope", "textarea"), F("findings", "Findings", "number")]),
    # ---------- SPM ----------
    "demand": dict(label="Demands", prefix="DMD", section="Portfolio", create=ALL, compute="demand",
        flow={"submitted": ["screening"], "screening": ["approved", "rejected"], "approved": [], "rejected": []}, initial="submitted",
        fields=[F("business_value", "Business value (1-10)", "number"), F("strategic_alignment", "Strategic alignment (1-10)", "number"),
                F("effort_weeks", "Effort (weeks)", "number")]),
    "project": dict(label="Projects", prefix="PRJ", section="Portfolio", create=STAFF, compute="project",
        flow=linear("initiating", "planning", "executing", "closing", "closed", extra={"executing": ["on_hold"], "on_hold": ["executing"]}), initial="initiating",
        fields=[F("pm", "Project manager"), F("percent_complete", "% complete", "number"),
                F("start_date", "Start", "date"), F("end_date", "End", "date"), F("team", "Team (email:alloc%, …)")]),
    # ---------- Patch ----------
    "patch_job": dict(label="Patch Jobs", prefix="PAT", section="Autonomy", create=STAFF, custom_page="/patch",
        flow={"draft": ["dry_run_complete"], "dry_run_complete": ["approved", "draft"], "approved": ["deploying"], "deploying": ["completed", "halted"],
              "halted": ["deploying", "cancelled"], "completed": [], "cancelled": []}, initial="draft",
        fields=[F("os", "Target OS", "select", ["Windows", "Linux", "macOS"]), F("environment", "Environment", "select", ["production", "staging", "development"]),
                F("patches", "Patch IDs (comma separated)"), F("window", "Maintenance window", "datetime-local")]),
}
CLOSED = {"resolved", "closed", "cancelled", "fulfilled", "completed", "rejected", "done", "retired", "expired", "false_positive", "checked_out", "accepted_risk", "approved_final"}

def initial(m): return MODULES[m].get("initial") or next(iter(MODULES[m]["flow"]))
def allowed(m, s): return MODULES[m]["flow"].get(s, [])
def prefix(m): return MODULES[m]["prefix"]

def meta():
    return [{"key": k, **{x: v.get(x) for x in ("label", "prefix", "section", "fields", "custom_page", "hidden")}, "create": list(v["create"]),
             "states": list(v["flow"]), "ai": bool(v.get("ai")), "sla": bool(v.get("sla"))} for k, v in MODULES.items()]
