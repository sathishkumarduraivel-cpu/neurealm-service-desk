import httpx
from app.routers import aiops

def test_off_by_default_and_rules_everywhere(client, admin, agent, user):
    st = client.get("/api/ai/status", headers=user).json(); assert st["mode"] == "rules" and st["name"] == "Neurealm AI"
    p = client.get("/api/ai/provider", headers=admin).json(); assert p["enabled"] is False and "api_key" not in p
    assert client.get("/api/ai/provider", headers=agent).status_code == 403
    assert client.post("/api/ai/provider/test", headers=admin).json()["ok"] is False
    a = client.post("/api/ai/assistant", json={"message": "VPN is not working"}, headers=user).json()
    assert a["engine"] == "rules" and a["answer"] and any(x["type"] == "create_incident" for x in a["actions"])
    inc = client.post("/api/records/incident", json={"title": "Outlook keeps crashing when opening calendar", "description": "Since this morning. Error on start."}, headers=user).json()
    a2 = client.post("/api/ai/assistant", json={"message": f"what's the status of {inc['number']}?"}, headers=user).json(); assert inc["number"] in a2["answer"]
    s = client.post(f"/api/ai/tickets/incident/{inc['id']}/summary", headers=agent).json(); assert s["engine"] == "rules" and "•" in s["summary"]
    r = client.post(f"/api/ai/tickets/incident/{inc['id']}/reply", headers=agent).json(); assert r["reply"].startswith("Hi ")
    assert isinstance(client.get(f"/api/ai/tickets/incident/{inc['id']}/similar", headers=agent).json(), list)
    assert client.post(f"/api/ai/tickets/incident/{inc['id']}/summary", headers=user).status_code == 403
    w = client.post("/api/ai/write", json={"text": "  hi i cant login .  please help", "mode": "improve"}, headers=agent).json(); assert w["text"].startswith("Hi I") and w["text"].endswith(".")
    assert client.post("/api/ai/write", json={"text": "x", "mode": "poem"}, headers=agent).status_code == 400
    rep = client.post("/api/ai/report", json={"question": "open incidents by priority last 90 days"}, headers=agent).json()
    assert rep["spec"] == {"module": "incident", "group_by": "priority", "days": 90, "filter": {"open": True}} and rep["chart"] == "bar" and rep["total"] >= 1
    assert client.post("/api/ai/report", json={"question": "changes by month last 12 months"}, headers=agent).json()["chart"] == "line"

def test_provider_on_degrades_gracefully_and_masks_key(client, admin, agent, monkeypatch):
    assert client.put("/api/ai/provider", json={"enabled": True, "base_url": "ftp://x"}, headers=admin).status_code == 400
    p = client.put("/api/ai/provider", json={"enabled": True, "base_url": "https://llm.invalid/v1", "model": "m", "api_key": "sk-secret-123"}, headers=admin).json()
    assert p["has_key"] and "sk-secret" not in str(p)
    def boom(*a, **k): raise httpx.ConnectError("no network")
    monkeypatch.setattr(aiops.httpx, "post", boom)
    a = client.post("/api/ai/assistant", json={"message": "password reset"}, headers=agent).json(); assert a["engine"] == "rules"
    class R:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "Try restarting the VPN client."}}]}
    monkeypatch.setattr(aiops.httpx, "post", lambda *a, **k: R())
    assert client.post("/api/ai/assistant", json={"message": "vpn"}, headers=agent).json() == {**client.post("/api/ai/assistant", json={"message": "vpn"}, headers=agent).json(), "engine": "llm", "answer": "Try restarting the VPN client."}
    assert client.get("/api/ai/status", headers=agent).json()["mode"] == "llm"
    client.put("/api/ai/provider", json={"enabled": True, "features": {"assistant": False}}, headers=admin)
    assert client.post("/api/ai/assistant", json={"message": "vpn"}, headers=agent).json()["engine"] == "rules"
    client.put("/api/ai/provider", json={"enabled": False, "clear_key": True}, headers=admin)
    assert client.get("/api/ai/status", headers=agent).json()["mode"] == "rules"
