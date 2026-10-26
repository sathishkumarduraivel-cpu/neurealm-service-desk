import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Rec } from "../api";
import { Page, Stat, Ico, PageLoading } from "../ui";
const heatColor = (l: number, c: number) => { const s = l * c; return s >= 20 ? "bg-red-600 text-white" : s >= 12 ? "bg-orange-400 text-white" : s >= 6 ? "bg-amber-200" : "bg-emerald-100"; };
export default function Grc() {
  const [c, setC] = useState<any>(null); const [mon, setMon] = useState<any[]>([]);
  const load = () => api.get("/grc/compliance").then((r) => setC(r.data));
  useEffect(() => { load(); }, []);
  const monitor = async () => { const r = await api.post("/grc/controls/monitor"); setMon(r.data); load(); };
  if (!c) return <Page title="Governance, Risk & Compliance"><PageLoading /></Page>;
  return (
    <Page title="Governance, Risk & Compliance" actions={<><Link className="btn-ghost" to="/m/policy">Policies</Link><Link className="btn-ghost" to="/m/risk">Risks</Link><Link className="btn-ghost" to="/m/control">Controls</Link><Link className="btn-ghost" to="/m/audit_engagement">Audits</Link><button className="btn" onClick={monitor}><Ico n="sparkles" />Run continuous control monitoring</button></>}>
      <div className="grid lg:grid-cols-4 gap-4">{c.frameworks.map((f: any) => <div key={f.framework} className="card p-4"><div className="text-xs uppercase font-semibold text-slate-500">{f.framework}</div>
        <div className={`text-3xl font-bold ${f.compliance_pct >= 80 ? "text-emerald-600" : f.compliance_pct >= 50 ? "text-amber-600" : "text-red-600"}`}>{f.compliance_pct}%</div>
        <div className="text-xs text-slate-500">{f.effective} effective · {f.ineffective} ineffective · {f.not_tested} not tested</div></div>)}<Stat label="Open audit findings" value={c.open_findings} tone="text-amber-600" /></div>
      {mon.length > 0 && <div className="card overflow-hidden"><div className="px-4 py-3 font-semibold">Automated control test results</div><table className="w-full"><tbody>{mon.map((m, i) => <tr key={i}><td className="td">{m.framework}</td><td className="td font-mono">{m.control}</td>
        <td className="td"><span className={`px-2 py-0.5 rounded text-xs ${m.status === "effective" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{m.status}</span></td><td className="td text-xs">{m.evidence}</td></tr>)}</tbody></table></div>}
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card p-4"><h3 className="font-semibold mb-2">Risk heat map (likelihood × consequence)</h3><div className="grid grid-cols-6 gap-1 text-xs">
          {c.risk_heatmap.map((row: number[], i: number) => [<div key={"l" + i} className="flex items-center justify-end pe-1 text-slate-500">L{5 - i}</div>, ...row.map((n, j) => <div key={i + "-" + j} className={`h-12 rounded flex items-center justify-center font-bold ${heatColor(5 - i, j + 1)}`}>{n || ""}</div>)])}
          <div />{[1, 2, 3, 4, 5].map((x) => <div key={x} className="text-center text-slate-500">C{x}</div>)}</div></div>
        <div className="card p-4"><h3 className="font-semibold mb-2">Top risks</h3>{c.top_risks.map((r: Rec) => <div key={r.id} className="flex justify-between text-sm py-1 border-b last:border-0"><Link className="text-brand-600" to={`/m/risk/${r.id}`}>{r.title}</Link><span><b>{r.data.risk_score}</b> {r.data.risk_level} · {r.data.treatment}</span></div>)}
          <h3 className="font-semibold mt-4 mb-1">Policies due for review</h3>{c.policies_due_review.map((p: Rec) => <div key={p.id} className="text-sm"><Link className="text-brand-600" to={`/m/policy/${p.id}`}>{p.title}</Link> · {p.data.review_date}</div>)}{!c.policies_due_review.length && <p className="text-sm text-slate-400">None</p>}</div>
      </div>
    </Page>
  );
}
