import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Page, Stat, fmt, Ico, PageLoading } from "../ui";
const SC: Record<string, string> = { resolved: "bg-emerald-100 text-emerald-700", awaiting_approval: "bg-amber-100 text-amber-700", escalated: "bg-sky-100 text-sky-700", no_match: "bg-slate-100 text-slate-500", dry_run: "bg-violet-100 text-violet-700" };
export default function Autonomy() {
  const { user } = useAuth(); const [st, setSt] = useState<any>(null); const [runs, setRuns] = useState<any[]>([]); const [pbs, setPbs] = useState<any[]>([]); const [msg, setMsg] = useState("");
  const load = () => { api.get("/autoresolve/stats").then((r) => setSt(r.data)); api.get("/autoresolve/runs").then((r) => setRuns(r.data)); };
  useEffect(() => { load(); api.get("/autoresolve/playbooks").then((r) => setPbs(r.data)); }, []);
  const runAll = async () => { const r = await api.post("/autoresolve/run-all"); setMsg(`Evaluated ${r.data.evaluated} open incident(s): ${JSON.stringify(r.data.by_state)}`); load(); };
  const setS = async (b: any) => { await api.put("/autoresolve/settings", b); load(); };
  if (!st) return <Page title="Autonomous Resolution"><PageLoading /></Page>;
  return (
    <Page title="Agentic Auto-Resolution Engine" actions={<button className="btn" onClick={runAll}><Ico n="bot" />Run on open incidents</button>}>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4"><Stat label="Autonomous resolution rate" value={`${st.autonomous_resolution_rate_pct}%`} tone="text-brand-600" /><Stat label="Auto-resolved" value={st.auto_resolved} tone="text-emerald-600" />
        <Stat label="Awaiting human approval" value={st.awaiting_approval} tone="text-amber-600" /><Stat label="Escalated to humans" value={st.escalated} /><Stat label="Confidence threshold" value={`${Math.round(st.settings.threshold * 100)}%`} /></div>
      {msg && <div className="text-sm text-emerald-700">{msg}</div>}
      {user?.role === "admin" && <div className="card p-4 flex gap-6 items-center text-sm"><b>Guardrails</b>
        <label className="flex gap-2 items-center"><input type="checkbox" checked={st.settings.enabled} onChange={(e) => setS({ enabled: e.target.checked })} /> Engine enabled</label>
        <label className="flex gap-2 items-center"><input type="checkbox" checked={st.settings.on_create} onChange={(e) => setS({ on_create: e.target.checked })} /> Run automatically on new incidents</label>
        <label className="flex gap-2 items-center">Threshold <input type="range" min={0.3} max={0.95} step={0.05} value={st.settings.threshold} onChange={(e) => setS({ threshold: +e.target.value })} /> {Math.round(st.settings.threshold * 100)}%</label>
        <span className="text-xs text-slate-500">High-risk playbooks always require human approval.</span></div>}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card overflow-hidden lg:col-span-2"><div className="px-4 py-3 font-semibold">Recent agent runs</div><table className="w-full"><thead><tr>{["Ticket", "Playbook", "Confidence", "Risk", "Outcome", "When"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{runs.map((r) => <tr key={r.id}><td className="td"><Link className="text-brand-600 font-mono" to={`/incidents/${r.record_id}`}>{r.number}</Link><div className="text-xs text-slate-500 truncate max-w-[220px]">{r.title}</div></td><td className="td text-xs">{r.playbook}</td>
            <td className="td"><div className="w-20 bg-slate-100 h-2 rounded"><div className="bg-brand-500 h-2 rounded" style={{ width: `${r.confidence * 100}%` }} /></div><span className="text-xs">{Math.round(r.confidence * 100)}%</span></td>
            <td className="td text-xs">{r.risk}</td><td className="td"><span className={`px-2 py-0.5 rounded text-xs ${SC[r.state]}`}>{r.state.replace("_", " ")}</span></td><td className="td text-xs">{fmt(r.created_at)}</td></tr>)}</tbody></table></div>
        <div className="card p-4"><h3 className="font-semibold mb-2">Playbook library</h3>{pbs.map((p) => <div key={p.id} className="py-2 border-b last:border-0 text-sm"><div className="flex justify-between"><b>{p.name}</b><span className={`text-xs px-1.5 rounded ${p.risk === "high" ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>{p.risk} risk</span></div>
          <ol className="text-xs text-slate-500 list-decimal ms-4">{p.steps.map((s: any, i: number) => <li key={i}>{s[0]}: {s[1]}</li>)}</ol></div>)}</div>
      </div>
    </Page>
  );
}
