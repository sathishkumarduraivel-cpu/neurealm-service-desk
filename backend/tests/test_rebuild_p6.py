def test_import_dry_run_then_apply_with_identity(client, agent):
    csv = "Hostname,Class,IP,Serial\nnew-box-01,server,10.9.9.1,SN-NEW-1\nnew-box-02,server,10.9.9.2,\n,server,1.1.1.1,\nweird,toaster,,\n"
    r = client.post("/api/cmdb/import", json={"csv": csv, "mapping": {"Hostname": "name", "Class": "ci_class", "IP": "ip", "Serial": "serial"}}, headers=agent).json()
    assert r["dry_run"] and r["summary"] == {"create": 2, "update": 0, "unchanged": 0, "error": 2}
    before = len(client.get("/api/records/ci", headers=agent).json())
    assert len(client.get("/api/records/ci", headers=agent).json()) == before  # dry run changed nothing
    client.post("/api/cmdb/import", json={"csv": csv, "mapping": {"Hostname": "name", "Class": "ci_class", "IP": "ip", "Serial": "serial"}, "dry_run": False}, headers=agent)
    csv2 = "name,serial,os\nrenamed-box,SN-NEW-1,Ubuntu 24.04\nnew-box-02,,\n"
    r2 = client.post("/api/cmdb/import", json={"csv": csv2}, headers=agent).json()
    assert r2["rows"][0]["action"] == "update" and r2["rows"][0]["rule"] == "serial" and r2["rows"][1]["action"] == "unchanged"

def test_import_limit(client, agent):
    rows = [{"name": f"x{i}"} for i in range(501)]
    assert client.post("/api/cmdb/import", json={"rows": rows}, headers=agent).status_code == 400
    assert client.post("/api/cmdb/import", json={"rows": rows[:500]}, headers=agent).json()["summary"]["create"] == 500

def test_classes_reltypes_identity(client, admin, agent):
    cfg = client.get("/api/cmdb/config", headers=agent).json(); assert cfg["classes"] and cfg["rel_types"]
    assert client.put("/api/cmdb/classes", json=cfg["classes"], headers=agent).status_code == 403
    assert client.put("/api/cmdb/classes", json=[{"key": "Bad Key", "label": "x"}], headers=admin).status_code == 400
    cl = cfg["classes"] + [{"key": "iot_sensor", "label": "IoT sensor", "parent": "network", "attributes": [{"key": "location", "label": "Location", "required": True}]}]
    assert client.put("/api/cmdb/classes", json=cl, headers=admin).status_code == 200
    r = client.post("/api/cmdb/import", json={"rows": [{"name": "temp-1", "ci_class": "iot_sensor"}]}, headers=agent).json(); assert r["summary"]["create"] == 1
    cis = client.get("/api/records/ci", headers=agent).json(); a, b = cis[0]["id"], cis[1]["id"]
    assert client.post("/api/cmdb/relations", json={"parent_id": a, "child_id": b, "rel_type": "loves"}, headers=agent).status_code == 400
    client.put("/api/cmdb/rel-types", json=cfg["rel_types"] + [{"key": "replicates_to", "label": "Replicates to"}], headers=admin)
    assert client.post("/api/cmdb/relations", json={"parent_id": a, "child_id": b, "rel_type": "replicates_to"}, headers=agent).status_code == 201
    assert client.put("/api/cmdb/identity", json=[[]], headers=admin).status_code == 400
    assert client.put("/api/cmdb/identity", json=[["serial"], ["name"]], headers=admin).status_code == 200

def test_impact_health_map(client, agent):
    rels = client.get("/api/cmdb/relations", headers=agent).json(); child = rels[0]["child_id"]
    im = client.get(f"/api/cmdb/ci/{child}/impact", headers=agent).json()
    assert "summary" in im and rels[0]["parent_id"] in [x["id"] for x in im["impacted"]]
    h = client.get("/api/cmdb/health", headers=agent).json(); assert h["rows"] and 0 <= h["rows"][0]["score"] <= 100
    m = client.get("/api/cmdb/service-map", headers=agent).json(); assert m["nodes"] and m["edges"] and "label" in m["edges"][0]

def test_licences_contracts_po_no_money(client, agent):
    lc = client.get("/api/itam/licence-compliance", headers=agent).json(); assert lc["rows"]
    s = str(lc) + str(client.get("/api/itam/contracts", headers=agent).json()) + str(client.get("/api/itam/summary", headers=agent).json())
    for k in ("'value'", "cost", "savings", "price"): assert k not in s
    po = client.post("/api/records/purchase_order", json={"title": "Laptops for new joiners", "description": "", "data": {"vendor": "Dell", "item": "Latitude 7450", "quantity": 3}}, headers=agent).json()
    assert client.post(f"/api/itam/po/{po['id']}/receive", json={}, headers=agent).status_code == 400
    for s_ in ("submitted", "approved", "ordered"): client.patch(f"/api/records/purchase_order/{po['id']}", json={"state": s_}, headers=agent)
    r = client.post(f"/api/itam/po/{po['id']}/receive", json={"quantity": 2}, headers=agent).json(); assert r["state"] == "ordered" and len(r["assets"]) == 2
    assert client.post(f"/api/itam/po/{po['id']}/receive", json={"quantity": 5}, headers=agent).status_code == 400
    assert client.post(f"/api/itam/po/{po['id']}/receive", json={}, headers=agent).json()["state"] == "received"
