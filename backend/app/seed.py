"""Seed demo data: python -m app.seed  (idempotent: skips if users exist; --reset to wipe)."""
import random, sys
from datetime import timedelta
from sqlalchemy import select
from .db import SessionLocal, Base, engine
from .models import *
from .security import hash_pw
from . import ai, sla, audit, workflow as wf

GROUPS = [("Service Desk", "L1 support"), ("Network Ops", "Network & VPN"), ("Desktop Support", "End-user hardware"),
          ("Application Support", "Business apps"), ("Database Team", "DBA"), ("Security Ops", "SecOps"), ("HR Services", "HR"),
          ("CAB", "Change Advisory Board"), ("Field Services", "Field technicians"), ("Customer Support", "CSM agents"), ("Facilities", "Workplace services"), ("PMO", "Portfolio office"), ("GRC", "Risk & compliance")]
USERS = [("admin@neurealm.com", "Priya Raman", "admin", "Admin@123", "CAB"),
         ("cab@neurealm.com", "Karthik Subramanian", "admin", "Admin@123", "CAB"),
         ("agent@neurealm.com", "Arun Kumar", "agent", "Agent@123", "Service Desk"),
         ("netops@neurealm.com", "Divya Srinivasan", "agent", "Agent@123", "Network Ops"),
         ("appsupport@neurealm.com", "Rahul Menon", "agent", "Agent@123", "Application Support"),
         ("tech1@neurealm.com", "Suresh Babu", "agent", "Agent@123", "Field Services"),
         ("tech2@neurealm.com", "Anitha Rajan", "agent", "Agent@123", "Field Services"),
         ("user@neurealm.com", "Meena Lakshmi", "end_user", "User@123", None),
         ("user2@neurealm.com", "Vikram Iyer", "end_user", "User@123", None)]
KB = [("How to reset your Windows/SSO password", "1. Go to https://passwordreset.neurealm.com\n2. Verify with MFA.\n3. Choose a new password (12+ chars).\nIf locked out, call the Service Desk.", "access", "password,reset,sso,locked,account,login"),
      ("Fix VPN connection failures (GlobalProtect)", "1. Check internet connectivity.\n2. Restart the GlobalProtect client.\n3. Re-enter portal vpn.neurealm.com.\n4. Clear cached credentials.\nStill failing? Raise an incident to Network Ops.", "network", "vpn,network,connectivity,remote"),
      ("Outlook not syncing or crashing", "Run Outlook in safe mode (outlook.exe /safe), disable add-ins, repair the Office installation, rebuild the OST profile.", "email", "outlook,email,crash,sync,mailbox"),
      ("Connect to office Wi-Fi", "Select Corp-WiFi, authenticate with your SSO credentials, accept the certificate.", "network", "wifi,wi-fi,network,wireless"),
      ("Printer shows offline", "Power-cycle printer, check network cable, re-add printer via \\\\print01.", "hardware", "printer,offline,hardware"),
      ("Reporting a phishing email", "Do not click links. Use the 'Report Phish' button in Outlook or forward to security@neurealm.com.", "security", "phishing,email,security,suspicious"),
      ("Requesting software installation", "Use the Service Catalog > Software Request. Licensed software requires manager approval.", "software", "install,software,license,application"),
      ("Laptop battery draining fast", "Check battery health in Power settings, update BIOS, reduce screen brightness; request replacement via catalog if <60% health.", "hardware", "laptop,battery,hardware")]
