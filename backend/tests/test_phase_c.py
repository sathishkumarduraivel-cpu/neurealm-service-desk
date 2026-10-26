def find(client, h, module, title_part):
    return next(r for r in client.get(f"/api/records/{module}", headers=h).json() if title_part in r["title"])

def test_csm_entitlement_and_account_360(client, agent, user):
    acc = find(client, agent, "account", "Chola")
    c = client.post("/api/records/case", json={"title": "Bot not answering in Tamil", "data": {"account": acc["number"], "channel": "portal"}}, headers=user).json()
    assert c["data"]["entitled"] and c["data"]["sla_tier"] == "24x7" and c["priority"] in ("P1", "P2") and c["sla_due_at"]
    nc = client.post("/api/records/case", json={"title": "General question", "data": {"account": "ACC9999999"}}, headers=user).json()
    assert nc["data"]["entitled"] is False
    ov = client.get(f"/api/csm/accounts/{acc['id']}/overview", headers=agent).json()
    assert len(ov["contacts"]) == 2 and len(ov["entitlements"]) == 1 and ov["open_cases"] >= 2 and 0 <= ov["health_score"] <= 100
    mine = client.get("/api/records/case", headers=user).json()
    assert all(x["requester"]["email"] == "user@neurealm.com" for x in mine)

def test_hr_onboarding_lifecycle(client, agent):
    r = client.post("/api/hr/lifecycle", json={"type": "onboarding", "employee": "Test Joiner", "date": "2026-11-01"}, headers=agent).json()
    assert r["tasks"] == 6
    cid = r["case"]["id"]
    tasks = client.get(f"/api/records/hr_case/{cid}/children", headers=agent).json()
    assert len(tasks) == 6 and all(t["assignment_group"] for t in tasks)
    for t in tasks:
        for s in ("in_progress", "done"):
            assert client.patch(f"/api/records/task/{t['id']}", json={"state": s}, headers=agent).status_code == 200
    assert client.get(f"/api/records/hr_case/{cid}", headers=agent).json()["state"] == "resolved"
    assert client.post("/api/hr/lifecycle", json={"type": "bogus", "employee": "x"}, headers=agent).status_code == 400

def test_workplace_reservation_conflict_and_visitors(client, agent, user):
    av = client.get("/api/workplace/availability", params={"day": "2026-12-01"}, headers=user).json()
    assert all(s["free"] for s in av)
    body = {"title": "Planning", "data": {"space": "Huddle 2", "start": "2026-12-01T10:00", "end": "2026-12-01T11:00"}}
    assert client.post("/api/records/reservation", json=body, headers=user).json()["state"] == "confirmed"
    clash = client.post("/api/records/reservation", json={**body, "data": {**body["data"], "start": "2026-12-01T10:30", "end": "2026-12-01T11:30"}}, headers=user).json()
    assert clash["state"] == "conflict"
    ok = client.post("/api/records/reservation", json={**body, "data": {**body["data"], "start": "2026-12-01T11:00", "end": "2026-12-01T12:00"}}, headers=user).json()
    assert ok["state"] == "confirmed"
    assert not next(s for s in client.get("/api/workplace/availability", params={"day": "2026-12-01"}, headers=user).json() if s["space"] == "Huddle 2")["free"]
    assert len(client.get("/api/workplace/visitors/today", headers=agent).json()) >= 3
    fr = client.post("/api/records/facility_request", json={"title": "Leaking tap", "data": {"facility_type": "plumbing"}}, headers=user).json()
    assert fr["sla_due_at"]

def test_fsm_dispatch_skill_matching(client, agent):
    wo = client.post("/api/records/work_order", json={"title": "Fix CCTV", "data": {"skill": "cctv", "duration_h": 3}}, headers=agent).json()
    d = client.post(f"/api/fsm/dispatch/{wo['id']}", headers=agent).json()
    assert d["state"] == "scheduled" and d["data"]["technician"] == "Suresh Babu" and d["data"]["skill_match"]
    res = client.post("/api/fsm/optimize", headers=agent).json()
    assert len(res["scheduled"]) >= 3
    b = client.get("/api/fsm/board", headers=agent).json()
    assert not b["unassigned"] and len(b["technicians"]) == 2
    printer = next(j for t in b["technicians"] for j in t["jobs"] if "Printer" in j["title"])
    assert printer["data"]["technician"] == "Anitha Rajan"
    # no double-booking per technician
    for t in b["technicians"]:
        starts = [j["data"]["scheduled_start"] for j in t["jobs"]]
        assert len(starts) == len(set(starts))
