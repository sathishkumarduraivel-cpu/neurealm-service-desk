import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errMsg, type Rec } from "../api";
import { useAuth } from "../auth";
import { Page, State, Ico } from "../ui";
export default function Patch() {
  const { user } = useAuth(); const [jobs, setJobs] = useState<Rec[]>([]); const [ks, setKs] = useState<any>(null); const [sel, setSel] = useState<Rec | null>(null); const [msg, setMsg] = useState(""); const [reason, setReason] = useState("");
  const load = async (id?: number) => { const r = await api.get("/records/patch_job"); setJobs(r.data); setSel(r.data.find((j: Rec) => j.id === (id ?? sel?.id)) || r.data[0]); api.get("/patch/kill-switch").then((x) => setKs(x.data)); };
  useEffect(() => { load(); }, []);
  const act = async (path: string) => { try { setMsg(""); await api.post(`/patch/${sel!.id}/${path}`); load(sel!.id); } catch (x) { setMsg(errMsg(x)); } };
  const kill = async (engaged: boolean) => { try { const r = await api.post("/patch/kill-switch", { engaged, reason }); setMsg(engaged ? `Kill switch engaged; halted: ${r.data.halted_jobs.join(", ") || "none"}` : "Kill switch released"); load(); } catch (x) { setMsg(errMsg(x)); } };
  const d = sel?.data.dry_run; const dep = sel?.data.deployment;
  return (
    <Page title="AI Patch & Endpoint Management" actions={<Link className="btn" to="/m/patch_job/new"><Ico n="plus" />Patch job</Link>}>
      {ks && <div className={`card p-4 flex items-center gap-4 ${ks.engaged ? "border-red-500 bg-red-50" : ""}`}><div className={`flex size-10 items-center justify-center rounded-lg ${ks.engaged ? "bg-red-100 text-red-600" : "bg-emerald-100 text-emerald-600"}`}>{ks.engaged ? <Ico n="stop" className="size-5" /> : <Ico n="shield" className="size-5" />}</div>
        <div className="flex-1"><b>Global kill switch: {ks.engaged ? "ENGAGED" : "released"}</b><div className="text-xs text-slate-500">{ks.engaged ? `${ks.reason} — by ${ks.by} at ${ks.at}` : "All approved patch deployments may proceed."}</div></div>
        {user?.role === "admin" ? (ks.engaged ? <button className="btn-ghost" onClick={() => kill(false)}>Release</button> : <><input className="input max-w-xs" placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} /><button className="btn bg-red-600 hover:bg-red-700" onClick={() => kill(true)}>Engage kill switch</button></>) : <span className="text-xs text-slate-500">Admin only</span>}</div>}
      {msg && <div className="text-sm text-red-600">{msg}</div>}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card p-3 space-y-2">{jobs.map((j) => <button key={j.id} onClick={() => setSel(j)} className={`w-full text-start p-3 rounded-lg border ${sel?.id === j.id ? "border-brand-500 bg-brand-50" : ""}`}><div className="flex justify-between text-xs"><span className="font-mono">{j.number}</span><State s={j.state} /></div><div className="text-sm font-medium">{j.title}</div><div className="text-xs text-slate-500">{j.data.os} · {j.data.environment} · {j.data.patches}</div></button>)}</div>
        {sel && <div className="card p-5 lg:col-span-2 space-y-4 text-sm">
          <div className="flex justify-between"><h3 className="font-semibold text-base">{sel.title}</h3><div className="flex gap-2"><button className="btn-ghost" onClick={() => act("dry-run")}><Ico n="flask" />Dry run</button><button className="btn-ghost" onClick={() => act("approve")} disabled={sel.state !== "dry_run_complete"}><Ico n="checkCircle" />Approve</button><button className="btn" onClick={() => act("deploy")} disabled={!["approved", "halted"].includes(sel.state)}><Ico n="rocket" />Deploy</button></div></div>
          {d ? <div className="grid grid-cols-2 gap-4">
            <div><div className="label">Targets ({d.targets.length})</div>{d.targets.map((t: any) => <div key={t.id} className="text-xs">{t.name} <span className="text-slate-400">{t.os}</span></div>)}</div>
            <div className="space-y-1"><div><span className="label inline">Risk score</span> <b className={d.risk_score >= 50 ? "text-red-600" : "text-emerald-600"}>{d.risk_score}</b></div><div>Reboot required: {d.reboot_required ? "yes" : "no"}</div><div>Impacted services: {d.impacted_services.join(", ") || "none"}</div>
              <div>Change conflicts: {d.change_conflicts.join(", ") || "none"}</div><div>{d.requires_admin_approval ? <span className="inline-flex items-center gap-1 text-amber-600"><Ico n="lock" />Admin approval required</span> : "Agent approval sufficient"}</div>
              <div className="text-xs text-slate-500">Waves: {d.waves.map((w: any) => `${w.wave} (${w.targets.length})`).join(" → ")}</div></div></div> : <p className="text-slate-500">Run a dry run to simulate targets, impact, conflicts and risk before anything is touched.</p>}
          {dep && <div><div className="label">Deployment {dep.auto_halted && <span className="text-red-600">— auto-halted (failure rate &gt; 20%)</span>}</div><div className="flex flex-wrap gap-1">{dep.results.map((r: any) => <span key={r.target} className={`px-2 py-0.5 rounded text-xs ${r.status === "success" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{r.wave}: {r.target} {r.status}</span>)}</div></div>}
        </div>}
      </div>
    </Page>
  );
}
