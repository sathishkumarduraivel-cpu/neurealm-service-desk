def test_attachments(client, agent, user):
    r = client.post("/api/records/incident", json={"title": "Screen flicker", "use_ai": False}, headers=user).json()
    url = f"/api/records/incident/{r['id']}/attachments"
    a = client.post(url, files={"file": ("shot.png", b"\x89PNG data", "image/png")}, headers=user); assert a.status_code == 201, a.text
    assert client.post(url, files={"file": ("x.exe", b"MZ", "application/octet-stream")}, headers=user).status_code == 400
    assert client.post(url, files={"file": ("big.bin", b"0" * (5 * 1024 * 1024 + 1), "application/octet-stream")}, headers=user).status_code == 413
    lst = client.get(url, headers=agent).json(); assert [x["filename"] for x in lst] == ["shot.png"]
    d = client.get(f"/api/attachments/{lst[0]['id']}", headers=user); assert d.content == b"\x89PNG data" and "attachment" in d.headers["content-disposition"]
    assert client.delete(f"/api/attachments/{lst[0]['id']}", headers=user).status_code == 403
    assert client.delete(f"/api/attachments/{lst[0]['id']}", headers=agent).json()["ok"]
    h = client.get(f"/api/records/incident/{r['id']}/history", headers=agent).json(); assert "attachment.add" in [x["action"] for x in h]
