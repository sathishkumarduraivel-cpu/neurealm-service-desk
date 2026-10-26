def test_explore_pivot_csv(client, agent):
    s = {"module": "incident", "rows": "assignment_group", "cols": "priority", "days": 365}
    r = client.post("/api/analytics/explore", json=s, headers=agent).json()
    assert r["total"] > 0 and r["columns"] and r["matrix"][0]["_total"] >= 1
    assert sum(m["_total"] for m in r["matrix"]) == r["total"]
    c = client.post("/api/analytics/explore.csv", json=s, headers=agent)
    assert c.status_code == 200 and c.text.startswith("assignment_group")
    for m in ("avg_age_hours", "breached_pct", "open"):
        assert client.post("/api/analytics/explore", json={**s, "metric": m, "cols": None}, headers=agent).status_code == 200
    assert client.post("/api/analytics/explore", json={**s, "rows": "password"}, headers=agent).status_code == 400

def test_library_and_boards(client, agent, admin, user):
    assert client.get("/api/analytics/reports", headers=user).status_code == 403
    assert len(client.get("/api/analytics/templates", headers=agent).json()) >= 5
    r = client.post("/api/analytics/reports", json={"name": "Mine", "spec": {"module": "request", "rows": "state"}}, headers=agent).json()
    assert client.get(f"/api/analytics/reports/{r['id']}/run", headers=agent).json()["rows"] is not None
    assert client.get(f"/api/analytics/reports/{r['id']}/csv", headers=agent).status_code == 200
    b = client.post("/api/analytics/boards", json={"name": "B", "widgets": [{"report": r["id"]}, {"report": "nope"}]}, headers=agent).json()
    assert len(b["widgets"]) == 1
    full = client.get(f"/api/analytics/boards/{b['id']}", headers=agent).json()
    assert full["widgets"][0]["data"]["spec"]["module"] == "request"
    seeded = client.get("/api/analytics/boards", headers=agent).json()
    assert any(x["name"] == "Service desk overview" for x in seeded)
    assert client.delete(f"/api/analytics/reports/{r['id']}", headers=agent).status_code == 200
    assert client.get(f"/api/analytics/boards/{b['id']}", headers=agent).json()["widgets"] == []
