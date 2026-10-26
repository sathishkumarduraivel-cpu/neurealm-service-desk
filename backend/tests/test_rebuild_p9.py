def test_email_to_ticket(client, admin):
    c = client.put("/api/email/config", json={"enabled": True, "module": "incident"}, headers=admin).json()
    tok = c["token_once"]; assert "token_once" not in client.get("/api/email/config", headers=admin).json()
    assert client.post("/api/inbound/email/1?token=bad", json={"from": "x@y.com", "subject": "s"}).status_code == 401
    assert client.post(f"/api/inbound/email/1?token={tok}", json={"from": "Stranger <who@nowhere.io>", "subject": "Hi"}).status_code == 403
    r = client.post(f"/api/inbound/email/1?token={tok}", json={"from": "User <user@neurealm.com>", "subject": "Printer jammed", "text": "Paper stuck\n\nOn Mon someone wrote:\n> old"}).json()
    assert r["action"] == "created"
    d = client.get(f"/api/records/incident/{r['id']}", headers=admin).json()
    assert d["description"] == "Paper stuck" and d["data"]["channel"] == "email"
    r2 = client.post(f"/api/inbound/email/1?token={tok}", json={"from": "user@neurealm.com", "subject": f"RE: [{r['number']}] Printer jammed", "text": "Still stuck"}).json()
    assert r2 == {"action": "commented", "number": r["number"]}

def test_alert_rules(client, admin, agent):
    assert client.put("/api/alerts/rules", json=[{"name": "x"}], headers=agent).status_code == 403
    client.put("/api/alerts/rules", json=[{"name": "Mute test", "contains": "synthetic", "action": "suppress"}, {"name": "Disk crit", "contains": "disk", "action": "set_severity", "set_severity": "critical"}], headers=admin)
    res = client.post("/api/alerts/ingest", json=[{"node": "a", "metric": "synthetic check", "severity": "warning"}, {"node": "srv9", "metric": "disk_full", "severity": "warning"}, {"metric": "x"}], headers=agent).json()
    assert res[0]["action"] == "suppressed" and res[1]["rule"] == "Disk crit" and res[1]["incident_id"] and res[2]["action"] == "rejected"

def test_directory_sync(client, admin):
    client.post("/api/directory/sync", json={"users": [{"email": "temp.one@neurealm.com", "name": "Temp One"}], "dry_run": False}, headers=admin)
    body = {"users": [{"email": "new.person@neurealm.com", "name": "New Person"}, {"email": "temp.one@neurealm.com", "name": "Temp One", "active": False}, {"email": "bad", "name": "x"}, {"email": "z@neurealm.com", "name": "Z", "role": "admin"}]}
    dry = client.post("/api/directory/sync", json=body, headers=admin).json()
    assert dry["create"] == ["new.person@neurealm.com"] and dry["deactivate"] == ["temp.one@neurealm.com"] and len(dry["errors"]) == 2
    users = {x["email"]: x for x in client.get("/api/users", headers=admin).json()}
    assert "new.person@neurealm.com" not in users and users["temp.one@neurealm.com"]["active"]
    client.post("/api/directory/sync", json={**body, "dry_run": False}, headers=admin)
    users = {x["email"]: x for x in client.get("/api/users", headers=admin).json()}
    assert "new.person@neurealm.com" in users and not users["temp.one@neurealm.com"]["active"]

def test_v1_api_with_key(client, agent):
    k = client.post("/api/me/api-keys", json={"name": "ci"}, headers=agent).json()["key"]
    h = {"Authorization": f"Bearer {k}"}
    assert client.get("/api/v1/records/incident", headers={"Authorization": "Bearer nrsd_nope"}).status_code == 401
    c = client.post("/api/v1/records/incident", json={"title": "From API"}, headers=h).json()
    assert c["number"] and client.get(f"/api/v1/records/incident/{c['number']}", headers=h).json()["data"]["channel"] == "api"
    assert client.post(f"/api/v1/records/incident/{c['number']}/comments", json={"body": "hi"}, headers=h).status_code == 201
    assert client.get("/api/v1/records/nope", headers=h).status_code == 404

def test_export_and_errors(client, admin, agent):
    assert client.get("/api/admin/export", headers=agent).status_code == 403
    j = client.get("/api/admin/export", headers=admin)
    assert j.status_code == 200 and "password_hash" not in j.text and j.json()["records"]
    z = client.get("/api/admin/export?fmt=zip", headers=admin); assert z.content[:2] == b"PK"
    client.post("/api/errors/client", json={"message": "TypeError: boom", "path": "/x"}, headers=agent)
    assert client.get("/api/admin/errors", headers=admin).json()[0]["message"] == "TypeError: boom"

def test_offboarding_deactivates(client, admin):
    client.post("/api/directory/sync", json={"users": [{"email": "leaver@neurealm.com", "name": "Leaver"}], "dry_run": False}, headers=admin)
    client.put("/api/hr/settings", json={"deactivate_on_offboard": True}, headers=admin)
    r = client.post("/api/hr/lifecycle", json={"type": "offboarding", "employee": "Leaver", "employee_email": "leaver@neurealm.com"}, headers=admin).json()
    tasks = [t for t in client.get("/api/records/task?limit=1000", headers=admin).json() if t["title"].endswith("— Leaver")]
    assert len(tasks) == r["tasks"]
    for t in tasks:
        for st in ("in_progress", "done"):
            x = client.patch(f"/api/records/task/{t['id']}", json={"state": st}, headers=admin); assert x.status_code == 200, x.text
    users = {x["email"]: x for x in client.get("/api/users", headers=admin).json()}
    assert users["leaver@neurealm.com"]["active"] is False
