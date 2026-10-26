from datetime import timedelta
def T(): return {"id": "t", "type": "trigger", "data": {}}
def A(i, **d): return {"id": i, "type": "action", "data": d}
def C(i, **d): return {"id": i, "type": "condition", "data": d}
def E(a, b, h=None): return {"source": a, "target": b, **({"sourceHandle": h} if h else {})}
def wf(client, h, **kw): return client.post("/api/workflows", json={"name": "wf", "trigger": "created", **kw}, headers=h)
def inc(client, h, title, mod="incident", **data): return client.post(f"/api/records/{mod}", json={"title": title, "use_ai": False, "data": data}, headers=h).json()

def test_multi_module_custom_field_condition_and_versioning(client, admin, agent):
    f = client.post("/api/forms/fields", json={"label": "Wf tier", "type": "choice", "options": ["gold", "std"], "modules": ["*"]}, headers=admin).json()
    w = wf(client, admin, modules=["incident", "problem"], nodes=[T(), C("c", field="wf_tier", op="eq", value="gold"), A("a", action="set_field", field="priority", value="P1"), A("b", action="add_comment", text="std {number}")],
           edges=[E("t", "c"), E("c", "a", "true"), E("c", "b", "false")]).json()
    assert w["modules"] == ["incident", "problem"] and w["version"] == 1
    assert inc(client, agent, "gold one", wf_tier="gold")["priority"] == "P1"
    assert inc(client, agent, "gold problem", "problem", wf_tier="gold")["priority"] == "P1"
    assert inc(client, agent, "gold change", "change", wf_tier="gold")["priority"] != "P1"
    runs = client.get(f"/api/workflows/{w['id']}/runs", headers=agent).json(); assert len(runs) == 2 and runs[0]["status"] == "done"
    w2 = client.put(f"/api/workflows/{w['id']}", json={**w, "modules": ["*"], "name": "renamed"}, headers=admin).json(); assert w2["version"] == 2
    assert inc(client, agent, "gold change 2", "change", wf_tier="gold")["priority"] == "P1"
    vs = client.get(f"/api/workflows/{w['id']}/versions", headers=agent).json(); assert [v["version"] for v in vs] == [2, 1]
    w3 = client.post(f"/api/workflows/{w['id']}/restore/1", headers=admin).json(); assert w3["version"] == 3 and w3["modules"] == ["incident", "problem"] and w3["name"] == "wf"
    assert not client.post(f"/api/workflows/{w['id']}/toggle", headers=admin).json()["active"]
    assert inc(client, agent, "gold off", wf_tier="gold")["priority"] != "P1"
    client.delete(f"/api/workflows/{w['id']}", headers=admin); client.delete(f"/api/forms/fields/{f['id']}", headers=admin)

def test_validation(client, admin):
    assert wf(client, admin, modules=["nope"], nodes=[T()]).status_code == 400
    assert wf(client, admin, modules=["incident"], trigger="bogus", nodes=[T()]).status_code == 400
    assert wf(client, admin, modules=["incident"], nodes=[T(), A("a", action="explode")], edges=[E("t", "a")]).status_code == 400
    assert wf(client, admin, modules=["incident"], nodes=[T(), A("a", action="webhook", url="file:///etc/passwd")], edges=[E("t", "a")]).status_code == 400
    assert wf(client, admin, modules=["incident"], trigger="field_changed", nodes=[T()]).status_code == 400

def test_state_change_assign_notify_create_related_webhook(client, admin, agent, monkeypatch):
    calls = []
    import app.flowengine as fe
    monkeypatch.setattr(fe.httpx, "post", lambda url, **kw: calls.append((url, kw["json"])) or type("R", (), {"status_code": 200})())
    grp = client.get("/api/groups", headers=agent).json()[0]["name"]
    w = wf(client, admin, modules=["incident"], trigger="state_changed", trigger_cfg={"to_state": "in_progress"},
           nodes=[T(), A("a", action="assign", group=grp), A("n", action="notify", to="requester", text="Working on {number}"), A("p", action="create_record", module="problem", title="RCA for {number}"), A("h", action="webhook", url="https://hooks.example.com/x")],
           edges=[E("t", "a"), E("a", "n"), E("n", "p"), E("p", "h")]).json()
    r = inc(client, agent, "VPN flaps")
    r2 = client.patch(f"/api/records/incident/{r['id']}", json={"title": "VPN flaps again"}, headers=agent).json()
    assert not client.get(f"/api/workflows/{w['id']}/runs", headers=agent).json()
    r2 = client.patch(f"/api/records/incident/{r['id']}", json={"state": "in_progress"}, headers=agent).json()
    assert r2["assignment_group"]["name"] == grp
    full = client.get(f"/api/records/incident/{r['id']}", headers=agent).json()
    assert any(l["module"] == "problem" and "RCA for" in l["title"] for l in full["linked"])
    assert calls and calls[0][0] == "https://hooks.example.com/x" and calls[0][1]["number"] == r["number"]
    run = client.get(f"/api/workflows/{w['id']}/runs", headers=agent).json()[0]; assert run["status"] == "done" and run["record"] == r["number"]
    client.delete(f"/api/workflows/{w['id']}", headers=admin)

