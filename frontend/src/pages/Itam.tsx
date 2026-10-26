import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Page, Stat, PageLoading } from "../ui";
const CC: Record<string, string> = { compliant: "bg-emerald-100 text-emerald-700", under_utilized: "bg-amber-100 text-amber-700", over_deployed: "bg-red-100 text-red-700" };
export default function Itam() {
  const [s, setS] = useState<any>(null);
  useEffect(() => { api.get("/itam/summary").then((r) => setS(r.data)); }, []);
  if (!s) return <Page title="IT Asset Management"><PageLoading /></Page>;
  return (
    <Page title="IT Asset Management" actions={<><Link className="btn-ghost" to="/m/asset">Assets</Link><Link className="btn-ghost" to="/m/license">Licenses</Link><Link className="btn-ghost" to="/m/contract">Contracts</Link></>}>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4"><Stat label="Assets" value={s.assets.total} /><Stat label="Licences tracked" value={s.licenses.length} /><Stat label="Contracts expiring soon" value={s.contracts_expiring.length} />
        <Stat label="Licences to review" value={s.licenses.filter((l: any) => l.compliance !== "compliant").length} tone="text-orange-600" /></div>
      <div className="card overflow-hidden"><div className="px-4 py-3 font-semibold">Software license compliance</div><table className="w-full"><thead><tr>{["License", "Owned", "Used", "Utilization", "Status", "Savings"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody>{s.licenses.map((l: any) => <tr key={l.id}><td className="td"><Link className="text-brand-600" to={`/m/license/${l.id}`}>{l.title}</Link></td><td className="td">{l.seats_owned}</td><td className="td">{l.seats_used}</td>
          <td className="td"><div className="w-32 bg-slate-100 rounded h-2"><div className={`h-2 rounded ${l.utilization_pct > 100 ? "bg-red-500" : "bg-brand-500"}`} style={{ width: `${Math.min(100, l.utilization_pct)}%` }} /></div><span className="text-xs">{l.utilization_pct}%</span></td>
          <td className="td"><span className={`px-2 py-0.5 rounded text-xs ${CC[l.compliance]}`}>{l.compliance.replace("_", " ")}</span></td><td className="td">{l.compliance === "compliant" ? "Looks good" : "Worth a review"}</td></tr>)}</tbody></table></div>
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card p-4"><h3 className="font-semibold mb-2">Assets by state</h3>{Object.entries(s.assets.by_state).map(([k, v]: any) => <div key={k} className="flex justify-between text-sm py-0.5"><span>{k.replace("_", " ")}</span><b>{v}</b></div>)}</div>
        <div className="card p-4"><h3 className="font-semibold mb-2">Contracts expiring ≤ 60 days</h3>{s.contracts_expiring.map((c: any) => <div key={c.id} className="text-sm py-0.5"><Link className="text-brand-600" to={`/m/contract/${c.id}`}>{c.title}</Link> · {c.end_date}</div>)}</div>
        <div className="card p-4"><h3 className="font-semibold mb-2">Warranty expiring ≤ 60 days</h3>{s.assets.warranty_expiring.map((a: any) => <div key={a.id} className="text-sm py-0.5"><Link className="text-brand-600" to={`/m/asset/${a.id}`}>{a.title}</Link> · {a.warranty_end}</div>)}{!s.assets.warranty_expiring.length && <p className="text-sm text-slate-400">None</p>}</div>
      </div>
    </Page>
  );
}
