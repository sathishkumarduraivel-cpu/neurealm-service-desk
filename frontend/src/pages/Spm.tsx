import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errMsg, type Rec } from "../api";
import { Page, State, Stat, Ico, PageLoading } from "../ui";
const HC: Record<string, string> = { green: "bg-emerald-500", amber: "bg-amber-400", red: "bg-red-500" };
export default function Spm() {
  const [p, setP] = useState<any>(null); const [res, setRes] = useState<any[]>([]); const [msg, setMsg] = useState("");
  const load = () => { api.get("/spm/portfolio").then((r) => setP(r.data)); api.get("/spm/resources").then((r) => setRes(r.data)); };
  useEffect(() => { load(); }, []);
  const conv = async (id: number) => { try { const r = await api.post(`/spm/demands/${id}/convert`); setMsg(`Created ${r.data.number} (synced to PMO)`); load(); } catch (x) { setMsg(errMsg(x)); } };
  if (!p) return <Page title="Strategic Portfolio"><PageLoading /></Page>;
  return (
    <Page title="Strategic Portfolio Management" actions={<><Link className="btn-ghost" to="/m/demand/new"><Ico n="plus" />Demand</Link><Link className="btn" to="/m/project/new"><Ico n="plus" />Project</Link></>}>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4"><Stat label="Projects" value={(p.health.green || 0) + (p.health.amber || 0) + (p.health.red || 0)} /><Stat label="On track (green)" value={p.health.green || 0} /><Stat label="Projects at risk (red)" value={p.health.red || 0} tone="text-red-600" /><Stat label="Over-allocated people" value={res.filter((r) => r.over_allocated).length} tone="text-amber-600" /></div>
      {msg && <div className="text-sm text-emerald-700">{msg}</div>}
      <div className="card overflow-hidden"><div className="px-4 py-3 font-semibold">Projects</div><table className="w-full"><thead><tr>{["Project", "PM", "State", "Progress", "Schedule", "Health"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody>{p.projects.map((r: Rec) => <tr key={r.id}><td className="td"><Link className="text-brand-600" to={`/m/project/${r.id}`}>{r.title}</Link></td><td className="td">{r.data.pm}</td><td className="td"><State s={r.state} /></td>
          <td className="td"><div className="w-28 bg-slate-100 h-2 rounded"><div className="bg-brand-500 h-2 rounded" style={{ width: `${r.data.percent_complete}%` }} /></div><span className="text-xs">{r.data.percent_complete}%</span></td>
          <td className="td text-xs">{r.data.percent_complete ?? 0}% done of {r.data.planned_pct ?? 0}% planned</td><td className="td"><span className={`inline-block w-3 h-3 rounded-full ${HC[r.data.health]}`} /> {r.data.health}</td></tr>)}</tbody></table></div>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card overflow-hidden"><div className="px-4 py-3 font-semibold">Demand pipeline (AI-scored)</div><table className="w-full"><tbody>{p.demands.map((d: Rec) => <tr key={d.id}><td className="td"><Link className="text-brand-600" to={`/m/demand/${d.id}`}>{d.title}</Link></td><td className="td font-bold">{d.data.priority_score}</td><td className="td text-xs">{d.data.recommendation}</td><td className="td"><State s={d.state} /></td>
          <td className="td">{d.state === "approved" && !d.data.project && <button className="btn text-xs" onClick={() => conv(d.id)}>→ Project</button>}{d.data.project && <span className="text-xs">{d.data.project}</span>}</td></tr>)}</tbody></table></div>
        <div className="card p-4"><h3 className="font-semibold mb-2">Resource allocation</h3>{res.map((r) => <div key={r.person} className="mb-2 text-sm"><div className="flex justify-between"><span>{r.person}</span><b className={r.over_allocated ? "text-red-600" : ""}>{r.total_pct}%</b></div>
          <div className="flex h-3 rounded overflow-hidden bg-slate-100">{r.assignments.map((a: any, i: number) => <div key={i} title={`${a.title} ${a.pct}%`} style={{ width: `${Math.min(100, a.pct) / Math.max(100, r.total_pct) * 100}%` }} className={["bg-brand-500", "bg-sky-400", "bg-emerald-400", "bg-violet-400"][i % 4]} />)}</div></div>)}</div>
      </div>
    </Page>
  );
}
