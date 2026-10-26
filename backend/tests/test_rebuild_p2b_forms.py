def F(client, h, **kw):
    r = client.post("/api/forms/fields", json=kw, headers=h); return r

def test_designer_crud_types_and_permissions(client, admin, agent):
    assert "multichoice" in client.get("/api/forms/types", headers=agent).json()
    assert F(client, agent, label="Nope").status_code == 403
    assert F(client, admin, label="Bad", type="blob").status_code == 400
    assert F(client, admin, label="Choice no opts", type="choice").status_code == 400
    a = F(client, admin, label="Badge code", type="text", modules=["incident", "request"], show_in_list=True, section="Hardware").json()
    b = F(client, admin, label="Wing", type="choice", options=["Chennai", "Pune"], modules=["*"], default="Chennai").json()
    assert a["key"] == "badge_code" and F(client, admin, label="Badge code").status_code == 409
    inc = [f["key"] for f in client.get("/api/forms/fields?module=incident", headers=agent).json()]
    assert "badge_code" in inc and "wing" in inc
    assert "badge_code" not in [f["key"] for f in client.get("/api/forms/fields?module=change", headers=agent).json()]
    assert client.post("/api/forms/fields/reorder", json={"ids": [b["id"], a["id"]]}, headers=admin).json()["ok"]
    keys = [f["key"] for f in client.get("/api/forms/fields?module=incident", headers=agent).json()]
    assert keys.index("wing") < keys.index("badge_code")
    upd = client.put(f"/api/forms/fields/{a['id']}", json={**a, "hidden": True}, headers=admin).json()
    assert upd["hidden"] and "badge_code" not in [f["key"] for f in client.get("/api/forms/fields?module=incident", headers=agent).json()]
    for x in (a, b): client.delete(f"/api/forms/fields/{x['id']}", headers=admin)

def test_values_validation_required_conditional_filter_export_audit(client, admin, agent):
    ids = [F(client, admin, label="Gadget type", type="choice", options=["Laptop", "Phone"], required=True).json()["id"],
           F(client, admin, label="Serial no", type="text", required=True, condition={"field": "gadget_type", "op": "eq", "value": "Laptop"}).json()["id"],
           F(client, admin, label="Floors", type="multichoice", options=["1", "2", "3"]).json()["id"],
           F(client, admin, label="Seats", type="number", default=1).json()["id"]]
    url = "/api/records/incident"
    r = client.post(url, json={"title": "No device", "use_ai": False}, headers=agent); assert r.status_code == 400 and "Gadget type" in r.text
    r = client.post(url, json={"title": "Laptop w/o serial", "use_ai": False, "data": {"gadget_type": "Laptop"}}, headers=agent); assert r.status_code == 400
    r = client.post(url, json={"title": "Phone ok", "use_ai": False, "data": {"gadget_type": "Phone", "serial_no": "x", "floors": "1,3"}}, headers=agent)
    assert r.status_code == 201, r.text; rec = r.json()
    assert rec["data"]["serial_no"] is None and rec["data"]["floors"] == ["1", "3"] and rec["data"]["seats"] == 1
    assert client.post(url, json={"title": "bad", "use_ai": False, "data": {"gadget_type": "Tablet"}}, headers=agent).status_code == 400
    r = client.patch(f"{url}/{rec['id']}", json={"data": {"seats": "4"}}, headers=agent); assert r.status_code == 200 and r.json()["data"]["seats"] == 4
    assert client.patch(f"{url}/{rec['id']}", json={"data": {"seats": "many"}}, headers=agent).status_code == 400
    h = client.get(f"{url}/{rec['id']}/history", headers=agent).json()
    assert any("data.seats" in str(x.get("details")) for x in h if x["action"] == "update"), h
    lst = client.get(f"{url}?cf_gadget_type=phone", headers=agent).json(); assert [x["id"] for x in lst] == [rec["id"]]
    csv = client.get(f"{url}/export.csv", headers=agent).text
    assert "Gadget type" in csv.splitlines()[0] and "Phone" in csv
    for i in ids: client.delete(f"/api/forms/fields/{i}", headers=admin)

def test_user_and_reference_types(client, admin, agent):
    a = F(client, admin, label="Approver", type="user").json(); b = F(client, admin, label="Parent problem", type="reference", ref_module="problem").json()
    prob = client.post("/api/records/problem", json={"title": "Root cause X", "use_ai": False}, headers=agent).json()
    inc = client.post("/api/records/incident", json={"title": "Linked", "use_ai": False}, headers=agent).json()
    assert client.patch(f"/api/records/incident/{inc['id']}", json={"data": {"parent_problem": inc["id"]}}, headers=agent).status_code == 400
    assert client.patch(f"/api/records/incident/{inc['id']}", json={"data": {"parent_problem": prob["id"], "approver": 999999}}, headers=agent).status_code == 400
    assert client.patch(f"/api/records/incident/{inc['id']}", json={"data": {"parent_problem": prob["id"]}}, headers=agent).json()["data"]["parent_problem"] == prob["id"]
    for x in (a, b): client.delete(f"/api/forms/fields/{x['id']}", headers=admin)
