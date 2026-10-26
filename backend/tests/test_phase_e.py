import hmac, hashlib, json

def mk(client, h, title, **kw):
    return client.post("/api/records/incident", json={"title": title, **kw}, headers=h).json()

def test_autoresolve_low_risk_autonomous(client, agent):
    inc = mk(client, agent, "Account locked - forgot password", description="Cannot login, account locked after reset")
    r = client.post(f"/api/autoresolve/{inc['id']}", headers=agent).json()
    assert r["run"]["state"] == "resolved" and r["run"]["playbook"] == "password_reset" and r["run"]["confidence"] >= 0.6
    rec = client.get(f"/api/records/incident/{inc['id']}", headers=agent).json()
    assert rec["state"] == "resolved" and rec["data"]["auto_resolved"] and any("🤖" in c["body"] for c in rec["comments"])

def test_autoresolve_high_risk_needs_human(client, agent, admin):
    inc = mk(client, agent, "ERP application down - service error for finance")
    r = client.post(f"/api/autoresolve/{inc['id']}", headers=agent).json()
    assert r["run"]["state"] == "awaiting_approval" and r["record"]["state"] != "resolved"
    rec = client.get(f"/api/records/incident/{inc['id']}", headers=agent).json()
    ap = next(a for a in rec["approvals"] if a["state"] == "requested")
    done = client.post(f"/api/approvals/{ap['id']}/decide", json={"approve": True}, headers=admin).json()
    assert done["state"] == "resolved" and done["data"]["playbook"] == "service_restart"

def test_autoresolve_threshold_and_dry_run(client, agent, admin):
    inc = mk(client, agent, "Printer offline on 2nd floor")
    hi = client.post(f"/api/autoresolve/{inc['id']}", params={"threshold": 0.99}, headers=agent).json()
    assert hi["run"]["state"] == "escalated" and hi["record"]["state"] != "resolved"
    dry = client.post(f"/api/autoresolve/{inc['id']}", params={"dry_run": True}, headers=agent).json()
    assert dry["run"]["state"] == "dry_run" and dry["run"]["steps"]
    nm = mk(client, agent, "Quarterly budget question")
    assert client.post(f"/api/autoresolve/{nm['id']}", headers=agent).json()["run"]["state"] == "no_match"
    client.put("/api/autoresolve/settings", json={"enabled": False}, headers=admin)
    assert client.post(f"/api/autoresolve/{inc['id']}", headers=agent).status_code == 423
    client.put("/api/autoresolve/settings", json={"enabled": True}, headers=admin)
    st = client.get("/api/autoresolve/stats", headers=agent).json()
    assert st["auto_resolved"] >= 2 and st["autonomous_resolution_rate_pct"] > 0

def test_workflow_engine_seeded_and_crud(client, agent, admin):
    p1 = mk(client, agent, "Total outage", impact=1, urgency=1, use_ai=False)
    rec = client.get(f"/api/records/incident/{p1['id']}", headers=agent).json()
    assert any("Major incident process" in c["body"] for c in rec["comments"])
    sec = mk(client, agent, "Phishing email with suspicious link")
    assert sec["category"] == "security" and sec["assignment_group"]["name"] == "Security Ops"
    wf = {"name": "Tag VIP", "module": "incident", "trigger": "created", "nodes": [{"id": "t", "type": "trigger", "data": {}}, {"id": "c", "type": "condition", "data": {"field": "title", "op": "contains", "value": "ceo"}},
          {"id": "a", "type": "action", "data": {"action": "set_field", "field": "vip", "value": True}}], "edges": [{"source": "t", "target": "c"}, {"source": "c", "target": "a", "sourceHandle": "true"}]}
    assert client.post("/api/workflows", json=wf, headers=agent).status_code == 403
    w = client.post("/api/workflows", json=wf, headers=admin).json()
    vip = mk(client, agent, "CEO laptop broken")
    assert vip["data"].get("vip") is True and not mk(client, agent, "Laptop broken")["data"].get("vip")
    trace = client.post(f"/api/workflows/{w['id']}/test", params={"record_id": vip["id"]}, headers=agent).json()["trace"]
    assert [t["type"] for t in trace] == ["trigger", "condition", "action"]
    bad = {**wf, "nodes": wf["nodes"][1:]}
    assert client.post("/api/workflows", json=bad, headers=admin).status_code == 400
    assert client.delete(f"/api/workflows/{w['id']}", headers=admin).json()["ok"]