CATALOG = [("New Laptop", "Hardware", "Standard developer or business laptop", "💻", True, "Desktop Support", [{"name": "model", "label": "Model", "type": "select", "options": ["Dell Latitude 7450", "MacBook Pro 14", "Lenovo T14"]}]),
           ("Software Request", "Software", "Request licensed software", "🧩", True, "Application Support", [{"name": "software", "label": "Software name", "type": "text"}]),
           ("VPN Access", "Access", "Remote VPN access", "🔐", True, "Network Ops", [{"name": "duration", "label": "Duration", "type": "select", "options": ["30 days", "90 days", "Permanent"]}]),
           ("Password Reset", "Access", "Self-service password reset assist", "🔑", False, "Service Desk", []),
           ("Shared Mailbox", "Email", "Create a shared mailbox", "📧", True, "Application Support", [{"name": "mailbox", "label": "Mailbox name", "type": "text"}]),
           ("Monitor / Peripherals", "Hardware", "Monitor, keyboard, mouse, dock", "🖥️", False, "Desktop Support", [{"name": "item", "label": "Item", "type": "text"}]),
           ("Employee Onboarding", "HR", "Onboard new joiner: accounts, laptop, access", "🧑‍💼", True, "HR Services", [{"name": "employee", "label": "Employee name", "type": "text"}, {"name": "start_date", "label": "Start date", "type": "date"}])]
INCIDENTS = ["VPN not connecting from home", "Outlook crashes on startup", "Cannot login - account locked", "Production database slow for all users",
             "Printer on 3rd floor offline", "Suspicious phishing email received", "Wi-Fi intermittent in conference room", "Teams calls dropping for multiple users",
             "Laptop battery drains quickly", "Excel macro error after update", "ERP outage - entire finance team cannot work", "Password reset not working",
             "Monitor flickering", "SAP login error", "Email not syncing on mobile", "DNS resolution failing intermittently", "Payroll portal access denied",
             "Ransomware alert on file server", "Slow internet in Chennai office", "Application crash when exporting report"]

SEED_VERSION = "rebuild-10"  # bump to wipe and reseed demo data on next deploy

def _stored_version():
    from . import settings_store
    try:
        db = SessionLocal()
        try: return settings_store.get(db, 1, "seed_version").get("v")
        finally: db.close()
    except Exception:
        return None

