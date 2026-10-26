import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errMsg, type Rec } from "../api";
import { Page, State, Ico } from "../ui";
function Progress({ id }: { id: number }) {
  const [t, setT] = useState<Rec[]>([]);
  useEffect(() => { api.get(`/records/hr_case/${id}/children`).then((r) => setT(r.data)); }, [id]);
  if (!t.length) return <span className="text-xs text-slate-400">—</span>;
  const d = t.filter((x) => x.state === "done").length;
  return <div className="w-40"><div className="bg-slate-100 h-2 rounded"><div className="bg-emerald-500 h-2 rounded" style={{ width: `${(100 * d) / t.length}%` }} /></div><span className="text-xs">{d}/{t.length} tasks</span></div>;
}
export default function Hr() {
  const [rows, setRows] = useState<Rec[]>([]); const [f, setF] = useState({ type: "onboarding", employee: "", date: "", manager: "", employee_email: "" }); const [msg, setMsg] = useState("");
  const load = () => api.get("/records/hr_case").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);
  const go = async (e: any) => { e.preventDefault(); try { const r = await api.post("/hr/lifecycle", f); setMsg(`Created ${r.data.case.number} with ${r.data.tasks} tasks across IT, Facilities and HR`); load(); } catch (x) { setMsg(errMsg(x)); } };
  return (
    <Page title="HR Service Delivery" actions={<Link className="btn" to="/m/hr_case/new"><Ico n="plus" />HR case</Link>}>
      <form onSubmit={go} className="card p-4 flex flex-wrap gap-2 items-end"><div className="w-full font-semibold text-sm">Employee lifecycle workflow</div>
        <div><label className="label">Type</label><select aria-label="Type" className="input" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}><option>onboarding</option><option>offboarding</option></select></div>
        <div><label className="label">Employee</label><input aria-label="Employee" required className="input" value={f.employee} onChange={(e) => setF({ ...f, employee: e.target.value })} /></div>
        <div><label className="label">Date</label><input aria-label="Date" type="date" className="input" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></div>
        <div><label className="label">Employee email</label><input aria-label="Employee email" className="input" type="email" value={f.employee_email} onChange={(e) => setF({ ...f, employee_email: e.target.value })} /></div>
        <div><label className="label">Manager</label><input aria-label="Manager" className="input" value={f.manager} onChange={(e) => setF({ ...f, manager: e.target.value })} /></div>
        <button className="btn">Start workflow</button><span className="text-sm text-emerald-700">{msg}</span></form>
      <div className="card overflow-hidden"><table className="w-full"><thead><tr>{["Number", "Title", "Category", "Employee", "State", "Lifecycle progress"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody>{rows.map((r) => <tr key={r.id}><td className="td"><Link className="text-brand-600 font-mono" to={`/m/hr_case/${r.id}`}>{r.number}</Link></td><td className="td">{r.title}{r.data.confidential && <Ico n="lock" className="ms-1.5 size-3.5 text-amber-600" />}</td><td className="td">{r.data.hr_category}</td><td className="td">{r.data.employee}</td><td className="td"><State s={r.state} /></td><td className="td">{r.data.lifecycle ? <Progress id={r.id} /> : "—"}</td></tr>)}</tbody></table></div>
    </Page>
  );
}