def test_quality_audit(client, agent):
    s = client.post("/api/quality/audit", headers=agent).json()
    assert s["audited"] >= 5 and 0 < s["avg_score"] <= 100 and s["coverage_pct"] == 100.0
    assert s["by_agent"] and s["top_findings"] and len(s["checks"]) == 7
    auto = next(r for r in client.get("/api/records/incident", headers=agent).json() if r["data"].get("auto_resolved"))
    assert auto["data"]["quality_score"] >= 50

def test_dex(client, agent):
    devs = client.get("/api/dex/devices", headers=agent).json()
    worst = devs[0]; assert worst["score"] < 60 and worst["issues"]
    assert devs[-1]["score"] > worst["score"]
    r = client.post(f"/api/dex/{worst['id']}/remediate", params={"action": "disk_cleanup"}, headers=agent).json()
    assert r["after"] >= r["before"]
    t = client.post(f"/api/dex/{worst['id']}/remediate", params={"action": "memory_upgrade_ticket"}, headers=agent).json()
    assert t["ticket"].startswith("INC")
    assert client.post("/api/dex/telemetry", json=[{"hostname": "NEW-01", "disk_free_pct": 5}], headers=agent).json()["ingested"] == 1
    assert client.get("/api/dex/summary", headers=agent).json()["devices"] == 11

def test_finops_center(client, agent):
    c = client.get("/api/finops/center", headers=agent).json()
    types = {r["type"] for r in c["recommendations"]}
    assert {"rightsizing", "license_reclaim", "anomaly"} <= types and c["open_count"] > 0 and "savings" not in str(c)
    rs = next(r for r in c["recommendations"] if r["type"] == "rightsizing")
    ap = client.post("/api/finops/apply", params={"rec_id": rs["id"]}, headers=agent).json()
    assert ap["record"]["module"] == "change" and ap["recommendation"]["applied"]
    assert client.post("/api/finops/apply", params={"rec_id": rs["id"]}, headers=agent).status_code == 400
    assert client.get("/api/finops/center", headers=agent).json()["applied_count"] >= 1

def test_patch_dry_run_approval_kill_switch(client, agent, admin):
    job = next(j for j in client.get("/api/records/patch_job", headers=agent).json() if "Windows" in j["title"])
    assert client.post(f"/api/patch/{job['id']}/deploy", headers=admin).status_code == 400  # needs dry-run + approval
    d = client.post(f"/api/patch/{job['id']}/dry-run", headers=agent).json()["dry_run"]
    assert len(d["targets"]) >= 3 and d["requires_admin_approval"] and d["waves"][0]["wave"] == "canary"
    assert client.post(f"/api/patch/{job['id']}/approve", headers=agent).status_code == 403
    assert client.post(f"/api/patch/{job['id']}/approve", headers=admin).json()["state"] == "approved"
    assert client.post("/api/patch/kill-switch", json={"engaged": True, "reason": "Bad KB"}, headers=agent).status_code == 403
    assert client.post("/api/patch/kill-switch", json={"engaged": True, "reason": "Bad KB"}, headers=admin).json()["engaged"]
    blocked = client.post(f"/api/patch/{job['id']}/deploy", headers=agent)
    assert blocked.status_code == 423 and "Bad KB" in blocked.json()["detail"]
    client.post("/api/patch/kill-switch", json={"engaged": False}, headers=admin)
    res = client.post(f"/api/patch/{job['id']}/deploy", headers=agent).json()
    assert res["state"] in ("completed", "halted") and res["data"]["deployment"]["results"]

