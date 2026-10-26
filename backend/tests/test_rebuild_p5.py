from datetime import datetime, timedelta
def mk(client, h, **data):
    return client.post("/api/records/change", json={"title": "Test change", "description": "x", "data": {"rollback_plan": "revert", **data}}, headers=h)
def move(client, h, rid, s): return client.patch(f"/api/records/change/{rid}", json={"state": s}, headers=h)

def test_change_cannot_start_before_approval_and_needs_pir(client, admin, agent):
    c = mk(client, agent).json()
    rk = client.post(f"/api/changes/{c['id']}/risk", json={"prod": True, "users": True, "untested": True, "no_rollback": True}, headers=agent).json()
    assert rk["risk_level"] == "high" and rk["risk_score"] == 80
    move(client, agent, c["id"], "assess"); r = move(client, agent, c["id"], "authorize").json()
    assert len(r["approvals"]) == 2 and r["state"] == "authorize"
    assert "implement" not in r["allowed_transitions"]
    # force through: even if state were scheduled, guard blocks while approvals pending
    from app.db import SessionLocal; from app.models import Record
    db = SessionLocal(); x = db.get(Record, c["id"]); x.state = "scheduled"; db.commit(); db.close()
    bad = move(client, agent, c["id"], "implement"); assert bad.status_code == 400 and "approval" in bad.json()["detail"]
    for a in sorted(r["approvals"], key=lambda a: a["level"]):
        client.post(f"/api/approvals/{a['id']}/decide", json={"approve": True}, headers=admin)
    assert move(client, agent, c["id"], "implement").status_code == 200
    move(client, agent, c["id"], "review")
    assert move(client, agent, c["id"], "closed").status_code == 400
    assert client.post(f"/api/changes/{c['id']}/pir", json={"successful": True, "notes": "Went fine"}, headers=agent).status_code == 200
    assert move(client, agent, c["id"], "closed").json()["state"] == "closed"
    assert client.get("/api/change-ops/stats", headers=agent).json()["reviews"] >= 1

def test_freeze_blocks_scheduling_but_not_emergency(client, admin, agent):
    s = (datetime.utcnow() + timedelta(days=10)).replace(microsecond=0); e = s + timedelta(days=3)
    assert client.put("/api/change-ops/freeze", json=[{"name": "Bad", "start": e.isoformat(), "end": s.isoformat()}], headers=admin).status_code == 400
    assert client.put("/api/change-ops/freeze", json=[{"name": "Year-end", "start": s.isoformat(), "end": e.isoformat()}], headers=agent).status_code == 403
    client.put("/api/change-ops/freeze", json=[{"name": "Year-end", "start": s.isoformat(), "end": e.isoformat()}], headers=admin)
    when = (s + timedelta(days=1)).isoformat()
    r = mk(client, agent, planned_start=when); assert r.status_code == 400 and "freeze" in r.json()["detail"]
    assert mk(client, agent, planned_start=when, change_type="emergency").status_code == 201
    ok = mk(client, agent, planned_start=(e + timedelta(days=1)).isoformat()).json()
    assert client.patch(f"/api/records/change/{ok['id']}", json={"data": {"planned_start": when}}, headers=agent).status_code == 400
    cal = client.get("/api/change-ops/calendar", headers=agent).json(); assert cal["freeze"] and cal["changes"]
    client.put("/api/change-ops/freeze", json=[], headers=admin)

def test_routes_cab_pipeline(client, admin, agent):
    cfg = client.get("/api/change-ops/config", headers=agent).json(); assert cfg["questions"]
    assert client.put("/api/change-ops/routes", json={"normal": {"low": ["boss"]}}, headers=admin).status_code == 400
    routes = cfg["routes"]; routes["normal"]["low"] = ["group:CAB", "admin", "admin"]
    client.put("/api/change-ops/routes", json=routes, headers=admin)
    c = mk(client, agent).json(); client.post(f"/api/changes/{c['id']}/risk", json={}, headers=agent)
    move(client, agent, c["id"], "assess"); assert len(move(client, agent, c["id"], "authorize").json()["approvals"]) == 3
    cab = client.get("/api/change-ops/cab", headers=agent).json(); assert any(x["id"] == c["id"] for x in cab["suggested_agenda"])
    m = client.post("/api/change-ops/cab", json={"title": "Weekly CAB", "date": "2026-11-02T10:00", "change_ids": [c["id"]]}, headers=agent).json()
    m2 = client.post(f"/api/change-ops/cab?mid={m['id']}", json={**m, "minutes": "Approved"}, headers=agent).json(); assert m2["minutes"] == "Approved"
    p = client.get("/api/change-ops/pipeline", headers=agent).json(); assert [c["state"] for c in p][0] == "new"
    routes["normal"]["low"] = ["admin"]; client.put("/api/change-ops/routes", json=routes, headers=admin)

def test_problem_rca_trends_and_major_incident(client, agent, user):
    p = client.post("/api/records/problem", json={"title": "VPN drops", "description": "x"}, headers=agent).json()
    assert client.put(f"/api/problems/{p['id']}/rca", json={"method": "x"}, headers=agent).status_code == 400
    r = client.put(f"/api/problems/{p['id']}/rca", json={"whys": ["a", "b"], "root_cause": "Expired cert"}, headers=agent).json()
    assert r["data"]["root_cause"] == "Expired cert"
    assert "clusters" in client.get("/api/problems/trends", headers=agent).json()
    i = client.post("/api/records/incident", json={"title": "Email down for everyone", "description": "x"}, headers=user).json()
    assert client.post(f"/api/incidents/{i['id']}/comms", json={"message": "hi"}, headers=agent).status_code == 400
    assert client.post(f"/api/incidents/{i['id']}/major", json={"declare": True, "bridge": "https://meet.example/abc"}, headers=user).status_code == 403
    m = client.post(f"/api/incidents/{i['id']}/major", json={"declare": True}, headers=agent).json(); assert m["priority"] == "P1"
    assert len(client.post(f"/api/incidents/{i['id']}/comms", json={"message": "We're on it"}, headers=agent).json()) == 1
    assert any(x["id"] == i["id"] for x in client.get("/api/major-incidents", headers=agent).json())
    rv = client.post(f"/api/incidents/{i['id']}/major-review", json={"summary": "Mail relay died", "problem": True}, headers=agent).json()
    assert rv["problem_id"]
