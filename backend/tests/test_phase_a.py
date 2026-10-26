from datetime import timedelta
from app.db import SessionLocal
from app.models import Record, now
from app import ai

def test_meta_modules(client, agent):
    m = {x["key"]: x for x in client.get("/api/meta/modules", headers=agent).json()}
    assert {"incident", "ci", "case", "hr_case", "work_order", "sec_incident", "risk", "project", "patch_job"} <= set(m)
    assert m["incident"]["ai"] and m["ci"]["fields"]

def test_sla_escalation_and_notifications(client, agent, admin):
    r = client.post("/api/records/incident", json={"title": "Teams slow", "impact": 2, "urgency": 2, "use_ai": False}, headers=agent).json()
    assert r["priority"] == "P3"
    db = SessionLocal(); rec = db.get(Record, r["id"])
    rec.created_at = now() - timedelta(days=3); rec.sla_due_at = now() - timedelta(hours=1); db.commit(); db.close()
    res = client.post("/api/sla/escalate", headers=agent).json()
    assert res["escalated"] >= 1
    after = client.get(f"/api/records/incident/{r['id']}", headers=agent).json()
    assert after["sla_breached"] and after["priority"] == "P2" and after["data"]["escalation_level"] == 2
    again = client.post("/api/sla/escalate", headers=agent).json()  # idempotent
    assert client.get(f"/api/records/incident/{r['id']}", headers=agent).json()["priority"] == "P2"
    notes = client.get("/api/notifications", headers=admin).json()
    assert any("BREACHED" in n["title"] for n in notes)
    assert client.post(f"/api/notifications/{notes[0]['id']}/read", headers=admin).json()["ok"]

def test_scheduler_job_runs(client):
    from app import scheduler
    scheduler.sla_job()  # job body runs without error

def test_tenant_isolation(client, admin):
    h = {"Authorization": "Bearer " + client.post("/api/auth/login", json={"email": "admin@acme.test", "password": "Acme@123"}).json()["access_token"]}
    assert client.get("/api/records/incident", headers=h).json() == []
    inc = client.get("/api/records/incident", headers=admin).json()[0]
    assert client.get(f"/api/records/incident/{inc['id']}", headers=h).status_code == 404
    mine = client.post("/api/records/incident", json={"title": "Acme laptop broken"}, headers=h).json()
    assert all(x["id"] != mine["id"] for x in client.get("/api/records/incident", headers=admin).json())
    assert len(client.get("/api/users", headers=h).json()) == 1

def test_sso_config(client):
    c = client.get("/api/auth/sso/config").json()
    assert c["enabled"] is False and "azuread" in c["supported"]
    assert client.get("/api/auth/sso/login").status_code == 501

def test_ai_calibration():
    assert ai.calibrate(0, 0, False) == 0.3
    single = ai.rule_triage("VPN outage for Chennai office")
    assert single["confidence"] >= 0.6 and single["category"] == "network"
    ambiguous = ai.rule_triage("printer email")  # two categories tie
    assert ambiguous["confidence"] < single["confidence"]
    assert ai.calibrate(3, 3, True) <= 0.97