def run(reset=False):
    if not reset and _stored_version() != SEED_VERSION:
        print("Seed version changed: wiping demo data"); reset = True
    if reset: Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if db.scalar(select(User)):
        print("Already seeded"); return
    random.seed(42)
    db.add_all([Tenant(id=1, name="Neurealm", domain="neurealm.com"), Tenant(id=2, name="Acme Corp (demo tenant)", domain="acme.test")]); db.flush()
    db.add(Group(tenant_id=2, name="Service Desk", description="Acme L1"))
    db.add(User(tenant_id=2, email="admin@acme.test", full_name="Acme Admin", role="admin", password_hash=hash_pw("Acme@123")))
    g = {}
    for n, d in GROUPS:
        g[n] = Group(name=n, description=d); db.add(g[n])
    db.flush()
    users = {}
    for e, n, r, p, gr in USERS:
        users[e] = User(email=e, full_name=n, role=r, password_hash=hash_pw(p), group_id=g[gr].id if gr else None); db.add(users[e])
    for m, (pr, (resp, res)) in [(m, x) for m in ("incident", "request", "case", "hr_case", "sec_incident", "work_order", "facility_request") for x in sla.DEFAULTS.items()]:
        db.add(SLAPolicy(name=f"{m.title()} {pr}", module=m, priority=pr, response_minutes=resp, resolution_minutes=res if m == "incident" else res * 3))
    for i, (t, b, c, tags) in enumerate(KB):
        db.add(KBArticle(number=f"KB{1001 + i:07d}", title=t, body=b, category=c, tags=tags, views=random.randint(5, 300)))
    for n, c, d, ic, ap, fg, ff in CATALOG:
        db.add(CatalogItem(name=n, category=c, description=d, icon=ic, requires_approval=ap, fulfillment_group_id=g[fg].id, form_fields=ff))
    db.flush()
    agents = [u for u in users.values() if u.role == "agent" and not u.email.startswith("tech")]
    users["tech1@neurealm.com"].skills = ["network", "cctv"]; users["tech2@neurealm.com"].skills = ["hardware", "printer", "electrical"]
    requesters = [users["user@neurealm.com"], users["user2@neurealm.com"]]
    t0 = now(); incs = []
    for i, title in enumerate(INCIDENTS):
        tri = ai.triage(db, title, "")
        created = t0 - timedelta(days=random.randint(0, 13), hours=random.randint(0, 20))
        state = random.choice(["new", "in_progress", "in_progress", "on_hold", "resolved", "closed", "closed"])
        r = Record(module="incident", number=f"INC{1001 + i:07d}", title=title, description=f"Reported via portal: {title}.",
                   category=tri["category"], priority=tri["priority"], impact=tri["impact"], urgency=tri["urgency"],
                   assignment_group_id=tri["assignment_group_id"], requester_id=random.choice(requesters).id,
                   assignee_id=random.choice(agents).id if state != "new" else None, state=state, created_at=created, ai_suggestion=tri)
        sla.apply_sla(db, r)
        if state in ("resolved", "closed"): r.resolved_at = created + timedelta(hours=random.uniform(0.5, 30))
        db.add(r); incs.append(r)
    db.flush()
    vpn = [r for r in incs if "vpn" in r.title.lower() or "dns" in r.title.lower() or "wi-fi" in r.title.lower()]
    p1 = Record(module="problem", number="PRB0001001", title="Recurring VPN / network connectivity failures", state="root_cause_analysis",
                description="Multiple incidents of remote connectivity failure; suspected VPN concentrator capacity.", category="network",
                priority="P2", impact=2, urgency=2, assignment_group_id=g["Network Ops"].id, requester_id=users["agent@neurealm.com"].id,
                data={"root_cause": "VPN concentrator license cap at 500 sessions"}, created_at=t0 - timedelta(days=5))
    p1.linked = vpn
    p2 = Record(module="problem", number="PRB0001002", title="Outlook crashes after Office update", state="known_error", category="email",
                description="Office build 2409 causes Outlook crash with legacy add-in.", priority="P3", impact=3, urgency=2,
                assignment_group_id=g["Application Support"].id, requester_id=users["agent@neurealm.com"].id,
                data={"known_error": True, "root_cause": "Incompatible COM add-in", "workaround": "Disable 'LegacySync' add-in, then restart Outlook."},
                created_at=t0 - timedelta(days=3))
    p2.linked = [r for r in incs if "outlook" in r.title.lower()]
    db.add_all([p1, p2])
    changes = [("Upgrade VPN concentrator licenses to 2000 sessions", "normal", "authorize", 2, {"rollback_plan": "Revert license file", "tested": True}),
               ("Monthly Windows patching - Wave 1", "standard", "scheduled", 3, {"rollback_plan": "Uninstall KB", "tested": True}),
               ("Emergency firewall rule to block ransomware C2", "emergency", "authorize", 1, {"rollback_plan": "", "tested": False}),
               ("Migrate ERP database to new cluster", "normal", "assess", 1, {"rollback_plan": "Fallback to old cluster", "tested": False}),
               ("Rollout Office update 2410", "normal", "closed", 3, {"rollback_plan": "Rollback to 2409", "tested": True})]
    for i, (t, ct, st, imp, extra) in enumerate(changes):
        d = {"change_type": ct, "affects_production": True, "planned_start": (t0 + timedelta(days=i + 1)).isoformat(), **extra}
        d.update(wf.change_risk(d, imp))
        c = Record(module="change", number=f"CHG{1001 + i:07d}", title=t, state=st, description=t, priority=ai.priority_from(imp, 2),
                   impact=imp, urgency=2, category="infrastructure", data=d, assignment_group_id=g["CAB"].id,
                   requester_id=users["netops@neurealm.com"].id, created_at=t0 - timedelta(days=i))
        if st == "authorize":
            c.approvals.append(Approval(level=1, approver_id=users["admin@neurealm.com"].id))
        db.add(c)
    items = db.scalars(select(CatalogItem)).all()
    for i, (it, st) in enumerate([(items[0], "pending_approval"), (items[2], "approved"), (items[1], "in_progress"), (items[3], "fulfilled")]):
        rq = Record(module="request", number=f"REQ{1001 + i:07d}", title=f"{it.name} for {requesters[i % 2].full_name}", state=st,
                    requester_id=requesters[i % 2].id, category=it.category, priority="P4", assignment_group_id=it.fulfillment_group_id,
                    data={"catalog_item_id": it.id, "item": it.name, "values": {}}, created_at=t0 - timedelta(days=i))
        if it.requires_approval:
            rq.approvals.append(Approval(level=1, approver_id=users["admin@neurealm.com"].id, state="requested" if st == "pending_approval" else "approved"))
        sla.apply_sla(db, rq); db.add(rq)
    from . import seed_ext
    seed_ext.phase_b(db, users, g, t0)
    for fn in ("phase_c", "phase_d", "phase_e", "phase_f", "phase_g", "phase_h", "phase_i"):
        if hasattr(seed_ext, fn): getattr(seed_ext, fn)(db, users, g, t0)
    from . import settings_store
    from .models import FieldDef
    for i, (k, l, ty, opts, mods, sec, cond, lst) in enumerate([
        ("device_type", "Device type", "choice", ["Laptop", "Desktop", "Phone", "Printer", "Other"], ["incident", "request"], "Device", {}, True),
        ("asset_tag", "Asset tag", "text", [], ["incident", "request"], "Device", {"field": "device_type", "op": "filled"}, False),
        ("site", "Office site", "choice", ["Chennai", "Bengaluru", "Pune", "Remote"], ["*"], "Location", {}, True),
        ("floor", "Floor", "number", [], ["incident"], "Location", {"field": "site", "op": "neq", "value": "Remote"}, False)]):
        db.add(FieldDef(tenant_id=1, key=k, label=l, type=ty, options=opts, modules=mods, section=sec, condition=cond, show_in_list=lst, position=i,
                        help="Helps us find you faster." if k == "floor" else "", default={"v": None}))
    db.flush()
    from .models import Group as _G, User as _U
    from datetime import timedelta as _td
    settings_store.put(db, 1, "sla.calendar", {"v": {"enabled": False, "tz_offset_min": 330, "days": [0, 1, 2, 3, 4], "start": "09:00", "end": "18:00", "holidays": ["2026-12-25", "2027-01-26"]}})
    pols, rota = {}, []
    for gi, grp in enumerate(db.query(_G).filter(_G.tenant_id == 1).order_by(_G.id).limit(3)):
        mem = db.query(_U).filter(_U.group_id == grp.id, _U.role != "end_user").order_by(_U.id).all()
        if not mem: continue
        pols[grp.name] = ["round_robin", "least_loaded", "on_call"][gi]
        base = (t0 + _td(minutes=330)).replace(hour=9, minute=0, second=0, microsecond=0)
        for k in range(3):
            m = mem[k % len(mem)]; st = base + _td(days=k - 1)
            rota.append({"id": len(rota) + 1, "group": grp.name, "user_id": m.id, "name": m.full_name, "start": st.strftime("%Y-%m-%dT%H:%M"), "end": (st + _td(days=1)).strftime("%Y-%m-%dT%H:%M"), "note": ""})
    settings_store.put(db, 1, "assign.policies", {"v": pols}); settings_store.put(db, 1, "oncall", {"v": rota})
    audit.log(db, None, "seed", "system", "demo", {"incidents": len(incs)})
    db.commit(); sla.refresh_breaches(db)
    settings_store.put(db, 1, "seed_version", {"v": SEED_VERSION}); db.commit(); db.close()
    print("Seeded demo data")

if __name__ == "__main__":
    run(reset="--reset" in sys.argv)
