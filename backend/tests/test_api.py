def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"

def test_login_bad(client):
    assert client.post("/api/auth/login", json={"email": "admin@neurealm.com", "password": "x"}).status_code == 401

def test_rbac(client, user, agent):
    assert client.get("/api/users", headers=user).status_code == 403
    assert client.get("/api/audit", headers=agent).status_code == 403
    assert client.get("/api/records/incident").status_code == 401
    assert client.post("/api/records/change", json={"title": "x"}, headers=user).status_code == 403

def test_ai_triage(client, agent):
    r = client.post("/api/ai/triage", json={"title": "VPN outage for all users", "description": "cannot connect"}, headers=agent).json()
    assert r["category"] == "network" and r["priority"] == "P1" and r["assignment_group"] == "Network Ops"
    assert r["kb_suggestions"] and "VPN" in r["kb_suggestions"][0]["title"]
    r = client.post("/api/ai/triage", json={"title": "Forgot my password, account locked"}, headers=agent).json()
    assert r["category"] == "access"

def test_incident_lifecycle(client, user, agent):
    r = client.post("/api/records/incident", json={"title": "Outlook crash when opening email"}, headers=user)
    assert r.status_code == 201
    inc = r.json(); assert inc["number"].startswith("INC") and inc["sla_due_at"] and inc["ai_suggestion"]["engine"] == "rules"
    iid = inc["id"]
    assert client.patch(f"/api/records/incident/{iid}", json={"state": "closed"}, headers=agent).status_code == 400
    for s in ("in_progress", "resolved", "closed"):
        r = client.patch(f"/api/records/incident/{iid}", json={"state": s}, headers=agent); assert r.status_code == 200, r.text
    assert r.json()["resolved_at"]
    assert client.post(f"/api/records/incident/{iid}/comments", json={"body": "Fixed"}, headers=agent).status_code == 201
    # end user sees only own
    mine = client.get("/api/records/incident", headers=user).json()
    assert all(x["requester"]["email"] == "user@neurealm.com" for x in mine)

def test_priority_matrix_and_sla(client, agent):
    r = client.post("/api/records/incident", json={"title": "x", "impact": 1, "urgency": 1, "use_ai": False}, headers=agent).json()
    assert r["priority"] == "P1"
    pols = client.get("/api/sla/policies", headers=agent).json(); assert len(pols) >= 4

def test_problem_known_error(client, agent):
    incs = client.get("/api/records/incident", headers=agent).json()
    p = client.post("/api/records/problem", json={"title": "Recurring crash", "data": {"incident_ids": [incs[0]["id"], incs[1]["id"]]}}, headers=agent).json()
    assert len(p["linked"]) == 2
    p = client.post(f"/api/records/problem/{p['id']}/known-error", json={"workaround": "Restart"}, headers=agent).json()
    assert p["data"]["known_error"]
    assert any(k["id"] == p["id"] for k in client.get("/api/known-errors", headers=agent).json())

def test_change_approval_flow(client, agent, admin):
    c = client.post("/api/records/change", json={"title": "Upgrade core switch", "data": {"change_type": "normal", "rollback_plan": ""}}, headers=agent).json()
    assert c["data"]["risk_score"] > 0 and c["state"] == "new"
    for s in ("assess", "authorize"):
        c = client.patch(f"/api/records/change/{c['id']}", json={"state": s}, headers=agent).json()
    assert c["approvals"]
    for a in sorted(c["approvals"], key=lambda a: a["level"]):
        c = client.post(f"/api/approvals/{a['id']}/decide", json={"approve": True}, headers=admin).json()
    assert c["state"] == "scheduled"
    std = client.post("/api/records/change", json={"title": "Std patch", "data": {"change_type": "standard", "rollback_plan": "y", "tested": True}}, headers=agent).json()
    assert std["state"] == "scheduled" and std["data"]["risk_level"] == "low"

def test_catalog_request_approval(client, user, admin):
    items = client.get("/api/catalog", headers=user).json()
    item = next(i for i in items if i["requires_approval"])
    r = client.post(f"/api/catalog/{item['id']}/order", json={"values": {}, "justification": "need"}, headers=user).json()
    assert r["state"] == "pending_approval"
    r = client.post(f"/api/approvals/{r['approvals'][0]['id']}/decide", json={"approve": False, "comment": "no"}, headers=admin).json()
    assert r["state"] == "rejected"
    free = next(i for i in items if not i["requires_approval"])
    assert client.post(f"/api/catalog/{free['id']}/order", json={}, headers=user).json()["state"] == "approved"

def test_kb_search_and_generate(client, user, agent):
    res = client.get("/api/kb", params={"q": "vpn"}, headers=user).json()
    assert res and "VPN" in res[0]["title"]
    inc = client.get("/api/records/incident", headers=agent).json()[0]
    a = client.post(f"/api/kb/from-incident/{inc['id']}", headers=agent).json()
    assert a["ai_generated"] and not a["published"]

def test_dashboard(client, agent):
    m = client.get("/api/dashboard/metrics", headers=agent).json()
    assert m["totals"]["incident"] >= 20 and len(m["trend"]) == 14 and "sla_compliance_pct" in m

def test_admin_users(client, admin):
    r = client.post("/api/users", json={"email": "new@neurealm.com", "full_name": "New", "password": "pw12345", "role": "agent"}, headers=admin)
    assert r.status_code == 201
    assert client.patch(f"/api/users/{r.json()['id']}", json={"active": False}, headers=admin).json()["active"] is False

def test_audit_chain(client, admin):
    v = client.get("/api/audit/verify", headers=admin).json()
    assert v["valid"] and v["entries"] > 5
    from app.db import SessionLocal
    from app.models import AuditLog
    db = SessionLocal(); row = db.get(AuditLog, 2); orig = row.action; row.action = "tampered"; db.commit()
    assert client.get("/api/audit/verify", headers=admin).json() == {"valid": False, "broken_at": 2, "entries": v["entries"] + 0} or \
        client.get("/api/audit/verify", headers=admin).json()["valid"] is False
    row.action = orig; db.commit(); db.close()
    assert client.get("/api/audit/verify", headers=admin).json()["valid"]


def test_tenant_and_search(client, agent):
    t = client.get("/api/tenant", headers=agent).json()
    assert t["name"]
    r = client.get("/api/search", params={"q": "INC"}, headers=agent)
    assert r.status_code == 200 and isinstance(r.json(), list)
