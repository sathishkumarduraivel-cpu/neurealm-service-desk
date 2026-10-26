def me(client, h): return client.get("/api/auth/me", headers=h).json()

def test_catalog_builder_conditional_stages_fulfilment_csat_reopen(client, admin, agent, user):
    a = me(client, agent); grp = client.get("/api/groups", headers=agent).json()[0]["name"]
    body = {"name": "Test laptop", "category": "Hardware", "fulfillment_group": grp,
            "form_fields": [{"key": "os", "label": "OS", "type": "choice", "options": ["Windows", "macOS"], "required": True},
                            {"key": "why_mac", "label": "Why a Mac?", "type": "text", "required": True, "visible_if": {"field": "os", "value": "macOS"}}],
            "approval_stages": [{"name": "Manager", "approver": f"user:{a['id']}"}, {"name": "IT", "approver": "admin"}], "fulfilment_tasks": ["Image laptop", "Hand over"]}
    assert client.post("/api/catalog-admin/items", json=body, headers=agent).status_code == 403
    assert client.post("/api/catalog-admin/items", json={**body, "approval_stages": [{"approver": "boss"}]}, headers=admin).status_code == 400
    it = client.post("/api/catalog-admin/items", json=body, headers=admin).json()
    assert it["id"] in [x["id"] for x in client.get("/api/portal/catalog", headers=user).json()]
    o = f"/api/portal/order/{it['id']}"
    assert client.post(o, json={"values": {}}, headers=user).status_code == 400
    assert client.post(o, json={"values": {"os": "macOS"}}, headers=user).status_code == 400
    r = client.post(o, json={"values": {"os": "Windows", "why_mac": "ignored"}}, headers=user).json(); assert r["state"] == "pending_approval"
    rec = client.get(f"/api/records/request/{r['id']}", headers=agent).json()
    assert "why_mac" not in rec["data"]["values"] and len(rec["approvals"]) == 2
    l1 = [x for x in rec["approvals"] if x["level"] == 1][0]; l2 = [x for x in rec["approvals"] if x["level"] == 2][0]
    assert client.post(f"/api/approvals/{l2['id']}/decide", json={"approve": True}, headers=admin).status_code == 400  # stage 1 first
    client.post(f"/api/approvals/{l1['id']}/decide", json={"approve": True}, headers=agent)
    rec = client.post(f"/api/approvals/{l2['id']}/decide", json={"approve": True}, headers=admin).json()
    assert rec["state"] == "in_progress" and [t["title"] for t in rec["data"]["tasks"]] == ["Image laptop", "Hand over"]
    assert client.post(f"/api/records/request/{r['id']}/rate", json={"score": 5}, headers=user).status_code == 400
    for t in rec["data"]["tasks"]: rec = client.post(f"/api/records/request/{r['id']}/tasks/{t['id']}/toggle", headers=agent).json()
    assert client.get(f"/api/records/request/{r['id']}", headers=agent).json()["state"] == "fulfilled"
    assert client.post(f"/api/records/request/{r['id']}/rate", json={"score": 9}, headers=user).status_code == 400
    assert client.post(f"/api/records/request/{r['id']}/rate", json={"score": 2, "comment": "slow"}, headers=agent).status_code == 403
    assert client.post(f"/api/records/request/{r['id']}/rate", json={"score": 4, "comment": "Nice"}, headers=user).json()["ok"]
    s = client.get("/api/csat/summary", headers=agent).json(); assert s["responses"] >= 1 and s["distribution"]["4"] >= 1
    assert client.post(f"/api/records/request/{r['id']}/reopen", json={"reason": ""}, headers=user).status_code == 400
    assert client.post(f"/api/records/request/{r['id']}/reopen", json={"reason": "Charger missing"}, headers=user).json()["state"] == "in_progress"

def test_on_behalf_and_entitlements(client, admin, agent, user):
    u = me(client, user)
    it = client.post("/api/catalog-admin/items", json={"name": "Agents only", "requires_approval": False, "entitled": ["agent"], "fulfilment_tasks": ["Do it"]}, headers=admin).json()
    assert it["id"] not in [x["id"] for x in client.get("/api/portal/catalog", headers=user).json()]
    assert client.post(f"/api/portal/order/{it['id']}", json={}, headers=user).status_code == 403
    r = client.post(f"/api/portal/order/{it['id']}", json={"on_behalf_of": u["id"]}, headers=agent).json(); assert r["state"] == "in_progress"
    rec = client.get(f"/api/records/request/{r['id']}", headers=user).json()
    assert rec["requester"]["id"] == u["id"] and rec["data"]["ordered_by_name"]

def test_delegation(client, admin, agent):
    a, ad = me(client, agent), me(client, admin)
    assert client.put("/api/me/delegate", json={"to_user_id": ad["id"]}, headers=admin).status_code == 400
    it = client.post("/api/catalog-admin/items", json={"name": "Deleg item", "approval_stages": [{"approver": f"user:{ad['id']}"}]}, headers=admin).json()
    r = client.post(f"/api/portal/order/{it['id']}", json={}, headers=agent).json()
    ap = client.get(f"/api/records/request/{r['id']}", headers=agent).json()["approvals"][0]
    assert client.post(f"/api/approvals/{ap['id']}/decide", json={"approve": True}, headers=agent).status_code == 403
    client.put("/api/me/delegate", json={"to_user_id": a["id"], "until": "2099-01-01"}, headers=admin)
    assert ap["id"] in [x["approval_id"] for x in client.get("/api/approvals/pending", headers=agent).json()]
    d = client.post(f"/api/approvals/{ap['id']}/decide", json={"approve": True}, headers=agent).json()
    assert "on behalf" in d["approvals"][0]["comment"]
    client.put("/api/me/delegate", json={"to_user_id": None}, headers=admin)

def test_kb_versions_feedback_insights(client, agent, user):
    a = client.get("/api/kb", headers=agent).json()[0]
    v = client.put(f"/api/kb/{a['id']}", json={"title": a["title"] + " (updated)", "body": "New body"}, headers=agent).json(); assert v["version"] == 2
    assert client.put(f"/api/kb/{a['id']}", json={"title": "x", "body": "y"}, headers=user).status_code == 403
    h = client.get(f"/api/kb/{a['id']}/versions", headers=agent).json(); assert h["current"] == 2 and h["versions"][0]["title"] == a["title"]
    assert client.post(f"/api/kb/{a['id']}/feedback", json={"helpful": False}, headers=user).json()["not_helpful"] >= 1
    assert client.post(f"/api/kb/{a['id']}/feedback", json={"helpful": True}, headers=user).status_code == 409
    ins = client.get("/api/kb-insights", headers=agent).json(); assert ins["total"] and ins["needs_work"] and "gaps" in ins