def test_wait_and_approval_pause_and_resume(client, admin, agent, db_session=None):
    me = client.get("/api/auth/me", headers=admin).json()
    w = wf(client, admin, modules=["incident"], nodes=[T(), A("w", action="wait", minutes=0), A("ap", action="approval", approver_id=me["id"]), A("yes", action="set_field", field="priority", value="P2"), A("no", action="set_field", field="priority", value="P4")],
           edges=[E("t", "w"), E("w", "ap"), E("ap", "yes", "true"), E("ap", "no", "false")]).json()
    r = inc(client, agent, "Needs sign-off")
    run = client.get(f"/api/workflows/{w['id']}/runs", headers=agent).json()[0]; assert run["status"] == "waiting"
    client.post("/api/workflows/tick", headers=admin)
    run = client.get(f"/api/workflows/{w['id']}/runs", headers=agent).json()[0]; assert run["status"] == "awaiting_approval"
    ap = [a for a in client.get(f"/api/records/incident/{r['id']}", headers=agent).json()["approvals"] if a["state"] == "requested"][0]
    assert client.post(f"/api/approvals/{ap['id']}/decide", json={"approve": True}, headers=admin).status_code == 200
    assert client.post("/api/workflows/tick", headers=admin).json()["resumed"] == 1
    assert client.get(f"/api/records/incident/{r['id']}", headers=agent).json()["priority"] == "P2"
    assert client.get(f"/api/workflows/{w['id']}/runs", headers=agent).json()[0]["status"] == "done"
    client.delete(f"/api/workflows/{w['id']}", headers=admin)

def test_field_changed_and_schedule_and_sla_trigger(client, admin, agent):
    w = wf(client, admin, modules=["incident"], trigger="field_changed", trigger_cfg={"field": "urgency"}, nodes=[T(), A("c", action="add_comment", text="urgency changed")], edges=[E("t", "c")]).json()
    r = inc(client, agent, "Urgency test")
    client.patch(f"/api/records/incident/{r['id']}", json={"title": "x"}, headers=agent)
    assert not client.get(f"/api/workflows/{w['id']}/runs", headers=agent).json()
    client.patch(f"/api/records/incident/{r['id']}", json={"urgency": 1}, headers=agent)
    assert len(client.get(f"/api/workflows/{w['id']}/runs", headers=agent).json()) == 1
    s = wf(client, admin, modules=["incident"], trigger="schedule", trigger_cfg={"every_minutes": 60, "field": "title", "op": "eq", "value": "x"}, nodes=[T(), A("c", action="add_comment", text="nightly")], edges=[E("t", "c")]).json()
    assert client.post("/api/workflows/tick", headers=admin).json()["scheduled"] >= 1
    assert client.post("/api/workflows/tick", headers=admin).json()["scheduled"] == 0  # not due again yet
    sl = wf(client, admin, modules=["*"], trigger="sla_breach", nodes=[T(), A("c", action="add_comment", text="breach")], edges=[E("t", "c")]).json()
    from app import bus
    from app.db import SessionLocal
    from app.models import Record
    db = SessionLocal(); rec = db.get(Record, r["id"]); bus.emit(db, rec, "sla_breach", None, {}); db.commit(); db.close()
    assert len(client.get(f"/api/workflows/{sl['id']}/runs", headers=agent).json()) == 1
    for x in (w, s, sl): client.delete(f"/api/workflows/{x['id']}", headers=admin)
