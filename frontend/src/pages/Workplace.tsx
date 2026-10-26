import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Page, State, Ico } from "../ui";
export default function Workplace() {
  const [day, setDay] = useState(new Date().toISOString().slice(0, 10)); const [av, setAv] = useState<any[]>([]); const [vis, setVis] = useState<any[]>([]);
  const [b, setB] = useState({ space: "Huddle 2", start: "15:00", end: "16:00", title: "Meeting" }); const [msg, setMsg] = useState("");
  const load = () => api.get("/workplace/availability", { params: { day } }).then((r) => setAv(r.data));
  useEffect(() => { load(); }, [day]);
  useEffect(() => { api.get("/workplace/visitors/today").then((r) => setVis(r.data)).catch(() => {}); }, []);
  const book = async () => { const r = await api.post("/records/reservation", { title: b.title, data: { space: b.space, start: `${day}T${b.start}`, end: `${day}T${b.end}`, attendees: 4 } }); setMsg(r.data.state === "conflict" ? `${r.data.number}: conflict — space already booked` : `${r.data.number} confirmed`); load(); };
  const hours = Array.from({ length: 10 }, (_, i) => 9 + i);
  return (
    <Page title="Workplace Services" actions={<><Link className="btn-ghost" to="/m/facility_request">Facilities requests</Link><Link className="btn-ghost" to="/m/visitor">Visitors</Link><Link className="btn" to="/m/facility_request/new"><Ico n="plus" />Facilities request</Link></>}>
      <div className="card p-4 space-y-3"><div className="flex gap-2 items-end"><div><label className="label">Date</label><input aria-label="Date" type="date" className="input" value={day} onChange={(e) => setDay(e.target.value)} /></div>
        <div><label className="label">Space</label><select aria-label="Space" className="input" value={b.space} onChange={(e) => setB({ ...b, space: e.target.value })}>{av.map((s) => <option key={s.space}>{s.space}</option>)}</select></div>
        <div><label className="label">From</label><input aria-label="From" type="time" className="input" value={b.start} onChange={(e) => setB({ ...b, start: e.target.value })} /></div><div><label className="label">To</label><input aria-label="To" type="time" className="input" value={b.end} onChange={(e) => setB({ ...b, end: e.target.value })} /></div>
        <div><label className="label">Purpose</label><input aria-label="Purpose" className="input" value={b.title} onChange={(e) => setB({ ...b, title: e.target.value })} /></div><button className="btn" onClick={book}>Reserve</button><span className="text-sm">{msg}</span></div>
        <div className="overflow-x-auto"><div className="grid" style={{ gridTemplateColumns: `140px repeat(${hours.length}, minmax(60px,1fr))` }}>
          <div />{hours.map((h) => <div key={h} className="text-xs text-slate-500 text-center">{h}:00</div>)}
          {av.map((s) => [<div key={s.space} className="text-sm font-medium py-2">{s.space}</div>, ...hours.map((h) => { const bk = s.bookings.find((x: any) => +x.start.slice(11, 13) <= h && +x.end.slice(11, 13) > h);
            return <div key={s.space + h} title={bk?.title} className={`m-0.5 rounded text-[10px] px-1 truncate ${bk ? "bg-brand-500 text-white" : "bg-emerald-50"}`}>{bk && +bk.start.slice(11, 13) === h ? bk.title : ""}</div>; })])}
        </div></div></div>
      <div className="card overflow-hidden"><div className="px-4 py-3 font-semibold">Visitors today</div><table className="w-full"><tbody>{vis.map((v) => <tr key={v.id}><td className="td">{v.data.visitor_name}</td><td className="td">{v.data.company}</td><td className="td">Host: {v.data.host}</td><td className="td">{v.data.nda_signed ? "NDA signed" : "NDA pending"}</td><td className="td"><State s={v.state} /></td><td className="td"><Link className="text-brand-600" to={`/m/visitor/${v.id}`}>open</Link></td></tr>)}</tbody></table></div>
    </Page>
  );
}
