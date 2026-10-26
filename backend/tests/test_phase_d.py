def test_siem_intake_and_playbook(client, agent):
    r = client.post("/api/secops/siem", json={"rule": "Mass phishing URL clicks", "severity": "high", "attack_vector": "phishing", "host": "Email (M365)"}, headers=agent)
    assert r.status_code == 201; s = r.json()
    assert s["number"].startswith("SIR") and s["priority"] == "P1" and s["sla_due_at"]
    dry = client.post(f"/api/secops/{s['id']}/playbook", params={"dry_run": True}, headers=agent).json()
    assert dry["dry_run"] and all(x["status"] == "simulated" for x in dry["steps"]) and dry["record"]["state"] == "new"
    run = client.post(f"/api/secops/{s['id']}/playbook", headers=agent).json()
    assert run["record"]["state"] == "contain" and run["record"]["data"]["playbook_runs"] == 1
    assert len(client.get(f"/api/records/sec_incident/{s['id']}", headers=agent).json()["comments"]) == len(run["steps"])

def test_vuln_import_and_scoring(client, agent):
    res = client.post("/api/secops/vulns/import", json=[{"cve": "CVE-2026-0001", "cvss": 9.1, "affected_ci": "web-01"}, {"cve": "CVE-2024-3400", "cvss": 10.0, "affected_ci": "vpn-gw-01"}], headers=agent).json()
    assert res == {"created": 1, "updated": 1}
    v = next(x for x in client.get("/api/records/vulnerability", headers=agent).json() if x["data"]["cve"] == "CVE-2026-0001")
    assert v["data"]["severity"] == "critical" and v["priority"] == "P1" and v["data"]["remediation_days"] == 7
    s = client.get("/api/secops/summary", headers=agent).json()
    assert s["open_vulns"] >= 5 and s["overdue_vulns"] >= 1 and "phishing" in s["playbooks"]

def test_grc_continuous_monitoring_and_compliance(client, agent):
    res = client.post("/api/grc/controls/monitor", headers=agent).json()
    by = {(r["framework"], r["control"]): r for r in res}
    assert by[("ISO27001", "A.8.15")]["status"] == "effective"          # audit chain intact
    assert by[("ISO27001", "A.8.8")]["status"] == "ineffective"          # seeded overdue critical vuln
    c = client.get("/api/grc/compliance", headers=agent).json()
    fw = {f["framework"]: f for f in c["frameworks"]}
    assert set(fw) == {"ISO27001", "SOC2", "GDPR"} and all(f["not_tested"] == 0 or f["controls"] for f in fw.values())
    assert 0 <= fw["ISO27001"]["compliance_pct"] <= 100 and sum(map(sum, c["risk_heatmap"])) >= 5 and c["open_findings"] == 8

def test_risk_scoring(client, agent):
    r = client.post("/api/records/risk", json={"title": "Cloud region outage", "data": {"likelihood": 4, "consequence": 5}}, headers=agent).json()
    assert r["data"]["risk_score"] == 20 and r["data"]["risk_level"] == "critical" and r["priority"] == "P1"

def test_spm_portfolio_resources_convert(client, agent):
    p = client.get("/api/spm/portfolio", headers=agent).json()
    scores = [d["data"]["priority_score"] for d in p["demands"]]
    assert scores == sorted(scores, reverse=True)
    assert any(x["data"]["health"] == "red" for x in p["projects"])
    res = {r["person"]: r for r in client.get("/api/spm/resources", headers=agent).json()}
    assert res["rahul@neurealm.com"]["over_allocated"] is False and res["divya@neurealm.com"]["total_pct"] == 120 and res["divya@neurealm.com"]["over_allocated"]
    approved = next(d for d in p["demands"] if d["state"] == "approved")
    prj = client.post(f"/api/spm/demands/{approved['id']}/convert", headers=agent).json()
    assert prj["number"].startswith("PRJ") and prj["data"]["demand"] == approved["number"]
    pending = next(d for d in p["demands"] if d["state"] != "approved")
    assert client.post(f"/api/spm/demands/{pending['id']}/convert", headers=agent).status_code == 400
