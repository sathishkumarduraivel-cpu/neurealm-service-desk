def ci_by(client, h, name):
    return next(c for c in client.get("/api/records/ci", headers=h).json() if c["title"] == name)

def test_cmdb_graph_and_quality(client, agent):
    erp = ci_by(client, agent, "ERP Application"); sw = ci_by(client, agent, "core-sw-01")
    g = client.get(f"/api/cmdb/ci/{sw['id']}/graph", headers=agent).json()
    assert erp["id"] in g["impacted"]  # switch outage impacts ERP app transitively
    q = client.get("/api/cmdb/quality", headers=agent).json()
    assert q["ci_count"] >= 10 and 0 < q["avg_dq_score"] <= 100 and q["worst"][0]["dq_score"] <= q["avg_dq_score"]
    assert client.post("/api/cmdb/relations", json={"parent_id": erp["id"], "child_id": erp["id"]}, headers=agent).status_code == 400

def test_discovery_import_idempotent(client, agent):
    body = {"source": "scan-1", "items": [{"name": "web-01", "ci_class": "server", "ip": "10.9.9.9", "os": "Ubuntu", "serial": "W1"},
                                          {"name": "build-srv-02", "ip": "10.10.3.40", "os": "Debian 12", "owner": "DevOps"}],
            "relations": [{"parent": "web-01", "child": "core-sw-01", "type": "connects_to"}]}
    r = client.post("/api/cmdb/discovery", json=body, headers=agent).json()
    assert r == {"created": 1, "updated": 1, "relations": 1}
    r2 = client.post("/api/cmdb/discovery", json=body, headers=agent).json()
    assert r2["created"] == 0 and r2["relations"] == 0
    b = ci_by(client, agent, "build-srv-02")
    assert b["data"]["os"] == "Debian 12" and b["data"]["discovered"]

def test_event_correlation_noise_reduction(client, agent):
    ev = {"source": "prometheus", "node": "core-sw-01", "metric": "interface_down", "severity": "critical", "message": "Gi1/0/1 down"}
    first = client.post("/api/events", json=ev, headers=agent).json()[0]
    assert first["action"] == "incident_created" and first["incident_id"]
    dups = client.post("/api/events", json=[ev] * 5, headers=agent).json()
    assert all(d["action"] == "deduplicated" and d["incident_id"] == first["incident_id"] for d in dups)
    # downstream CI alert correlates to same incident (topology)
    down = client.post("/api/events", json={"source": "datadog", "node": "erp-app-01", "metric": "http_5xx", "severity": "major"}, headers=agent).json()[0]
    assert down["action"] == "correlated" and down["incident_id"] == first["incident_id"]
    warn = client.post("/api/events", json={"source": "newrelic", "node": "hr-portal-01", "metric": "cpu", "severity": "warning"}, headers=agent).json()[0]
    assert warn["incident_id"] is None
    st = client.get("/api/events/stats", headers=agent).json()
    assert st["raw_events"] >= 8 and st["noise_reduction_pct"] > 50
    assert client.post("/api/events", json={**ev, "severity": "clear"}, headers=agent).json()[0]["action"] == "cleared"
    inc = client.get(f"/api/records/incident/{first['incident_id']}", headers=agent).json()
    assert inc["data"]["auto_created"] and len(inc["data"]["event_ids"]) >= 2

def test_itam_summary(client, agent):
    s = client.get("/api/itam/summary", headers=agent).json()
    comp = {l["product"]: l["compliance"] for l in s["licenses"]}
    assert comp["Adobe Creative Cloud"] == "over_deployed" and comp["Zoom Business"] == "under_utilized"
    assert s["assets"]["total"] >= 8 and s["contracts_expiring"]

def test_costs_anomalies(client, agent):
    c = client.get("/api/costs", headers=agent).json()
    assert len(c["months"]) == 6 and c["current_index"] > 0 and "amount" not in str(c)
    flagged = {(a["provider"], a["service"]) for a in c["anomalies"]}
    assert ("AWS", "EC2") in flagged and ("AWS", "S3") not in flagged
    assert client.post("/api/costs", json=[{"provider": "AWS", "service": "Lambda", "month": c["current_month"], "amount": 1000}], headers=agent).json()["ingested"] == 1

def test_generic_itam_crud(client, agent, user):
    r = client.post("/api/records/license", json={"title": "Figma", "data": {"product": "Figma", "seats_owned": 10, "seats_used": 12}}, headers=agent)
    assert r.status_code == 201 and r.json()["data"]["compliance"] == "over_deployed"
    assert client.post("/api/records/ci", json={"title": "x"}, headers=user).status_code == 403
    assert client.get("/api/records/ci", headers=user).status_code == 403
