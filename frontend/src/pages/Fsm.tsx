import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Page, Priority, State, Ico, PageLoading } from "../ui";
export default function Fsm() {
  const [b, setB] = useState<any>(null); const [msg, setMsg] = useState("");
  const load = () => api.get("/fsm/board").then((r) => setB(r.data));
  useEffect(() => { load(); }, []);
  const opt = async () => { const r = await api.post("/fsm/optimize"); setMsg(`AI dispatch scheduled ${r.data.scheduled.length} work order(s)`); load(); };
  if (!b) return <Page title="Field Service"><PageLoading /></Page>;
  return (
    <Page title="Field Service — Dispatch Board" actions={<><Link className="btn-ghost" to="/m/work_order">All work orders</Link><Link className="btn-ghost" to="/m/work_order/new"><Ico n="plus" />Work order</Link><button className="btn" onClick={opt}><Ico n="sparkles" />Optimize dispatch</button></>}>
      {msg && <div className="text-sm text-emerald-700">{msg}</div>}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card p-4"><h3 className="font-semibold mb-2">Unassigned ({b.unassigned.length})</h3>{b.unassigned.map((w: any) => <div key={w.id} className="border rounded-lg p-2 mb-2 text-sm"><div className="flex justify-between"><Link className="text-brand-600 font-mono" to={`/m/work_order/${w.id}`}>{w.number}</Link><Priority p={w.priority} /></div>{w.title}<div className="text-xs text-slate-500">skill: {w.data.skill} · {w.data.customer}</div>
          <button className="btn-ghost text-xs mt-1" onClick={async () => { await api.post(`/fsm/dispatch/${w.id}`); load(); }}>Dispatch</button></div>)}{!b.unassigned.length && <p className="text-sm text-slate-400">All work orders dispatched</p>}</div>
        {b.technicians.map((t: any) => <div key={t.id} className="card p-4"><h3 className="font-semibold"><Ico n="tech" className="me-1.5 text-muted-foreground" />{t.name}</h3><div className="text-xs text-slate-500 mb-2">Skills: {t.skills.join(", ")}</div>
          {t.jobs.map((w: any) => <div key={w.id} className="border-s-4 border-brand-500 bg-slate-50 rounded p-2 mb-2 text-sm"><div className="flex justify-between"><span className="font-mono text-xs">{w.data.scheduled_start?.replace("T", " ")}</span><State s={w.state} /></div>{w.title}<div className="text-xs text-slate-500">{w.data.customer} · {w.data.duration_h}h · {w.data.skill}</div></div>)}</div>)}
      </div>
    </Page>
  );
}
