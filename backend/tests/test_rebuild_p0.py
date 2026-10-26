from app import seed

def test_features_default_off_and_admin_toggle(client, admin, agent):
    f = client.get("/api/features", headers=agent).json()
    assert f and not any(f.values())
    assert client.put("/api/features", json={"fsm": True}, headers=agent).status_code == 403
    r = client.put("/api/features", json={"fsm": True, "bogus": True}, headers=admin).json()
    assert r["fsm"] is True and "bogus" not in r
    assert client.get("/api/features", headers=agent).json()["fsm"] is True
    client.put("/api/features", json={"fsm": False}, headers=admin)

def test_ai_status_rules_fallback(client, agent):
    r = client.get("/api/ai/status", headers=agent).json()
    assert r["name"] == "Neurealm AI" and r["llm_enabled"] is False

def test_no_money_fields_in_registry(client, agent):
    import json
    from app.registry import MODULES
    blob = json.dumps({k: v.get("fields", []) for k, v in MODULES.items()}, default=str)
    assert "INR" not in blob and "₹" not in blob

def test_seed_version_recorded(client):
    assert seed._stored_version() == seed.SEED_VERSION
