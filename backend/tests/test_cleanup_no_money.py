import json
from app.hooks import MONEY_KEYS

def _keys(o, acc):
    if isinstance(o, dict):
        for k, v in o.items(): acc.add(k); _keys(v, acc)
    elif isinstance(o, list):
        for v in o: _keys(v, acc)
    return acc

def test_no_money_fields_anywhere(client, admin):
    bad = set(MONEY_KEYS) - {"value"}
    for path in ["/api/spm/portfolio", "/api/records/asset", "/api/records/contract", "/api/records/demand", "/api/records/project"]:
        r = client.get(path, headers=admin)
        assert r.status_code != 404, path
        assert r.status_code == 200, path
        assert not (_keys(r.json(), set()) & bad), path

def test_money_scrubbed_on_create(client, admin):
    r = client.post("/api/records/project", json={"title": "P", "data": {"budget": 5, "spent": 2, "planned_pct": 50, "percent_complete": 20}}, headers=admin)
    assert r.status_code in (200, 201), r.text
    d = r.json()["data"]; assert "budget" not in d and "spent" not in d and d["health"] == "red"