def test_connectors_outbound_inbound(client, agent, admin, user):
    kinds = {a["kind"] for a in client.get("/api/integrations/adapters", headers=agent).json()}
    assert {"chatbot", "sla_assist", "pmo", "quality_audit", "workflow_hub", "teams", "slack", "jira", "servicenow"} <= kinds
    mk(client, agent, "Payroll system outage for everyone")
    logs = client.get("/api/integrations/logs", headers=agent).json()
    assert any(l["connector"].startswith("Teams") and l["direction"] == "out" for l in logs) and any(l["connector"].startswith("Slack") for l in logs)
    assert client.post("/api/integrations/slack/webhook", json={"text": "x"}).status_code == 401
    r = client.post("/api/integrations/slack/webhook", params={"token": "demo-slack-secret"}, json={"text": "VPN keeps dropping", "user_name": "meena"}).json()
    assert r["module"] == "incident" and r["created"].startswith("INC")
    body = json.dumps({"summary": "Customer cannot pay via bot", "transcript": "...", "customer": True, "account": "ACC0001001", "channel": "whatsapp"}).encode()
    sig = hmac.new(b"demo-chatbot-secret", body, hashlib.sha256).hexdigest()
    w = client.post("/api/integrations/chatbot/webhook", content=body, headers={"X-Neurealm Service Desk-Signature": sig, "Content-Type": "application/json"}).json()
    assert w["module"] == "case"
    case = client.get(f"/api/records/case/{w['id']}", headers=agent).json()
    assert case["data"]["entitled"] and case["data"]["channel"] == "whatsapp"
    q = client.post("/api/integrations/quality_audit/webhook", params={"token": "demo-quality_audit-secret"}, json={"number": case["number"], "score": 88, "findings": []}).json()
    assert q["updated"] == case["number"]
    fb = client.post("/api/integrations/workflow_hub/webhook", params={"token": "demo-workflow_hub-secret"}, json={"module": "facility_request", "title": "Badge reader broken"}).json()
    assert fb["module"] == "facility_request"
    c = client.post("/api/integrations/connectors", json={"kind": "webhook", "name": "Custom", "config": {"events": ["created"]}}, headers=admin).json()
    assert len(c["secret"]) == 32
    assert client.post(f"/api/integrations/connectors/{c['id']}/test", headers=agent).json()["status"] == "simulated"

def test_servicenow_migration(client, admin, agent):
    rows = [{"number": "INC0010001", "short_description": "Legacy: SAP slow", "state": "2", "priority": "2", "impact": "2", "urgency": "2", "assignment_group": "Application Support", "sys_created_on": "2026-09-01 10:00:00"},
            {"number": "INC0010002", "short_description": "Legacy: mouse broken", "state": "7", "priority": "4", "close_notes": "Replaced"},
            {"number": "", "short_description": "bad"}]
    dry = client.post("/api/integrations/servicenow/import", json={"table": "incident", "records": rows, "dry_run": True}, headers=admin).json()
    assert dry["imported"] == 2 and len(dry["errors"]) == 1
    assert not any(r["data"].get("sn_number") == "INC0010001" for r in client.get("/api/records/incident", headers=agent).json())
    res = client.post("/api/integrations/servicenow/import", json={"table": "incident", "records": rows}, headers=admin).json()
    assert res["imported"] == 2
    again = client.post("/api/integrations/servicenow/import", json={"table": "incident", "records": rows}, headers=admin).json()
    assert again["imported"] == 0 and again["skipped"] == 2
    m = {r["data"].get("sn_number"): r for r in client.get("/api/records/incident", headers=agent).json()}
    assert m["INC0010001"]["state"] == "in_progress" and m["INC0010001"]["priority"] == "P2" and m["INC0010001"]["assignment_group"]["name"] == "Application Support"
    assert m["INC0010002"]["state"] == "closed"
    ch = client.post("/api/integrations/servicenow/import", json={"table": "change_request", "records": [{"number": "CHG0030001", "short_description": "Legacy change", "state": "-2"}]}, headers=admin).json()
    assert ch["module"] == "change" and ch["imported"] == 1
    kb = client.post("/api/integrations/servicenow/import", json={"table": "kb_knowledge", "records": [{"short_description": "Old KB", "text": "body"}]}, headers=admin).json()
    assert kb["imported"] == 1
    assert client.post("/api/integrations/servicenow/import", json={"table": "incident", "records": rows}, headers=agent).status_code == 403

def test_autoresolve_security_guardrail(client, agent):
    inc = mk(client, agent, "Suspicious phishing email received in Outlook")
    r = client.post(f"/api/autoresolve/{inc['id']}", headers=agent).json()
    assert r["run"]["state"] == "escalated" and r["record"]["state"] != "resolved"
