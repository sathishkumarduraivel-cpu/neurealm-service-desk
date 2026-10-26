import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errMsg, type Rec } from "../api";
import { useAuth } from "../auth";
import { Page, Priority, Sla, State, Stat, Ico } from "../ui";
export function CsmOverview() {
  const [accts, setAccts] = useState<Rec[]>([]); const [sel, setSel] = useState<number | null>(null); const [ov, setOv] = useState<any>(null);
  useEffect(() => { api.get("/records/account").then((r) => { setAccts(r.data); if (r.data[0]) setSel(r.data[r.data.length - 1].id); }); }, []);
  useEffect(() => { if (sel) api.get(`/csm/accounts/${sel}/overview`).then((r) => setOv(r.data)); }, [sel]);
  return (
    <Page title="Customer Service — Account 360" actions={<><Link className="btn-ghost" to="/m/case">All cases</Link><Link className="btn-ghost" to="/m/entitlement">Entitlements</Link><Link className="btn" to="/m/account/new"><Ico n="plus" />Account</Link></>}>
      <div className="flex gap-2 flex-wrap">{accts.map((a) => <button key={a.id} onClick={() => setSel(a.id)} className={sel === a.id ? "btn" : "btn-ghost"}>{a.title} <span className="text-xs opacity-70">({a.data.tier})</span></button>)}</div>
      {ov && <>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4"><Stat label="Health score" value={ov.health_score} tone={ov.health_score >= 70 ? "text-emerald-600" : "text-amber-600"} /><Stat label="Open cases" value={ov.open_cases} /><Stat label="Contacts" value={ov.contacts.length} />
          <Stat label="Entitlement" value={ov.entitlements[0]?.data.sla_tier || "none"} /></div>
        <div className="grid lg:grid-cols-3 gap-4">
          <div className="card overflow-hidden lg:col-span-2"><div className="px-4 py-3 font-semibold">Cases</div><table className="w-full"><tbody>{ov.cases.map((c: Rec) => <tr key={c.id}><td className="td"><Link className="text-brand-600 font-mono" to={`/m/case/${c.id}`}>{c.number}</Link></td><td className="td">{c.title}</td><td className="td"><Priority p={c.priority} /></td><td className="td"><State s={c.state} /></td><td className="td"><Sla s={c.sla_status} /></td><td className="td text-xs">{c.data.channel}</td></tr>)}</tbody></table></div>
          <div className="space-y-4"><div className="card p-4"><h3 className="font-semibold mb-2">Contacts</h3>{ov.contacts.map((c: Rec) => <div key={c.id} className="text-sm py-1">{c.title}<div className="text-xs text-slate-500">{c.data.email} · {c.data.phone}</div></div>)}</div>
            <div className="card p-4"><h3 className="font-semibold mb-2">Entitlements</h3>{ov.entitlements.map((e: Rec) => <div key={e.id} className="text-sm">{e.title}<div className="w-full bg-slate-100 h-2 rounded mt-1"><div className="h-2 bg-brand-500 rounded" style={{ width: `${(100 * e.data.used_hours) / e.data.support_hours}%` }} /></div><div className="text-xs text-slate-500">{e.data.used_hours}/{e.data.support_hours} hrs used · ends {e.data.end_date}</div></div>)}{!ov.entitlements.length && <p className="text-sm text-slate-400">No entitlement</p>}</div></div>
        </div></>}
    </Page>
  );
}
export function CustomerPortal() {
  const { user } = useAuth(); const nav = useNavigate(); const [cases, setCases] = useState<Rec[]>([]); const [f, setF] = useState({ title: "", description: "", account: "ACC0001001", channel: "portal", product: "Chatbot" }); const [err, setErr] = useState("");
  useEffect(() => { api.get("/records/case").then((r) => setCases(r.data.filter((c: Rec) => c.requester?.id === user?.id))); }, []);
  const submit = async (e: any) => { e.preventDefault(); try { const { data } = await api.post("/records/case", { title: f.title, description: f.description, data: { account: f.account, channel: f.channel, product: f.product } }); nav(`/m/case/${data.id}`); } catch (x) { setErr(errMsg(x)); } };
  return (
    <div><div className="bg-gradient-to-r from-sky-700 to-brand-600 text-white px-10 py-10"><h1 className="text-3xl font-bold">Customer Support Portal</h1><p className="text-white/70">Raise and track support cases for Neurealm products — Chatbot, PMO, Quality audit, SLA Assist and more.</p></div>
      <Page title="">
        <div className="grid lg:grid-cols-2 gap-4">
          <form onSubmit={submit} className="card p-5 space-y-3"><h3 className="font-semibold">Open a new case</h3>
            <input required className="input" placeholder="Subject" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
            <textarea className="input h-24" placeholder="Describe the problem" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
            <div className="grid grid-cols-3 gap-2"><div><label className="label">Account no.</label><input aria-label="Account no." className="input" value={f.account} onChange={(e) => setF({ ...f, account: e.target.value })} /></div>
              <div><label className="label">Product</label><select aria-label="Product" className="input" value={f.product} onChange={(e) => setF({ ...f, product: e.target.value })}>{["Chatbot", "PMO", "Quality audit", "SLA Assist", "Remote Agent", "Workflow connector"].map((p) => <option key={p}>{p}</option>)}</select></div>
              <div><label className="label">Channel</label><select aria-label="Channel" className="input" value={f.channel} onChange={(e) => setF({ ...f, channel: e.target.value })}>{["portal", "email", "phone", "chat", "whatsapp"].map((p) => <option key={p}>{p}</option>)}</select></div></div>
            {err && <div className="text-red-600 text-sm">{err}</div>}<button className="btn">Submit case</button><p className="text-xs text-slate-500">Your entitlement is verified automatically and the right SLA applied.</p></form>
          <div className="card overflow-hidden"><div className="px-4 py-3 font-semibold">My cases</div><table className="w-full"><tbody>{cases.map((c) => <tr key={c.id}><td className="td"><Link className="text-brand-600 font-mono" to={`/m/case/${c.id}`}>{c.number}</Link></td><td className="td">{c.title}</td><td className="td"><State s={c.state} /></td><td className="td text-xs">{c.data.entitled ? <span className="inline-flex items-center gap-1 text-emerald-600"><Ico n="check" />Entitled</span> : "—"}</td></tr>)}
            {!cases.length && <tr><td className="td text-slate-400">No cases yet</td></tr>}</tbody></table></div>
        </div>
      </Page></div>
  );
}
