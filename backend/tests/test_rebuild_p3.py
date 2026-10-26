from datetime import datetime
from app.routers.serviceops import add_business_minutes

CAL = {"enabled": True, "tz_offset_min": 330, "days": [0, 1, 2, 3, 4], "start": "09:00", "end": "18:00", "holidays": ["2026-10-27"]}

def test_business_minutes_math():
    # Mon 2026-10-26 17:00 IST = 11:30 UTC. 120 business minutes -> 60 today, Tue is holiday, Wed 10:00 IST = 04:30 UTC
    assert add_business_minutes(datetime(2026, 10, 26, 11, 30), 120, CAL) == datetime(2026, 10, 28, 4, 30)
    # Sat 2026-10-31 10:00 IST -> Mon 09:30 IST (04:00 UTC)
    assert add_business_minutes(datetime(2026, 10, 31, 4, 30), 30, CAL) == datetime(2026, 11, 2, 4, 0)
    # before hours: Mon 07:00 IST -> starts 09:00
    assert add_business_minutes(datetime(2026, 10, 26, 1, 30), 60, CAL) == datetime(2026, 10, 26, 4, 30)

def test_calendar_and_escalation_config(client, admin, agent):
    assert client.put("/api/service-ops/calendar", json=CAL, headers=agent).status_code == 403
    assert client.put("/api/service-ops/calendar", json={**CAL, "end": "08:00"}, headers=admin).status_code == 400
    assert client.put("/api/service-ops/calendar", json={**CAL, "holidays": ["soon"]}, headers=admin).status_code == 400
    c = client.put("/api/service-ops/calendar", json=CAL, headers=admin).json(); assert c["enabled"] and c["holidays"] == ["2026-10-27"]
    r = client.post("/api/records/incident", json={"title": "Biz hours SLA", "use_ai": False}, headers=agent).json()
    p = client.post("/api/service-ops/preview-due?minutes=600", headers=agent).json(); assert p["business"] > p["wall_clock"]
    client.put("/api/service-ops/calendar", json={**CAL, "enabled": False}, headers=admin)
    assert client.put("/api/service-ops/escalation", json={"warn_pct": 0}, headers=admin).status_code == 400
    assert client.put("/api/service-ops/escalation", json={"warn_pct": 50, "bump_priority": False}, headers=admin).json()["warn_pct"] == 50
    client.put("/api/service-ops/escalation", json={"warn_pct": 75}, headers=admin)
    assert r["sla_due_at"]

def _group_with_members(client, admin, n=2):
    gs = client.get("/api/groups", headers=admin).json(); us = client.get("/api/users", headers=admin).json()
    for g in gs:
        m = [u for u in us if u.get("group_id") == g["id"] and u["role"] != "end_user" and u.get("active", True)]
        if len(m) >= n: return g, m
    raise AssertionError("no group with members")

def test_round_robin_least_loaded_and_on_call(client, admin, agent):
    g, members = _group_with_members(client, admin)
    assert client.put("/api/service-ops/policies", json={"policies": {g["name"]: "teleport"}}, headers=admin).status_code == 400
    client.put("/api/service-ops/policies", json={"policies": {g["name"]: "round_robin"}}, headers=admin)
    got = []
    for i in range(len(members) + 1):
        r = client.post("/api/records/incident", json={"title": f"RR {i}", "use_ai": False}, headers=agent).json()
        r = client.patch(f"/api/records/incident/{r['id']}", json={"assignment_group_id": g["id"]}, headers=agent).json()
        got.append(r["assignee"]["id"])
    assert len(set(got[:len(members)])) == len(members) and got[len(members)] == got[0]
    client.put("/api/service-ops/policies", json={"policies": {g["name"]: "least_loaded"}}, headers=admin)
    r = client.post("/api/records/incident", json={"title": "LL", "use_ai": False}, headers=agent).json()
    assert client.patch(f"/api/records/incident/{r['id']}", json={"assignment_group_id": g["id"]}, headers=agent).json()["assignee"]["id"] in [m["id"] for m in members]
    assert client.post("/api/service-ops/oncall", json={"group": g["name"], "user_id": members[1]["id"], "start": "2026-01-01T00:00", "end": "2025-01-01T00:00"}, headers=admin).status_code == 400
    rota = client.post("/api/service-ops/oncall", json={"group": g["name"], "user_id": members[1]["id"], "start": "2020-01-01T00:00", "end": "2099-01-01T00:00"}, headers=admin).json()
    assert client.get(f"/api/service-ops/oncall/now?group={g['name']}", headers=agent).json()[g["name"]]["user_id"] == members[1]["id"]
    client.put("/api/service-ops/policies", json={"policies": {g["name"]: "on_call"}}, headers=admin)
    r = client.post("/api/records/incident", json={"title": "OC", "use_ai": False}, headers=agent).json()
    assert client.patch(f"/api/records/incident/{r['id']}", json={"assignment_group_id": g["id"]}, headers=agent).json()["assignee"]["id"] == members[1]["id"]
    client.delete(f"/api/service-ops/oncall/{rota[-1]['id']}", headers=admin); client.put("/api/service-ops/policies", json={"policies": {}}, headers=admin)
