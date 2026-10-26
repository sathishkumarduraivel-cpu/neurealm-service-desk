from app import totp

def login(client, email, pw):
    return client.post("/api/auth/login", json={"email": email, "password": pw}).json()

def test_totp_rfc_vector():
    # RFC 6238 SHA1 test secret "12345678901234567890" at T=59 -> 94287082 (8 digits) -> 287082 (6)
    import base64
    sec = base64.b32encode(b"12345678901234567890").decode()
    assert totp.now_code(sec, at=59) == "287082"
    assert totp.verify(sec, "287082", at=59) and not totp.verify(sec, "000000", at=59)

def test_2fa_enrol_login_and_disable(client):
    s = login(client, "agent@neurealm.com", "Agent@123"); h = {"Authorization": f"Bearer {s['access_token']}"}
    sec = client.post("/api/me/2fa/setup", headers=h).json()
    assert sec["otpauth"].startswith("otpauth://totp/Neurealm%20Service%20Desk:")
    assert client.post("/api/me/2fa/enable", json={"code": "000000"}, headers=h).status_code == 400
    assert client.post("/api/me/2fa/enable", json={"code": totp.now_code(sec["secret"])}, headers=h).json()["totp_enabled"]
    ch = login(client, "agent@neurealm.com", "Agent@123")
    assert ch["mfa_required"] and "access_token" not in ch
    assert client.post("/api/auth/mfa", json={"mfa_token": ch["mfa_token"], "code": "111111"}).status_code == 401
    # an mfa token cannot be used as an access token
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {ch['mfa_token']}"}).status_code == 401
    ok = client.post("/api/auth/mfa", json={"mfa_token": ch["mfa_token"], "code": totp.now_code(sec["secret"])}).json()
    h2 = {"Authorization": f"Bearer {ok['access_token']}"}
    assert client.get("/api/me/security", headers=h2).json()["totp_enabled"]
    assert not client.post("/api/me/2fa/disable", json={"code": totp.now_code(sec["secret"])}, headers=h2).json()["totp_enabled"]
    assert "access_token" in login(client, "agent@neurealm.com", "Agent@123")

def test_registration_toggle_and_domain(client, admin):
    r = client.post("/api/auth/register", json={"email": "signup.p1@neurealm.com", "full_name": "New Person", "password": "Welcome@123"})
    assert r.status_code == 403
    assert client.put("/api/admin/auth-settings", json={"registration": True}, headers=admin).json()["registration"]
    assert client.get("/api/auth/config").json()["registration"]
    assert client.post("/api/auth/register", json={"email": "x@gmail.com", "full_name": "X Y", "password": "Welcome@123"}).status_code == 400
    r = client.post("/api/auth/register", json={"email": "signup.p1@neurealm.com", "full_name": "New Person", "password": "Welcome@123"}).json()
    assert r["user"]["role"] == "end_user"
    assert client.post("/api/auth/register", json={"email": "signup.p1@neurealm.com", "full_name": "New Person", "password": "Welcome@123"}).status_code == 409
    client.put("/api/admin/auth-settings", json={"registration": False}, headers=admin)

def test_api_keys(client, agent, user):
    k = client.post("/api/me/api-keys", json={"name": "CI bot"}, headers=agent).json()
    assert k["key"].startswith("nrsd_")
    kh = {"Authorization": f"Bearer {k['key']}"}
    assert client.get("/api/auth/me", headers=kh).json()["email"] == "agent@neurealm.com"
    assert any(x["id"] == k["id"] for x in client.get("/api/me/security", headers=agent).json()["api_keys"])
    assert client.post("/api/me/api-keys", json={"name": "x"}, headers=user).status_code == 403
    client.delete(f"/api/me/api-keys/{k['id']}", headers=agent)
    assert client.get("/api/auth/me", headers=kh).status_code == 401

def test_impersonation(client, admin, agent):
    users = client.get("/api/users", headers=admin).json()
    emp = next(u for u in users if u["email"] == "user@neurealm.com")
    assert client.post(f"/api/admin/impersonate/{emp['id']}", headers=agent).status_code == 403
    s = client.post(f"/api/admin/impersonate/{emp['id']}", headers=admin).json()
    assert s["user"]["email"] == "user@neurealm.com" and s["impersonator"]
    ih = {"Authorization": f"Bearer {s['access_token']}"}
    assert client.get("/api/me/security", headers=ih).json()["impersonator"] == s["impersonator"]
    back = client.post("/api/admin/impersonate/stop", headers=ih).json()
    assert back["user"]["email"] == "admin@neurealm.com"
    acts = [a["action"] for a in client.get("/api/audit", params={"limit": 50}, headers=admin).json()]
    assert "impersonate.start" in acts and "impersonate.stop" in acts

def test_roles_and_groups(client, admin, agent):
    r = client.get("/api/roles", headers=agent).json()
    assert {x["key"] for x in r["roles"]} == {"admin", "agent", "end_user"} and r["permissions"]
    g = client.post("/api/admin/groups", json={"name": "Network Team", "description": "LAN and WAN"}, headers=admin).json()
    assert client.patch(f"/api/admin/groups/{g['id']}", json={"name": "Network Ops", "description": ""}, headers=admin).json()["name"] == "Network Ops"
    assert client.post("/api/admin/groups", json={"name": "Nope"}, headers=agent).status_code == 403
