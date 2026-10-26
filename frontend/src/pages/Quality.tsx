import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { pathFor } from "../modules";
import { Page, Stat, Ico } from "../ui";
export default function Quality() {
  const [s, setS] = useState<any>(null);
  const load = () => api.get("/quality/summary").then((r) => setS(r.data));
  useEffect(() => { load(); }, []);
  const run = async () => setS((await api.post("/quality/audit")).data);
  const tone = (n: number) => (n >= 80 ? "text-emerald-600" : n >= 60 ? "text-amber-600" : "text-red-600");
  return (
    <Page title="Quality audit Quality & Compliance Auditing" actions={<button className="btn" onClick={run}><Ico n="sparkles" />Audit 100% of resolved tickets</button>}>
      {!s?.audited ? <div className="card p-6 text-slate-500">No audits yet — run the auditor.</div> : <>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4"><Stat label="Tickets audited" value={s.audited} /><Stat label="Coverage" value={`${s.coverage_pct}%`} tone="text-emerald-600" /><Stat label="Avg quality score" value={s.avg_score} tone={tone(s.avg_score)} />
          <Stat label="Positive sentiment" value={s.sentiment.positive || 0} tone="text-emerald-600" /><Stat label="Negative sentiment" value={s.sentiment.negative || 0} tone="text-red-600" /></div>
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="card p-4"><h3 className="font-semibold mb-2">Process adherence checks</h3>{s.checks.map((c: any) => <div key={c.key} className="text-sm mb-2"><div className="flex justify-between"><span>{c.label}</span><b className={tone(c.pass_pct)}>{c.pass_pct}%</b></div><div className="bg-slate-100 h-2 rounded"><div className="bg-brand-500 h-2 rounded" style={{ width: `${c.pass_pct}%` }} /></div></div>)}</div>
          <div className="card overflow-hidden"><div className="px-4 py-3 font-semibold">Agent scorecards & training gaps</div><table className="w-full"><tbody>{s.by_agent.map((a: any) => <tr key={a.agent}><td className="td">{a.agent}</td><td className="td">{a.tickets} tickets</td><td className={`td font-bold ${tone(a.avg_score)}`}>{a.avg_score}</td><td className="td text-xs text-slate-500">{a.training_gaps.join("; ") || "—"}</td></tr>)}</tbody></table></div>
        </div>
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="card p-4"><h3 className="font-semibold mb-2">Top findings</h3>{s.top_findings.map((f: any) => <div key={f.finding} className="flex justify-between text-sm py-1 border-b last:border-0"><span>{f.finding}</span><b>{f.count}</b></div>)}</div>
          <div className="card p-4"><h3 className="font-semibold mb-2">Lowest-scoring tickets</h3>{s.lowest.map((l: any) => <div key={l.record_id} className="text-sm py-1 flex justify-between"><Link className="text-brand-600" to={`${pathFor(l.module)}/${l.record_id}`}>{l.number} {l.title}</Link><b className={tone(l.score)}>{l.score}</b></div>)}</div>
        </div></>}
    </Page>
  );
}
