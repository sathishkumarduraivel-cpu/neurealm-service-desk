def mk(client, h, title, desc=""):
    r = client.post("/api/records/incident", json={"title": title, "description": desc}, headers=h)
    assert r.status_code == 201, r.text; return r.json()

def test_config_categories_fields_matrix(client, admin, agent):
    c = client.get("/api/ticketing/config", headers=agent).json()
    assert "Network" in c["categories"] and c["matrix"]["1,1"] == "P1" and c["canned"]
    assert client.put("/api/ticketing/config", json={"categories": ["X"]}, headers=agent).status_code == 403
    c = client.put("/api/ticketing/config", json={"fields": [{"label": "Floor number", "type": "number"}], "matrix": {"3,3": "P3"}}, headers=admin).json()
    assert c["fields"][0]["key"] == "floor_number" and c["matrix"]["3,3"] == "P3"
    r = client.post("/api/records/incident", json={"title": "Printer jam on floor 3", "impact": 3, "urgency": 3, "use_ai": False}, headers=agent).json()
    assert r["priority"] == "P3"
    client.put("/api/ticketing/config", json={"matrix": {}}, headers=admin)
    assert client.put("/api/ticketing/config", json={"fields": [{"label": "Bad", "type": "blob"}]}, headers=admin).status_code == 400

def test_tasks_watchers_history(client, agent, user):
    r = mk(client, agent, "Laptop battery swelling")
    r = client.post(f"/api/records/incident/{r['id']}/tasks", json={"title": "Order replacement"}, headers=agent).json()
    t = r["data"]["tasks"][0]; assert not t["done"]
    r = client.post(f"/api/records/incident/{r['id']}/tasks/{t['id']}/toggle", headers=agent).json()
    assert r["data"]["tasks"][0]["done"]
    r = client.post(f"/api/records/incident/{r['id']}/watch", headers=agent).json()
    assert r["data"]["watchers"]
    h = client.get(f"/api/records/incident/{r['id']}/history", headers=agent).json()
    assert [x["action"] for x in h][:3] == ["create", "task.add", "task.done"]

def test_duplicates_and_merge(client, agent):
    a = mk(client, agent, "Outlook keeps crashing on startup", "outlook crashing startup")
    b = mk(client, agent, "Outlook crashing at startup every morning", "outlook crashing startup")
    d = client.get(f"/api/records/incident/{b['id']}/duplicates", headers=agent).json()
    assert any(x["id"] == a["id"] for x in d)
    client.post(f"/api/records/incident/{b['id']}/comments", json={"body": "Happens after the update"}, headers=agent)
    m = client.post(f"/api/records/incident/{b['id']}/merge", json={"into": a["id"]}, headers=agent).json()
    assert m["id"] == a["id"] and any("Happens after the update" in c["body"] for c in m["comments"])
    src = client.get(f"/api/records/incident/{b['id']}", headers=agent).json()
    assert src["data"]["merged_into"] == a["number"] and src["state"] in ("cancelled", "closed", "resolved")
    assert client.post(f"/api/records/incident/{a['id']}/merge", json={"into": a["id"]}, headers=agent).status_code == 400

def test_spam_and_bulk(client, agent, user):
    s = mk(client, agent, "WIN A FREE PHONE click here")
    assert client.post(f"/api/records/incident/{s['id']}/spam", headers=agent).json()["data"]["spam"]
    x, y = mk(client, agent, "Bulk one"), mk(client, agent, "Bulk two")
    r = client.post("/api/records/incident/bulk", json={"ids": [x["id"], y["id"]], "priority": "P2"}, headers=agent).json()
    assert len(r["updated"]) == 2
    assert client.post("/api/records/incident/bulk", json={"ids": [x["id"]], "priority": "P1"}, headers=user).status_code == 403

def test_saved_views(client, agent):
    v = client.post("/api/views", json={"name": "My P1s", "filters": {"priority": "P1", "mine": True, "evil": 1}}, headers=agent).json()
    assert v[-1]["filters"] == {"priority": "P1", "mine": True}
    assert client.delete(f"/api/views/{v[-1]['id']}", headers=agent).json() == v[:-1]

def test_conflict_and_live_events(client, agent):
    r = mk(client, agent, "Conflict check")
    cur = client.get("/api/live/since", headers=agent).json()["cursor"]
    ok = client.patch(f"/api/records/incident/{r['id']}", json={"title": "Conflict check v2", "expected_updated_at": r["updated_at"]}, headers=agent)
    assert ok.status_code == 200
    stale = client.patch(f"/api/records/incident/{r['id']}", json={"title": "v3", "expected_updated_at": "2000-01-01T00:00:00"}, headers=agent)
    assert stale.status_code == 409
    ev = client.get("/api/live/since", params={"cursor": cur}, headers=agent).json()["events"]
    assert any(e["id"] == r["id"] and e["event"] == "updated" for e in ev)
