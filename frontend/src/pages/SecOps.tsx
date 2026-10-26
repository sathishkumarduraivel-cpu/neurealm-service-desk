import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Rec } from "../api";
import { Page, Priority, State, Stat, Ico, PageLoading } from "../ui";
const SV: Record<string, string> = { critical: "bg-red-600 text-white", high: "bg-orange-500 text-white", medium: "bg-amber-200", low: "bg-slate-100" };
export default function SecOps() {
  const [s, setS] = useState<any>(null); const [sirs, setSirs] = useState<Rec[]>([]); const [out, setOut] = useState<any>(null);
  const load = () => { api.get("/secops/summary").then((r) => setS(r.data)); api.get("/records/sec_incident").then((r) => setSirs(r.data)); };
  useEffect(() => { load(); }, []);
  const pb = async (id: number, dry: boolean) => { const r = await api.post(`/secops/${id}/playbook`, null, { params: { dry_run: dry } }); setOut(r.data); load(); };
  const siem = async () => { await api.post("/secops/siem", { source: "sentinel", rule: "Suspicious PowerShell download cradle", severity: "high", attack_vector: "malware", host: "build-srv-02", mitre_tactic: "Execution" }); load(); };
  if (!s) return <Page title="Security Operations"><PageLoading /></Page>;
  return (
    <Page title="Security Operations" actions={<><button className="btn-ghost" onClick={siem}>Simulate SIEM alert</button><Link className="btn-ghost" to="/m/vulnerability">Vulnerabilities</Link><Link className="btn" to="/m/sec_incident/new"><Ico n="plus" />Security incident</Link></>}>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4"><Stat label="Open security incidents" value={s.open_incidents} tone="text-red-600" /><Stat label="Open vulnerabilities" value={s.open_vulns} />
        <Stat label="Critical vulns" value={s.vulns_by_severity.critical || 0} tone="text-red-600" /><Stat label="Overdue vulns" value={s.overdue_vulns} tone="text-amber-600" /><Stat label="Playbooks" value={s.playbooks.length} /></div>
      <div className="card overflow-hidden"><div className="px-4 py-3 font-semibold">Security incidents</div><table className="w-full"><thead><tr>{["Number", "Title", "Vector", "MITRE", "Priority", "State", "Response playbook"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody>{sirs.map((r) => <tr key={r.id}><td className="td"><Link className="text-brand-600 font-mono" to={`/m/sec_incident/${r.id}`}>{r.number}</Link></td><td className="td">{r.title}</td><td className="td">{r.data.attack_vector}</td><td className="td text-xs">{r.data.mitre_tactic}</td><td className="td"><Priority p={r.priority} /></td><td className="td"><State s={r.state} /></td>
          <td className="td space-x-1">{s.playbooks.includes(r.data.attack_vector) && r.state !== "closed" && <><button className="btn-ghost text-xs" onClick={() => pb(r.id, true)}>Dry run</button><button className="btn text-xs" onClick={() => pb(r.id, false)}>Execute</button></>}</td></tr>)}</tbody></table></div>
      {out && <div className="card p-4 text-sm"><b>{out.dry_run ? <><Ico n="flask" className="me-1" />Dry run</> : <><Ico n="shield" className="me-1" />Executed</>} on {out.record.number}</b><ol className="list-decimal ms-5 mt-2">{out.steps.map((x: any) => <li key={x.step}>{x.step} — <span className="text-slate-500">{x.status}</span></li>)}</ol></div>}
      <div className="card overflow-hidden"><div className="px-4 py-3 font-semibold">Top vulnerabilities</div><table className="w-full"><tbody>{s.top_vulns.map((v: Rec) => <tr key={v.id}><td className="td"><Link className="text-brand-600 font-mono" to={`/m/vulnerability/${v.id}`}>{v.data.cve}</Link></td><td className="td">{v.data.affected_ci}</td><td className="td font-bold">{v.data.cvss}</td>
        <td className="td"><span className={`px-2 py-0.5 rounded text-xs ${SV[v.data.severity]}`}>{v.data.severity}</span></td><td className="td">{v.data.patch_available ? "patch available" : "no patch"}</td><td className="td"><State s={v.state} /></td></tr>)}</tbody></table></div>
    </Page>
  );
}
